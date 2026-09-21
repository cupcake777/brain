"""Integration tests for Task 4 recovery against the real portable outbox.

The existing ``tests/test_recovery.py`` exercises a ``FakeOutbox`` to prove
the recovery contract in isolation. These tests drive the **real**
``Outbox`` (SQLite-backed, durable across process restarts) so that:

* ack / version semantics are not silently dropped by an adapter;
* lease ownership is arbitrated by SQLite, not by a fake dictionary;
* unknown server outcomes (``dropped_response_unknown``) surface via
  ``inspect_unknown`` rather than getting blindly retried;
* the enrichment-provider-unavailable branch hands the capture to the
  real ``enqueue_enrichment`` API;
* two recovery workers with distinct owner labels cannot stomp on each
  other's leases.

The tests run against a temp ``Outbox``; no real HTTP, no sleeps.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "brain-loop" / "scripts"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import outbox as outbox_mod  # noqa: E402
import recovery as recovery_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Local clock + scripting transport
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ScriptedTransport:
    """A transport callable that scripts per-(kind, id) ``TransportResult``.

    Mirrors the existing ``FakeTransport`` in ``test_brain_outbox.py`` but
    lives in this module so the recovery integration suite is fully
    self-contained.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._queues: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._default: list[dict[str, Any]] = []

    def queue(self, kind: str, job_id: str, **fields: Any) -> None:
        self._queues.setdefault((kind, job_id), []).append(fields)

    def set_default(self, **fields: Any) -> None:
        self._default.append(fields)

    def __call__(self, job: outbox_mod.Job) -> outbox_mod.TransportResult:
        self.calls.append({
            "id": job.id,
            "kind": job.kind,
            "version": job.version,
            "attempts": job.attempts,
        })
        q = self._queues.get((job.kind, job.id))
        if q:
            fields = q.pop(0)
        elif self._default:
            fields = self._default.pop(0)
        else:
            return outbox_mod.TransportResult(
                state="ok",
                acknowledged_version=job.version,
                response={"echo": job.id, "version": job.version},
            )
        return outbox_mod.TransportResult(**fields)


def _capture_record(tag: str = "cap-1") -> dict[str, Any]:
    return {
        "id": tag,
        "kind": "tool.completed",
        "invocation_id": tag.replace("cap-", "inv-"),
        "session_id": "sess-1",
        "occurred_at": 100.0,
        "project_id": "proj-7",
        "tool_name": "terminal",
        "result_state": "ok",
        "error": None,
        "args": {"command": "ls"},
        "result": "ok",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def tmp_outbox(tmp_path: Path, request: pytest.FixtureRequest
               ) -> outbox_mod.Outbox:
    clock_fixture = None
    try:
        clock_fixture = request.getfixturevalue("clock")
    except pytest.FixtureLookupError:
        clock_fixture = None
    return outbox_mod.Outbox(tmp_path / "outbox.sqlite3",
                              clock=clock_fixture)


def _make_runner(transport: ScriptedTransport
                 ) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Bridge: real outbox transport -> recovery transport_runner contract.

    Recovery's ``transport_runner`` accepts the job's ``payload`` (a dict)
    and must return ``{"acknowledged_version": int, ...}``. We use the
    ScriptedTransport's recorded response to fabricate that envelope.
    """

    def runner(payload: dict[str, Any]) -> dict[str, Any]:
        # The recovery contract only sees ``payload``; it can't reach into
        # ``job.id`` directly. We use the payload's id as the lookup key.
        # Real callers inject transport via the recovery wrapper; here we
        # keep the test transport dumb and let recovery decide.
        return {"ok": True, "captured_id": payload.get("id")}

    # Re-bind so tests can introspect; not used here.
    return runner


# A more useful runner: use the payload id as the ScriptedTransport key.
def _runner_factory(transport: ScriptedTransport
                    ) -> Callable[[dict[str, Any]], dict[str, Any]]:
    calls: list[str] = []

    def runner(payload: dict[str, Any]) -> dict[str, Any]:
        job_id = payload.get("id") or "anon"
        calls.append(job_id)
        # Reach back into the transport by routing via a (kind, id) queue
        # set in the test. We can't call the transport directly because
        # recovery's contract is dict-in / dict-out, not TransportResult.
        # Tests that need TransportResult-style scripting wire the real
        # outbox transport instead (see ``test_unknown_outcome_*``).
        return {"ok": True, "captured_id": job_id}

    runner.calls = calls  # type: ignore[attr-defined]
    return runner


# ---------------------------------------------------------------------------
# Ack semantics — recovery must enforce strict version ack
# ---------------------------------------------------------------------------


def test_recovery_ack_missing_acknowledged_version_triggers_retry(
        tmp_outbox: outbox_mod.Outbox, clock: FakeClock) -> None:
    """If the transport runner returns no ``acknowledged_version``, recovery
    must treat the result as a retry rather than silently ack.

    Drives the **real** outbox: enqueues one job, runs recovery with a
    scripted transport that returns no ack, asserts the job stays
    ``pending`` and ``attempts`` increments.
    """
    job_id = tmp_outbox.enqueue("tool.completed", _capture_record("cap-1"))

    # Runner returns a dict WITHOUT ``acknowledged_version`` → recovery
    # must convert this to a retry, NOT record_success.
    rec = recovery_mod.Recovery(
        outbox=tmp_outbox,
        transport_runner=lambda _p: {"oops": True},
        owner="recovery-test",
        max_attempts=5,
    )

    counts = rec.run_once(clock=clock)
    job = tmp_outbox.get(job_id)
    assert job is not None
    # The job should still be pending — recovery refused to ack.
    assert job.state == "pending"
    assert job.attempts >= 1
    assert counts["retried"] >= 1 or counts["completed"] == 0


def test_recovery_ack_wrong_version_triggers_retry(
        tmp_outbox: outbox_mod.Outbox, clock: FakeClock) -> None:
    """A transport response whose ``acknowledged_version`` does NOT match
    ``job.version`` must surface as a retry. Recovery never silently
    records success on a wrong-version ack.
    """
    job_id = tmp_outbox.enqueue("tool.completed", _capture_record("cap-2"))

    def runner(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"acknowledged_version": 100}  # wrong: queued version is 1

    rec = recovery_mod.Recovery(
        outbox=tmp_outbox,
        transport_runner=runner,
        owner="recovery-test",
    )
    # Force the wrapper to use our runner; the wrapped version check inside
    # recovery.py is what we are exercising.
    counts = rec.run_once(clock=clock)
    job = tmp_outbox.get(job_id)
    assert job is not None
    assert job.state == "pending"
    assert counts["retried"] >= 1


# ---------------------------------------------------------------------------
# Lease ownership: two workers, restart, no shared-owner reuse
# ---------------------------------------------------------------------------


def test_recovery_two_distinct_workers_no_shared_owner_collision(
        tmp_outbox: outbox_mod.Outbox, clock: FakeClock) -> None:
    """Two Recovery instances with distinct ``owner`` labels running against
    the same SQLite outbox must NOT stomp on each other's leases.
    """
    a = tmp_outbox.enqueue("tool.completed", _capture_record("cap-A"))
    b = tmp_outbox.enqueue("tool.completed", _capture_record("cap-B"))

    transport = ScriptedTransport()
    transport.queue("tool.completed", a,
                    state="ok", acknowledged_version=1,
                    response={"id": a})
    transport.queue("tool.completed", b,
                    state="ok", acknowledged_version=1,
                    response={"id": b})

    rec_a = recovery_mod.Recovery(
        outbox=tmp_outbox,
        transport_runner=lambda _p: {"ok": True},
        owner="worker-alpha",
    )
    rec_b = recovery_mod.Recovery(
        outbox=tmp_outbox,
        transport_runner=lambda _p: {"ok": True},
        owner="worker-bravo",
    )
    rec_a._runner = lambda _p: {"acknowledged_version": 1}  # type: ignore[assignment]
    rec_b._runner = lambda _p: {"acknowledged_version": 1}  # type: ignore[assignment]

    counts_a = rec_a.run_once(clock=clock)
    counts_b = rec_b.run_once(clock=clock)

    # Each worker processes only the jobs it leased. Both jobs must end
    # ``completed`` without any lease reuse.
    assert counts_a["completed"] >= 1
    assert counts_b["completed"] >= 1
    assert tmp_outbox.get(a).state == "completed"
    assert tmp_outbox.get(b).state == "completed"

    # Re-opening the outbox and inspecting via a fresh worker must show
    # zero pending leases left behind by either owner.
    reloaded = outbox_mod.Outbox(tmp_outbox.path, clock=clock)
    for job_id in (a, b):
        job = reloaded.get(job_id)
        assert job is not None
        assert job.lease_owner is None
        assert job.lease_expires_at is None


def test_recovery_restart_lease_recovery_after_crash(
        tmp_path: Path, clock: FakeClock) -> None:
    """Worker A claims a job and dies without recording success. After
    lease expiry, worker B must be able to claim and finish it without
    any shared-owner reuse between the two.
    """
    path = tmp_path / "crash_recovery.sqlite3"
    ob = outbox_mod.Outbox(path, clock=clock)
    job_id = ob.enqueue("tool.completed", _capture_record("cap-crash"))

    transport = ScriptedTransport()
    transport.queue("tool.completed", job_id,
                    state="ok", acknowledged_version=1,
                    response={"id": job_id})

    # Worker A claims then "dies" without recording.
    rec_a = recovery_mod.Recovery(
        outbox=ob,
        transport_runner=lambda _p: {"ok": True},
        owner="worker-crashed",
    )
    # Direct lease claim without completing.
    ob.claim_ready(clock=clock, owner="worker-crashed", lease_seconds=10)
    del ob

    # Fresh process: new outbox handle.
    ob2 = outbox_mod.Outbox(path, clock=clock)
    # Lease still held; no claim yet.
    pre = ob2.claim_ready(clock=clock, owner="worker-survivor",
                           lease_seconds=10)
    assert pre == []

    # Advance past lease expiry.
    clock.advance(11)
    rec_b = recovery_mod.Recovery(
        outbox=ob2,
        transport_runner=lambda _p: {"acknowledged_version": 1},
        owner="worker-survivor",
    )
    counts = rec_b.run_once(clock=clock)
    assert counts["completed"] >= 1
    assert ob2.get(job_id).state == "completed"


# ---------------------------------------------------------------------------
# Unknown server outcome — must surface via inspect_unknown, NOT blind retry
# ---------------------------------------------------------------------------


def test_recovery_unknown_server_outcome_surfaces_via_inspect_unknown(
        tmp_outbox: outbox_mod.Outbox, clock: FakeClock) -> None:
    """When the transport cannot determine whether the server accepted,
    the real outbox leaves the job pending with a populated
    ``last_response``. Recovery must surface that state via
    ``inspect_unknown`` rather than blind-retrying on the next tick.
    """
    job_id = tmp_outbox.enqueue("tool.completed", _capture_record("cap-unk"))

    transport = ScriptedTransport()
    transport.queue("tool.completed", job_id,
                    state="dropped_response_unknown",
                    error="server-accepted-but-response-dropped",
                    response={"server_id": job_id, "version": 1})

    rec = recovery_mod.Recovery(
        outbox=tmp_outbox,
        transport_runner=lambda _p: transport(tmp_outbox.get(job_id)),
        owner="recovery-test",
    )
    counts = rec.run_once(clock=clock)

    # Outbox classifies the outcome.
    assert counts["dropped_unknown"] == 1
    info = tmp_outbox.inspect_unknown(job_id)
    assert info["last_error"] == "server-accepted-but-response-dropped"
    assert info["last_response"]["server_id"] == job_id
    # Unknown is durable and excluded from normal pending claims.
    assert info["state"] == "unknown"


def test_recovery_does_not_blind_retry_unknown_after_run_once(
        tmp_outbox: outbox_mod.Outbox, clock: FakeClock) -> None:
    """Right after a ``dropped_response_unknown`` outcome, the SAME
    ``run_once`` call must NOT re-dispatch the job. Recovery is
    run-once-per-call; the durable outbox is the one that decides
    when to retry.
    """
    job_id = tmp_outbox.enqueue("tool.completed", _capture_record("cap-unk2"))

    transport = ScriptedTransport()
    transport.queue("tool.completed", job_id,
                    state="dropped_response_unknown",
                    error="network-blip", response={"partial": True})
    # If recovery were naive, it would requeue + immediately redispatch.

    rec = recovery_mod.Recovery(
        outbox=tmp_outbox,
        transport_runner=lambda _p: transport(tmp_outbox.get(job_id)),
        owner="recovery-test",
    )
    rec.run_once(clock=clock)

    # Only ONE transport call recorded.
    assert len([c for c in transport.calls if c["id"] == job_id]) == 1
    # inspect_unknown surfaces the dropped response — operator decides.
    info = tmp_outbox.inspect_unknown(job_id)
    assert info["last_error"] == "network-blip"


def test_unknown_outcome_is_not_resent_after_ticks_and_restart(
        tmp_path: Path, clock: FakeClock) -> None:
    path = tmp_path / "unknown.sqlite3"
    ob = outbox_mod.Outbox(path, clock=clock)
    job_id = ob.enqueue("tool.completed", _capture_record("cap-unknown"))
    calls = []

    def upload(payload):
        calls.append(payload)
        return outbox_mod.TransportResult(state="dropped_response_unknown")

    rec = recovery_mod.Recovery(outbox=ob, transport_runner=upload)
    rec.run_once(clock=clock)
    for _ in range(3):
        clock.advance(100)
        rec.run_once(clock=clock)
    ob.close()
    restored = outbox_mod.Outbox(path, clock=clock)
    try:
        rec = recovery_mod.Recovery(outbox=restored, transport_runner=upload)
        rec.run_once(clock=clock)
        assert len(calls) == 1
        assert restored.inspect_unknown(job_id)["state"] == "unknown"
    finally:
        restored.close()


# ---------------------------------------------------------------------------
# Enrichment provider unavailable — separate real ``enqueue_enrichment`` API
# ---------------------------------------------------------------------------


def test_recovery_provider_unavailable_enqueues_real_enrichment(
        tmp_outbox: outbox_mod.Outbox, clock: FakeClock) -> None:
    """When the transport reports ``enrichment == 'provider_unavailable'``,
    recovery MUST enqueue a row on the separate ``enrichment_jobs`` table
    via the real ``enqueue_enrichment`` API. The original upload job still
    completes (its evidence is not lost) and the enrichment follow-up is
    durable.
    """
    job_id = tmp_outbox.enqueue("tool.completed", _capture_record("cap-e"))

    def runner(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "enrichment": "provider_unavailable",
            "acknowledged_version": 1,
        }

    rec = recovery_mod.Recovery(
        outbox=tmp_outbox,
        transport_runner=runner,
        owner="recovery-test",
    )
    counts = rec.run_once(clock=clock)

    # Original upload completed.
    assert counts["completed"] == 1
    job = tmp_outbox.get(job_id)
    assert job.state == "completed"

    # Enrichment follow-up is on the separate table.
    pending_enrich = tmp_outbox.pending_enrichment()
    assert len(pending_enrich) == 1
    # The enrichment row references the original capture id.
    eid = pending_enrich[0]
    row = tmp_outbox._conn.execute(  # type: ignore[attr-defined]
        "SELECT * FROM enrichment_jobs WHERE id=?", (eid,)
    ).fetchone()
    assert row is not None
    payload = __import__("json").loads(row["payload_json"])
    assert payload.get("capture_id") == job_id or payload.get("source_id") == job_id


# ---------------------------------------------------------------------------
# Configurable owner — default must NOT be the hard-coded ``brain-recovery``
# ---------------------------------------------------------------------------


def test_recovery_default_owner_is_not_colliding() -> None:
    """Two Recovery instances with no ``owner`` argument must receive
    distinct, non-empty owner labels so concurrent workers don't fight
    over the same SQLite lease.
    """
    ob = outbox_mod.Outbox(Path("/tmp/owner-test.sqlite3"))
    try:
        rec_a = recovery_mod.Recovery(outbox=ob, transport_runner=lambda _p: {"ok": True})
        rec_b = recovery_mod.Recovery(outbox=ob, transport_runner=lambda _p: {"ok": True})
        assert rec_a._owner != rec_b._owner  # type: ignore[attr-defined]
        assert rec_a._owner  # type: ignore[attr-defined]
        assert rec_b._owner  # type: ignore[attr-defined]
    finally:
        ob.close()
        Path("/tmp/owner-test.sqlite3").unlink(missing_ok=True)


def test_recovery_owner_override_is_honored() -> None:
    """A caller-supplied ``owner`` argument must be passed verbatim to
    ``outbox.run_once`` so operators can pin worker identity."""
    ob = outbox_mod.Outbox(Path("/tmp/owner-override.sqlite3"))
    try:
        rec = recovery_mod.Recovery(
            outbox=ob,
            transport_runner=lambda _p: {"ok": True},
            owner="custom-worker-7",
        )
        assert rec._owner == "custom-worker-7"  # type: ignore[attr-defined]
    finally:
        ob.close()
        Path("/tmp/owner-override.sqlite3").unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Persistence across process restart
# ---------------------------------------------------------------------------


def test_recovery_state_persists_across_restart(
        tmp_path: Path, clock: FakeClock) -> None:
    """Completing a job via Recovery, then closing and re-opening the
    outbox, must show the same completed state. This is the durability
    contract the operator can rely on.
    """
    path = tmp_path / "persist.sqlite3"
    ob = outbox_mod.Outbox(path, clock=clock)
    job_id = ob.enqueue("tool.completed", _capture_record("cap-p"))

    transport = ScriptedTransport()
    transport.queue("tool.completed", job_id,
                    state="ok", acknowledged_version=1,
                    response={"id": job_id})

    rec = recovery_mod.Recovery(
        outbox=ob,
        transport_runner=lambda _p: {"acknowledged_version": 1},
        owner="recovery-test",
    )
    counts = rec.run_once(clock=clock)
    assert counts["completed"] == 1
    ob.close()

    reloaded = outbox_mod.Outbox(path, clock=clock)
    try:
        job = reloaded.get(job_id)
        assert job is not None
        assert job.state == "completed"
        assert job.acknowledged_version == 1
        assert job.lease_owner is None
    finally:
        reloaded.close()


# ---------------------------------------------------------------------------
# Real-Outbox detection — recovery must route to the real transport API
# ---------------------------------------------------------------------------


def test_recovery_routes_to_real_outbox_transport_api(
        tmp_outbox: outbox_mod.Outbox) -> None:
    """Sanity: when the outbox is the real SQLite outbox, recovery uses
    the transport-oriented ``run_once`` branch (the one that enforces
    ack semantics and lease ownership) and NOT the legacy handler
    branch. This is the dual-fake hardening line: future maintenance
    cannot accidentally regress to the fake-only path.
    """
    rec = recovery_mod.Recovery(
        outbox=tmp_outbox,
        transport_runner=lambda _p: {"acknowledged_version": 1},
        owner="recovery-test",
    )
    assert rec._uses_real_outbox(tmp_outbox) is True  # type: ignore[attr-defined]


def test_recovery_legacy_fake_path_is_kept_for_back_compat() -> None:
    """Legacy outboxes (handler API) must still work. The dual path is
    justified: callers with bespoke outboxes do not need to migrate to
    SQLite to keep using recovery.
    """

    class LegacyOutbox:
        def __init__(self) -> None:
            self.calls = 0

        def run_once(self, handler, *, now=None):
            self.calls += 1
            return 0

        def record_success(self, *_a, **_kw): pass
        def record_failure(self, *_a, **_kw): pass
        def requeue(self, *_a, **_kw): pass
        def escalate(self, *_a, **_kw): pass

    legacy = LegacyOutbox()
    rec = recovery_mod.Recovery(
        outbox=legacy,
        transport_runner=lambda _p: {"ok": True},
    )
    assert rec._uses_real_outbox(legacy) is False  # type: ignore[attr-defined]
    rec.run_once(now=0.0)
    assert legacy.calls == 1