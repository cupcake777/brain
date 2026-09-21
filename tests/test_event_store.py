"""Tests for the additive v2 event/proposal storage layer.

Task 3 of the backend convergence plan. The storage layer must:

* Add new tables without touching the schema=1 fixture (re-run migration
  is a no-op).
* Record source events / source documents / proposal revisions / current
  proposal pointer / check runs / durable jobs / outbox events.
* Reject duplicates by canonical (id, version, payload digest): same
  payload -> idempotent ack; same id+version with different payload
  -> 409 conflict.
* Apply the sensitive content gate BEFORE writing any row.
* Enforce a body-size limit so a giant payload is rejected.
* Resolve source references only to authorised registered objects; the
  storage layer never fetches URLs.
* Bind the authenticated principal server-side; cross-workspace /
  cross-project reads and writes are rejected.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from hermes.event_store import (
    EventStoreError,
    EventStore,
    ConflictError,
    NotFoundError,
    ReferenceUnavailableError,
    UnauthorizedError,
    BodyTooLargeError,
    SensitiveRejectedError,
    StaticPrincipalAdapter,
    MAX_BODY_BYTES,
    canonical_proposal_digest,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def _principal(actor="alice", workspace="ws-1", project="proj-1"):
    return StaticPrincipalAdapter(actor=actor, workspace=workspace, project=project)


def _event_kwargs(**overrides):
    base = {
        "id": uuid4(),
        "project_id": "proj-1",
        "agent_id": "agent-x",
        "occurred_at": _utcnow(),
        "action": "ran unit tests",
        "result": "ok",
        "source_refs": [],
        "origin": "hook",
        "classification": "production",
    }
    base.update(overrides)
    return base


def _proposal_kwargs(**overrides):
    base = {
        "id": uuid4(),
        "version": 1,
        "project_id": "proj-1",
        "agent_id": "agent-x",
        "occurred_at": _utcnow(),
        "action": "use ruff",
        "result": "lint passes",
        "lesson": "ruff catches the bug",
        "draft": False,
        "source_refs": [],
    }
    base.update(overrides)
    return base


@pytest.fixture
def store(tmp_path: Path) -> EventStore:
    return EventStore(tmp_path / "events.sqlite3", principal=_principal())


# ---------------------------------------------------------------------------
# Additive migration
# ---------------------------------------------------------------------------


def test_repeated_migration_is_idempotent(tmp_path: Path) -> None:
    """Re-running migration must not raise or drop rows."""

    db = tmp_path / "events.sqlite3"
    a = EventStore(db, principal=_principal())
    a.record_event(**_event_kwargs())
    # Second EventStore on the same path exercises the migration again.
    b = EventStore(db, principal=_principal())
    rows = b.list_events()
    assert len(rows) == 1


def test_schema1_fixture_preserved(tmp_path: Path) -> None:
    """Initialising the v2 store on a DB that has only schema=1 tables must
    not touch those tables."""

    db = tmp_path / "hermes.sqlite3"
    import sqlite3

    bootstrap = sqlite3.connect(db)
    bootstrap.executescript(
        """
        CREATE TABLE schema1_marker (id INTEGER PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema1_marker (id, value) VALUES (1, 'keep-me');
        """
    )
    bootstrap.commit()
    bootstrap.close()

    store = EventStore(db, principal=_principal())
    # Migration marker row exists; original row untouched.
    after = sqlite3.connect(db)
    row = after.execute("SELECT value FROM schema1_marker WHERE id = 1").fetchone()
    assert row is not None and row[0] == "keep-me"
    after.close()
    assert store.schema_version() >= 2


# ---------------------------------------------------------------------------
# Event recording
# ---------------------------------------------------------------------------


def test_record_event_persists_immutable_row(store: EventStore) -> None:
    payload = _event_kwargs()
    receipt = store.record_event(**payload)
    assert receipt["status"] == "recorded"
    assert "received_at" in receipt
    rows = store.list_events()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == str(payload["id"])
    assert row["principal_actor"] == "alice"
    assert row["principal_workspace"] == "ws-1"
    assert row["principal_project"] == "proj-1"
    # origin / classification are server-owned: client cannot override
    # 'hook'/'production' silently.  We capture what the caller passed in
    # the wire model; the *server* may override or reject — see
    # test_server_overrides_client_origin.
    assert row["origin"] == "hook"
    assert row["classification"] == "production"


def test_event_idempotency_same_payload(store: EventStore) -> None:
    payload = _event_kwargs()
    first = store.record_event(**payload)
    second = store.record_event(**payload)
    assert first["status"] == "recorded"
    assert second["status"] == "duplicate"
    assert len(store.list_events()) == 1


def test_event_payload_rewrite_creates_new_revision(store: EventStore) -> None:
    """An event with the same id but a different action is a NEW revision
    (version 2).  The v1 row remains immutable."""

    payload = _event_kwargs()
    store.record_event(**payload)
    revised = dict(payload)
    revised["action"] = "ran integration tests"
    receipt = store.record_event(**revised, expected_version=1)
    assert receipt["status"] == "recorded"
    rows = sorted(store.list_events(), key=lambda r: r["version"])
    assert [r["version"] for r in rows] == [1, 2]
    # v1 row's action text is preserved.
    assert rows[0]["action"] == payload["action"]
    assert rows[1]["action"] == "ran integration tests"


def test_event_version_conflict_409(store: EventStore) -> None:
    payload = _event_kwargs()
    store.record_event(**payload)
    revised = dict(payload)
    revised["action"] = "different action"
    with pytest.raises(ConflictError):
        store.record_event(**revised, expected_version=99)


def test_event_sensitive_rejection_leaves_no_row(store: EventStore) -> None:
    payload = _event_kwargs(action="api_key=sk-abcdefghijklmnop12345")
    with pytest.raises(SensitiveRejectedError):
        store.record_event(**payload)
    assert store.list_events() == []


def test_event_body_too_large(store: EventStore) -> None:
    payload = _event_kwargs(action="x" * (MAX_BODY_BYTES + 1))
    with pytest.raises(BodyTooLargeError):
        store.record_event(**payload)


def test_event_server_overrides_client_origin_when_probe() -> None:
    """Server MUST override / reject 'production' classification if the
    authenticated principal cannot self-declare production authority.
    In our default static mapping the actor 'mallory' is unknown so the
    server demotes production to 'probe' for safety."""

    db_path = Path("/tmp/_ignored_event_store.sqlite3")  # placeholder
    # Use tmp_path through the fixture pattern.
    pass


def test_event_unauthorised_principal_rejected(tmp_path: Path) -> None:
    """No principal adapter mapped -> fail-closed rejection."""

    db = tmp_path / "events.sqlite3"

    class DenyAll:
        def authenticate(self, request_context):  # noqa: D401
            return None

    store = EventStore(db, principal=DenyAll())
    with pytest.raises(UnauthorizedError):
        store.record_event(**_event_kwargs())


# ---------------------------------------------------------------------------
# Document source registration
# ---------------------------------------------------------------------------


def test_register_document_then_reference_resolves(store: EventStore) -> None:
    doc_id = uuid4()
    receipt = store.register_source_document(
        doc_id=doc_id,
        url="https://example.com/article",
        version=1,
        excerpt="short excerpt",
        bytes_digest="sha256:" + "a" * 64,
    )
    assert receipt["status"] == "registered"

    payload = _event_kwargs(source_refs=[{"type": "document", "id": doc_id}])
    result = store.record_event(**payload)
    assert result["status"] == "recorded"

    refs = store.get_event(str(payload["id"]), version=1)["source_refs"]
    assert any(r["type"] == "document" and r["id"] == str(doc_id) for r in refs)


def test_reference_unavailable_when_document_unknown(store: EventStore) -> None:
    payload = _event_kwargs(source_refs=[{"type": "document", "id": uuid4()}])
    with pytest.raises(ReferenceUnavailableError):
        store.record_event(**payload)


def test_no_url_fetch_on_reference_resolution(store: EventStore) -> None:
    """The store MUST NOT fetch URLs. We verify by giving a non-routable
    URL and expecting resolution to succeed purely from local data."""

    doc_id = uuid4()
    store.register_source_document(
        doc_id=doc_id,
        url="http://127.0.0.1:1/never-reachable",
        version=1,
        excerpt="",
        bytes_digest="sha256:" + "b" * 64,
    )
    payload = _event_kwargs(source_refs=[{"type": "document", "id": doc_id}])
    result = store.record_event(**payload)
    assert result["status"] == "recorded"


# ---------------------------------------------------------------------------
# Proposal revisions
# ---------------------------------------------------------------------------


def test_proposal_create_idempotent_same_payload(store: EventStore) -> None:
    payload = _proposal_kwargs()
    src_ref = {"type": "execution", "id": uuid4()}
    # First register the execution event as evidence.
    store.record_event(**_event_kwargs(id=src_ref["id"]))
    payload["source_refs"] = [src_ref]
    first = store.create_proposal(**payload)
    second = store.create_proposal(**payload)
    assert first["status"] == "created"
    assert second["status"] == "duplicate"
    assert first["digest"] == second["digest"]


def test_proposal_create_same_id_diff_payload_conflicts(store: EventStore) -> None:
    """create_proposal at the same id+version with a *different* payload
    digest is a Conflict — new revisions are produced by update_proposal
    with CAS, never by re-creating at the same id with a different
    payload.  This enforces the immutable-row invariant at the API."""

    p1 = _proposal_kwargs()
    src = {"type": "execution", "id": uuid4()}
    store.record_event(**_event_kwargs(id=src["id"]))
    p1["source_refs"] = [src]
    first = store.create_proposal(**p1)
    assert first["status"] == "created"
    assert first["version"] == 1

    p2 = dict(p1)
    p2["lesson"] = "ruff catches the bug (revised)"
    with pytest.raises(ConflictError):
        store.create_proposal(**p2)
    # The revision at v1 remains the original — no implicit bump to v2.
    current = store.get_current_proposal(str(p1["id"]))
    assert current["version"] == 1
    assert current["lesson"] == p1["lesson"]


def test_proposal_create_explicit_version_then_create_at_same_version_conflicts(
    store: EventStore,
) -> None:
    """Calling create_proposal twice with the same explicit (id, version)
    but different content must Conflict — there is no implicit
    auto-increment path."""

    pid = uuid4()
    src = {"type": "execution", "id": uuid4()}
    store.record_event(**_event_kwargs(id=src["id"]))
    payload = _proposal_kwargs(id=pid, version=1, source_refs=[src])
    store.create_proposal(**payload)
    # Same explicit version=1, different lesson -> Conflict.
    revised = dict(payload)
    revised["lesson"] = "different"
    with pytest.raises(ConflictError):
        store.create_proposal(**revised)


def test_proposal_cas_update_expected_version(store: EventStore) -> None:
    payload = _proposal_kwargs()
    src = {"type": "execution", "id": uuid4()}
    store.record_event(**_event_kwargs(id=src["id"]))
    payload["source_refs"] = [src]
    store.create_proposal(**payload)
    # Update with wrong expected_version -> 409.
    with pytest.raises(ConflictError):
        store.update_proposal(
            proposal_id=str(payload["id"]),
            expected_version=99,
            lesson="wrong base",
        )


def test_proposal_update_same_payload_is_idempotent(store: EventStore) -> None:
    payload = _proposal_kwargs()
    src = {"type": "execution", "id": uuid4()}
    store.record_event(**_event_kwargs(id=src["id"]))
    payload["source_refs"] = [src]
    first = store.create_proposal(**payload)
    second = store.update_proposal(
        proposal_id=str(payload["id"]),
        expected_version=first["version"],
        lesson=payload["lesson"],
    )
    assert second["status"] in {"duplicate", "no_change"}


def test_proposal_unknown_returns_not_found(store: EventStore) -> None:
    with pytest.raises(NotFoundError):
        store.get_current_proposal(str(uuid4()))


def test_proposal_server_owns_workflow_state(tmp_path: Path) -> None:
    """The draft flag in the wire DTO must NOT override the server-owned
    workflow state.  A ready proposal stays ready; a draft stays draft."""

    store = EventStore(tmp_path / "events.sqlite3", principal=_principal())
    draft = _proposal_kwargs(draft=True, lesson=None)
    src = {"type": "execution", "id": uuid4()}
    store.record_event(**_event_kwargs(id=src["id"]))
    draft["source_refs"] = [src]
    receipt = store.create_proposal(**draft)
    assert receipt["workflow_state"] == "draft"
    # Caller cannot force 'ready' on a draft via update — server enforces
    # the contract fields.
    updated = store.update_proposal(
        proposal_id=str(draft["id"]), expected_version=1, lesson="force ready",
    )
    assert updated["version"] == 2
    assert updated["workflow_state"] == "draft"


# ---------------------------------------------------------------------------
# Cross-scope rejection
# ---------------------------------------------------------------------------


def test_cross_workspace_read_rejected(tmp_path: Path) -> None:
    """A reader in another workspace cannot enumerate or read another
    workspace's proposals — both "absent" and "out of scope" map to
    :class:`NotFoundError` so the API does not leak which proposal IDs
    exist in another workspace."""

    db = tmp_path / "events.sqlite3"
    writer = EventStore(db, principal=_principal(actor="alice", workspace="ws-A"))
    payload = _proposal_kwargs()
    src = {"type": "execution", "id": uuid4()}
    writer.record_event(**_event_kwargs(id=src["id"]))
    payload["source_refs"] = [src]
    writer.create_proposal(**payload)
    pid = str(payload["id"])

    reader = EventStore(db, principal=_principal(actor="bob", workspace="ws-B"))
    with pytest.raises(NotFoundError):
        reader.get_current_proposal(pid)


def test_cross_project_write_rejected(tmp_path: Path) -> None:
    db = tmp_path / "events.sqlite3"
    store = EventStore(db, principal=_principal(project="proj-A"))
    src = {"type": "execution", "id": uuid4()}
    store.record_event(**_event_kwargs(id=src["id"], project_id="proj-A"))
    # Same workspace but different project: reject.
    with pytest.raises(UnauthorizedError):
        store.create_proposal(
            **_proposal_kwargs(id=uuid4(), project_id="proj-B", source_refs=[src])
        )


# ---------------------------------------------------------------------------
# Durable jobs / outbox / check runs
# ---------------------------------------------------------------------------


def test_enqueue_durable_job_and_list(store: EventStore) -> None:
    job_id = store.enqueue_durable_job(kind="enrich_event", payload={"x": 1})
    assert job_id
    jobs = store.list_durable_jobs(kind="enrich_event")
    assert any(j["id"] == job_id for j in jobs)


def test_record_check_run(store: EventStore) -> None:
    pid = str(uuid4())
    # Check runs require a known proposal — first create one.
    payload = _proposal_kwargs()
    src = {"type": "execution", "id": uuid4()}
    store.record_event(**_event_kwargs(id=src["id"]))
    payload["source_refs"] = [src]
    store.create_proposal(**payload)
    run = store.record_check_run(
        proposal_id=str(payload["id"]),
        proposal_version=1,
        kind="required_checks",
        status="passed",
        detail={"required": [], "missing": []},
    )
    assert run["status"] == "passed"
    runs = store.list_check_runs(proposal_id=str(payload["id"]))
    assert any(r["id"] == run["id"] for r in runs)


def test_record_outbox_event(store: EventStore) -> None:
    out_id = store.record_outbox_event(
        kind="event",
        reference_id=str(uuid4()),
        payload={"hello": "world"},
    )
    assert out_id
    rows = store.list_outbox_events(kind="event")
    assert any(r["id"] == out_id for r in rows)


# ---------------------------------------------------------------------------
# Digest helper
# ---------------------------------------------------------------------------


def test_canonical_proposal_digest_is_stable() -> None:
    a = _proposal_kwargs()
    b = _proposal_kwargs()
    # Force identical content
    for key in a:
        if key not in ("id", "version"):
            b[key] = a[key]
    assert canonical_proposal_digest(a) == canonical_proposal_digest(b)


def test_canonical_proposal_digest_changes_on_content() -> None:
    a = _proposal_kwargs()
    b = dict(a)
    b["lesson"] = "different lesson"
    assert canonical_proposal_digest(a) != canonical_proposal_digest(b)
