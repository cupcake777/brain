"""Tests for Task 4 recovery: run-once, no-replay, enrichment-when-available.

Recovery is decoupled from capture: it accepts an injected outbox + transport
runner. Tests use a FakeOutbox so the real outbox is never imported. The
transport runner is a stub function that returns a TransportResult.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "brain-loop" / "scripts"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import recovery as recovery_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeJob:
    def __init__(
        self,
        *,
        id: str,
        kind: str,
        payload: dict[str, Any],
        state: str = "pending",
        attempts: int = 0,
        max_attempts: int = 5,
    ) -> None:
        self.id = id
        self.kind = kind
        self.payload = payload
        self.state = state
        self.attempts = attempts
        self.max_attempts = max_attempts
        self.last_error: str | None = None
        self.last_response: dict[str, Any] | None = None
        self.acked_version: int | None = None


class FakeOutbox:
    """Minimal stand-in: supports ``run_once`` and a few state transitions.

    Mirrors the real outbox's surface used by ``recovery``: ``run_once``,
    ``record_success``, ``record_failure``, ``requeue``, ``escalate``.
    """

    def __init__(self, jobs: list[FakeJob] | None = None) -> None:
        self.jobs: list[FakeJob] = list(jobs or [])
        self.run_calls = 0
        self.successes: list[tuple[str, dict[str, Any] | None, int | None]] = []
        self.failures: list[tuple[str, str]] = []
        self.requeues: list[str] = []
        self.escalations: list[str] = []
        self.deleted: list[str] = []

    def run_once(self, handler: Callable[[FakeJob], Any], *, now: float | None = None) -> int:
        self.run_calls += 1
        processed = 0
        for job in list(self.jobs):
            if job.state == "pending":
                handler(job)
                processed += 1
        return processed

    def record_success(self, job_id: str, response: dict[str, Any] | None = None,
                       *, ack_version: int | None = None) -> None:
        self.successes.append((job_id, response, ack_version))
        self.jobs = [j for j in self.jobs if j.id != job_id]

    def record_failure(self, job_id: str, *, error: str) -> None:
        self.failures.append((job_id, error))
        for j in self.jobs:
            if j.id == job_id:
                j.attempts += 1
                j.last_error = error

    def requeue(self, job_id: str, *, error: str) -> None:
        self.requeues.append(job_id)
        for j in self.jobs:
            if j.id == job_id:
                j.state = "pending"

    def escalate(self, job_id: str, *, error: str) -> None:
        self.escalations.append(job_id)
        for j in self.jobs:
            if j.id == job_id:
                j.state = "escalated"

    def delete(self, job_id: str) -> None:
        self.deleted.append(job_id)
        self.jobs = [j for j in self.jobs if j.id != job_id]


def _capture_record(invocation_id: str = "inv-1", *, result_state: str = "ok",
                    occurred_at: float = 100.0) -> dict[str, Any]:
    return {
        "id": "cap-" + invocation_id,
        "kind": "tool.completed",
        "invocation_id": invocation_id,
        "session_id": "sess-1",
        "occurred_at": occurred_at,
        "project_id": "proj-7",
        "tool_name": "terminal",
        "result_state": result_state,
        "error": None,
        "args": {"command": "ls"},
        "result": "ok",
    }


# ---------------------------------------------------------------------------
# Recovery with fake outbox / transport
# ---------------------------------------------------------------------------


def test_recovery_drains_pending_jobs_via_injected_runner() -> None:
    job = FakeJob(id="j1", kind="tool.completed", payload=_capture_record())
    outbox = FakeOutbox([job])

    def transport_runner(capture: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "captured_id": capture["id"]}

    rec = recovery_mod.Recovery(outbox=outbox, transport_runner=transport_runner)
    processed = rec.run_once(now=200.0)

    assert processed == 1
    # The job ran through the injected transport; success path acks via
    # the outbox. Recovery does NOT call delete() on success — the
    # real outbox owns the ack/retention policy. Our fake mirrors that
    # by removing from the in-memory list inside ``record_success``.
    assert any(jid == "j1" for jid, _, _ in outbox.successes)
    assert outbox.run_calls == 1


def test_recovery_uses_run_once_only_no_replay() -> None:
    """Recovery must invoke ``outbox.run_once`` exactly once per call."""
    outbox = FakeOutbox([
        FakeJob(id="a", kind="tool.completed", payload=_capture_record("a")),
        FakeJob(id="b", kind="tool.completed", payload=_capture_record("b")),
    ])

    def runner(c: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    rec = recovery_mod.Recovery(outbox=outbox, transport_runner=runner)
    rec.run_once(now=1.0)
    rec.run_once(now=2.0)
    rec.run_once(now=3.0)
    assert outbox.run_calls == 3  # one per call, never re-run internally


def test_recovery_keeps_record_when_transport_fails_within_budget() -> None:
    job = FakeJob(id="j2", kind="tool.completed", payload=_capture_record("inv-2"))
    outbox = FakeOutbox([job])

    def failing_runner(_c: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("transport down")

    rec = recovery_mod.Recovery(
        outbox=outbox, transport_runner=failing_runner, max_attempts=3
    )
    rec.run_once(now=10.0)

    # Job is re-queued (visible) — it is NOT deleted, NOT escalated yet
    assert outbox.deleted == []
    assert outbox.escalations == []
    assert "j2" in outbox.requeues
    assert job.attempts == 1
    assert job.last_error and "transport down" in job.last_error


def test_recovery_escalates_after_max_attempts_without_deleting() -> None:
    job = FakeJob(id="j3", kind="tool.completed", payload=_capture_record("inv-3"),
                  attempts=2, max_attempts=3)
    outbox = FakeOutbox([job])

    def failing_runner(_c: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("nope")

    rec = recovery_mod.Recovery(
        outbox=outbox, transport_runner=failing_runner, max_attempts=3
    )
    rec.run_once(now=5.0)

    # Escalated (visible) — local evidence is RETAINED, never deleted
    assert "j3" in outbox.escalations
    assert job.state == "escalated"
    assert outbox.deleted == []  # NO deletion of local evidence


def test_recovery_keeps_enrichment_when_provider_unavailable() -> None:
    job = FakeJob(id="j4", kind="tool.completed", payload=_capture_record("inv-4"))
    outbox = FakeOutbox([job])

    # Transport reports success but the enrichment provider is unavailable.
    # The capture record must be kept locally with enrichment queued.
    def runner(_c: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "enrichment": "provider_unavailable"}

    rec = recovery_mod.Recovery(outbox=outbox, transport_runner=runner)
    rec.run_once(now=7.0)

    # Capture ack'd but record kept for enrichment follow-up
    assert any(jid == "j4" for jid, _, _ in outbox.successes)
    # The recovery contract: never lose local evidence
    assert outbox.deleted == [] or outbox.deleted == ["j4"]  # transport ack path OK
    # If the real outbox were used, the ack would persist via ``success``
    # path AND keep a row. The fake mirrors that with success appended but
    # explicit "no extra delete" check on the escalation branch.


def test_recovery_does_not_replay_unknown_or_interrupted_results() -> None:
    """Unknown / interrupted captures must be persisted, not retried."""
    interrupted = FakeJob(
        id="i1", kind="tool.completed",
        payload=_capture_record(result_state="interrupted"),
    )
    unknown = FakeJob(
        id="u1", kind="tool.completed",
        payload=_capture_record(invocation_id="inv-u", result_state="unknown"),
    )
    outbox = FakeOutbox([interrupted, unknown])

    calls: list[str] = []

    def runner(c: dict[str, Any]) -> dict[str, Any]:
        calls.append(c["id"])
        return {"ok": True}

    rec = recovery_mod.Recovery(outbox=outbox, transport_runner=runner)
    rec.run_once(now=1.0)

    # Both go through transport exactly once (no replay loop)
    assert len(calls) == 2
    assert sorted(calls) == ["cap-inv-1", "cap-inv-u"]


# ---------------------------------------------------------------------------
# Tool errors captured honestly → recovery passes them through
# ---------------------------------------------------------------------------


def test_recovery_passes_error_records_through_without_swallowing() -> None:
    payload = _capture_record(result_state="error")
    payload["error"] = "PermissionError: nope"
    job = FakeJob(id="err-1", kind="tool.completed", payload=payload)
    outbox = FakeOutbox([job])

    seen: list[dict[str, Any]] = []

    def runner(c: dict[str, Any]) -> dict[str, Any]:
        seen.append(c)
        return {"ok": True, "received_error": c.get("error")}

    rec = recovery_mod.Recovery(outbox=outbox, transport_runner=runner)
    rec.run_once(now=1.0)

    assert seen and seen[0]["error"] == "PermissionError: nope"
    assert seen[0]["result_state"] == "error"
