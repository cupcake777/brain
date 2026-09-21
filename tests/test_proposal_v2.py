"""Tests for the standalone v2 proposal/event API router.

Task 4 of the backend convergence plan. The router delegates every read
and write to :class:`hermes.event_store.EventStore` and never inspects
caller-supplied headers for authority. These tests cover the contract
behaviours that matter for the Task 4 spec:

* Unauthenticated requests are rejected with 503 (default fail-closed
  adapter) — no raw caller header authority.
* Cross-workspace / cross-project references are rejected with 403.
* Idempotent duplicate POSTs ack as ``recorded`` without bumping the
  version.
* A stale ``expected_version`` on PUT returns 409.
* Oversized request bodies are rejected with 413 *before* the contract
  validator runs (verified by ensuring the body cap is enforced even
  when Pydantic would have accepted the payload).
* Sensitive payloads (labelled credentials) are rejected with 422 and
  never echo the matched substring.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hermes.event_store import (
    EventStore,
    MAX_BODY_BYTES,
    Principal,
    StaticPrincipalAdapter,
)
from hermes.proposal_protocol_v2 import (
    DEFAULT_PRINCIPAL_ADAPTER,
    build_router,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FixedAdapter:
    """Request-bound adapter that returns a fixed Principal.

    Used for the happy-path tests; we swap the principal per test by
    rebuilding the router with a different adapter.
    """

    def __init__(self, *, actor: str, workspace: str, project: str) -> None:
        self._principal = Principal(actor=actor, workspace=workspace, project=project)

    def authenticate(self, request):  # noqa: ARG002 — protocol shape
        return self._principal


class _PrincipalAdapter:
    """Adapter that wraps a server-resolved :class:`Principal`.

    The router resolves the trusted principal per request and passes it
    to ``store_factory(principal)``; the EventStore then calls
    ``adapter.authenticate(...)`` to obtain the identity it should bind
    to the write. This adapter simply returns the principal it was
    constructed with, keeping the request-bound binding server-side.
    """

    def __init__(self, principal: Principal) -> None:
        self._principal = principal

    def authenticate(self, request):  # noqa: ARG002 — protocol shape
        return self._principal


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "v2.sqlite3"


@pytest.fixture
def store_factory(db_path: Path):
    """Per-request EventStore factory.

    The router closes the store after each request, but the underlying
    SQLite file persists for the lifetime of the test. The factory
    wraps the request-supplied ``Principal`` with a thin adapter so
    the EventStore (which expects ``adapter.authenticate(...)``) binds
    to that exact server-resolved identity.
    """

    def _factory(principal: Principal | None = None) -> EventStore:
        if principal is None:
            principal = Principal(actor="alice", workspace="ws-team", project="brain")
        return EventStore(str(db_path), principal=_PrincipalAdapter(principal))

    return _factory


@pytest.fixture
def app(store_factory):
    adapter = _FixedAdapter(actor="alice", workspace="ws-team", project="brain")
    app = FastAPI()
    app.include_router(build_router(store_factory=store_factory, principal_adapter=adapter))
    return app


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


def _event_payload(*, project_id: str = "brain", agent_id: str = "agent-1",
                   occurred_at: str = "2026-09-17T08:00:00Z",
                   action: str | None = "apply patch",
                   result: str | None = "ok",
                   target_id: str | None = "ops/brain",
                   source_refs=None) -> dict:
    return {
        "id": str(uuid4()),
        "project_id": project_id,
        "agent_id": agent_id,
        "occurred_at": occurred_at,
        "target_id": target_id,
        "action": action,
        "result": result,
        "source_refs": source_refs or [],
    }


def _proposal_payload(*, project_id: str = "brain", agent_id: str = "agent-1",
                      draft: bool = True, source_refs=None,
                      occurred_at: str | None = None,
                      action: str | None = "apply patch",
                      result: str | None = "ok",
                      lesson: str | None = "atomic replace",
                      target_id: str | None = "ops/brain",
                      version: int = 1) -> dict:
    return {
        "id": str(uuid4()),
        "version": version,
        "project_id": project_id,
        "agent_id": agent_id,
        "occurred_at": occurred_at,
        "target_id": target_id,
        "action": action,
        "result": result,
        "lesson": lesson,
        "draft": draft,
        "source_refs": source_refs or [],
    }


# ---------------------------------------------------------------------------
# 503 when no adapter is configured
# ---------------------------------------------------------------------------


def test_no_adapter_returns_503(store_factory) -> None:
    app = FastAPI()
    app.include_router(
        build_router(store_factory=store_factory, principal_adapter=DEFAULT_PRINCIPAL_ADAPTER)
    )
    c = TestClient(app)
    resp = c.post("/api/v2/brain/events", json=_event_payload())
    assert resp.status_code == 503
    assert "principal" in resp.json()["detail"].lower()


def test_adapter_returning_none_returns_503(store_factory) -> None:
    class _NoneAdapter:
        def authenticate(self, request):
            return None

    app = FastAPI()
    app.include_router(
        build_router(store_factory=store_factory, principal_adapter=_NoneAdapter())
    )
    c = TestClient(app)
    resp = c.get("/api/v2/brain/events")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_post_event_records_and_lists(client: TestClient) -> None:
    payload = _event_payload()
    resp = client.post("/api/v2/brain/events", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "recorded"

    listed = client.get("/api/v2/brain/events")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["id"] == payload["id"]
    assert items[0]["principal_actor"] == "alice"
    assert items[0]["principal_workspace"] == "ws-team"
    assert items[0]["principal_project"] == "brain"


def test_post_event_idempotent_same_payload(client: TestClient) -> None:
    payload = _event_payload()
    first = client.post("/api/v2/brain/events", json=payload)
    assert first.status_code == 200
    assert first.json()["status"] == "recorded"

    second = client.post("/api/v2/brain/events", json=payload)
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"  # idempotent ack

    listed = client.get("/api/v2/brain/events").json()
    # Idempotency: only one row at version=1.
    versions = [item["version"] for item in listed]
    assert versions == [1]


def test_get_event_reads_exact_version(client: TestClient) -> None:
    payload = _event_payload()
    created = client.post("/api/v2/brain/events", json=payload)
    assert created.status_code == 200
    got = client.get(f"/api/v2/brain/events/{payload['id']}", params={"version": 1})
    assert got.status_code == 200
    assert got.json()["id"] == payload["id"]
    assert got.json()["version"] == 1


def test_event_ack_returns_client_digest_when_supplied(client: TestClient) -> None:
    payload = _event_payload()
    payload["client_digest"] = "d" * 64
    created = client.post("/api/v2/brain/events", json=payload)
    assert created.status_code == 200, created.text
    ack = client.get(
        f"/api/v2/brain/events/{payload['id']}/ack",
        params={"version": 1},
    )
    assert ack.status_code == 200
    assert ack.json() == {
        "status": "accepted",
        "authorized": True,
        "id": payload["id"],
        "version": 1,
        "digest": "d" * 64,
    }


def test_event_ack_absent_is_authorized_exact_absence(client: TestClient) -> None:
    identity = str(uuid4())
    ack = client.get(f"/api/v2/brain/events/{identity}/ack", params={"version": 1})
    assert ack.status_code == 200
    assert ack.json()["status"] == "absent"
    assert ack.json()["authorized"] is True
    assert ack.json()["id"] == identity


def test_get_event_out_of_scope_or_absent_is_404(client: TestClient) -> None:
    got = client.get(f"/api/v2/brain/events/{uuid4()}", params={"version": 1})
    assert got.status_code == 404


def test_post_event_rejects_origin_or_classification_in_body(client: TestClient) -> None:
    payload = _event_payload()
    payload["origin"] = "wrapper"          # server-owned, must be rejected
    payload["classification"] = "probe"    # server-owned, must be rejected
    resp = client.post("/api/v2/brain/events", json=payload)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    fields = {tuple(err["loc"]) for err in detail}
    assert any("origin" in f for f in fields), detail
    assert any("classification" in f for f in fields), detail


def test_post_event_rejects_principal_in_body(client: TestClient) -> None:
    payload = _event_payload()
    payload["principal_actor"] = "mallory"
    payload["principal_workspace"] = "other"
    payload["principal_project"] = "other"
    resp = client.post("/api/v2/brain/events", json=payload)
    assert resp.status_code == 422


def test_post_event_rejects_naive_datetime(client: TestClient) -> None:
    payload = _event_payload(occurred_at="2026-09-17T08:00:00")
    resp = client.post("/api/v2/brain/events", json=payload)
    assert resp.status_code == 422


def test_post_event_rejects_string_coercion(client: TestClient) -> None:
    payload = _event_payload()
    payload["agent_id"] = 7
    resp = client.post("/api/v2/brain/events", json=payload)
    assert resp.status_code == 422


def test_post_event_environment_operation_requires_target(client: TestClient) -> None:
    payload = _event_payload(action="systemctl restart service", target_id=None)
    resp = client.post("/api/v2/brain/events", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Cross-workspace / cross-project guards
# ---------------------------------------------------------------------------


def test_cross_project_event_rejected(client: TestClient) -> None:
    payload = _event_payload(project_id="other-project")
    resp = client.post("/api/v2/brain/events", json=payload)
    assert resp.status_code == 403
    assert "cross-project" in resp.json()["detail"].lower()


def test_cross_workspace_event_store_is_invisible(tmp_path: Path) -> None:
    """A principal in workspace ws-team cannot see rows in ws-other."""

    db = tmp_path / "v2.sqlite3"

    # Seed rows under ws-other via direct EventStore use.
    seed_adapter = StaticPrincipalAdapter(
        actor="bob", workspace="ws-other", project="brain"
    )
    seed_store = EventStore(str(db), principal=seed_adapter)
    seed_store.record_event(
        id=uuid4(),
        project_id="brain",
        agent_id="agent-x",
        occurred_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
        action="do thing",
        result="ok",
    )
    seed_store.close()

    # Wire the same DB but with a ws-team principal. The factory must
    # accept the server-resolved Principal and bind it through an adapter.
    def _factory(principal: Principal) -> EventStore:
        return EventStore(str(db), principal=_PrincipalAdapter(principal))

    app = FastAPI()
    app.include_router(
        build_router(
            store_factory=_factory,
            principal_adapter=_FixedAdapter(actor="alice", workspace="ws-team", project="brain"),
        )
    )
    c = TestClient(app)

    # POST: principal project matches, but we craft a body that references
    # the other workspace via project_id mismatch to exercise the 403 path.
    resp = c.post(
        "/api/v2/brain/events",
        json=_event_payload(project_id="ws-other"),
    )
    assert resp.status_code == 403

    # GET: the seeded event MUST NOT be visible to the ws-team principal.
    resp = c.get("/api/v2/brain/events")
    assert resp.status_code == 200
    assert resp.json() == []


def test_cross_workspace_proposal_get_returns_404(tmp_path: Path) -> None:
    """Out-of-scope proposal lookups collapse to 404 (no enumeration)."""

    db = tmp_path / "v2.sqlite3"
    pid = uuid4()
    seed = StaticPrincipalAdapter(
        actor="bob", workspace="ws-other", project="brain"
    )
    s = EventStore(str(db), principal=seed)
    s.create_proposal(
        id=pid,
        project_id="brain",
        agent_id="agent-x",
        occurred_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
        draft=True,
    )
    s.close()

    def _factory(principal: Principal) -> EventStore:
        return EventStore(str(db), principal=_PrincipalAdapter(principal))

    app = FastAPI()
    app.include_router(
        build_router(
            store_factory=_factory,
            principal_adapter=_FixedAdapter(actor="alice", workspace="ws-team", project="brain"),
        )
    )
    c = TestClient(app)

    resp = c.get(f"/api/v2/brain/proposals/{pid}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Proposals: create / CAS update / idempotency
# ---------------------------------------------------------------------------


def test_create_proposal_draft_happy_path(client: TestClient) -> None:
    payload = _proposal_payload(draft=True)
    resp = client.post("/api/v2/brain/proposals", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "created"
    assert body["version"] == 1
    assert body["workflow_state"] == "draft"

    got = client.get(f"/api/v2/brain/proposals/{payload['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == payload["id"]


def test_create_proposal_ready_requires_evidence(client: TestClient) -> None:
    """Ready proposal without source_refs must be rejected by the contract."""

    payload = _proposal_payload(draft=False, source_refs=[])
    resp = client.post("/api/v2/brain/proposals", json=payload)
    assert resp.status_code == 422
    assert "source_refs" in resp.text


def test_create_proposal_ready_requires_project_and_all_facts(client: TestClient) -> None:
    payload = _proposal_payload(
        project_id=None,
        draft=False,
        action=None,
        result=None,
        lesson=None,
        source_refs=[{"type": "execution", "id": str(uuid4())}],
    )
    resp = client.post("/api/v2/brain/proposals", json=payload)
    assert resp.status_code == 422
    assert "project_id" in resp.text


def test_create_proposal_idempotent_same_payload(client: TestClient) -> None:
    payload = _proposal_payload(draft=True)
    first = client.post("/api/v2/brain/proposals", json=payload)
    assert first.status_code == 200
    second = client.post("/api/v2/brain/proposals", json=payload)
    assert second.status_code == 200
    assert second.json()["status"] in ("duplicate", "created")


def test_create_proposal_rejects_workflow_state_in_body(client: TestClient) -> None:
    payload = _proposal_payload(draft=True)
    payload["workflow_state"] = "ready"
    resp = client.post("/api/v2/brain/proposals", json=payload)
    assert resp.status_code == 422


def test_update_proposal_cas_happy_path(client: TestClient) -> None:
    payload = _proposal_payload(draft=True)
    created = client.post("/api/v2/brain/proposals", json=payload)
    assert created.status_code == 200

    resp = client.put(
        f"/api/v2/brain/proposals/{payload['id']}",
        json={"expected_version": 1, "lesson": "new lesson text"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "updated"
    assert body["version"] == 2


def test_update_proposal_stale_version_returns_409(client: TestClient) -> None:
    payload = _proposal_payload(draft=True)
    created = client.post("/api/v2/brain/proposals", json=payload)
    assert created.status_code == 200

    # Bump once to v2.
    client.put(
        f"/api/v2/brain/proposals/{payload['id']}",
        json={"expected_version": 1, "lesson": "lesson v2"},
    )

    # Now try CAS with the OLD version -> must 409.
    stale = client.put(
        f"/api/v2/brain/proposals/{payload['id']}",
        json={"expected_version": 1, "lesson": "lesson v3"},
    )
    assert stale.status_code == 409


def test_update_unknown_proposal_returns_404(client: TestClient) -> None:
    resp = client.put(
        f"/api/v2/brain/proposals/{uuid4()}",
        json={"expected_version": 1, "lesson": "x"},
    )
    assert resp.status_code == 404


def test_update_proposal_rejects_draft_promotion(client: TestClient) -> None:
    """Drafts cannot be promoted via update_proposal (server-side rule)."""

    payload = _proposal_payload(draft=True)
    created = client.post("/api/v2/brain/proposals", json=payload)
    assert created.status_code == 200

    # Send extra fields -> must be rejected by extra=forbid.
    bad = {
        "expected_version": 1,
        "lesson": "x",
        "draft": False,
        "workflow_state": "ready",
    }
    resp = client.put(f"/api/v2/brain/proposals/{payload['id']}", json=bad)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Body-size enforcement (before parse)
# ---------------------------------------------------------------------------


def test_oversized_body_rejected_with_413(client: TestClient) -> None:
    """A payload over MAX_BODY_BYTES is rejected with 413 before Pydantic."""

    huge = "x" * (MAX_BODY_BYTES + 1024)
    payload = _event_payload(action=huge, result="ok")
    resp = client.post("/api/v2/brain/events", json=payload)
    assert resp.status_code == 413


def test_oversized_body_via_content_length_header(store_factory, db_path) -> None:
    """The Content-Length pre-screen also fires."""

    app = FastAPI()
    app.include_router(
        build_router(
            store_factory=store_factory,
            principal_adapter=_FixedAdapter(actor="alice", workspace="ws-team", project="brain"),
        )
    )
    c = TestClient(app)
    big = b'{"id":"' + (b"x" * (MAX_BODY_BYTES + 16)) + b'"}'
    resp = c.post(
        "/api/v2/brain/events",
        content=big,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Privacy gate never leaks the matched substring
# ---------------------------------------------------------------------------


def test_sensitive_payload_rejected_without_leak(client: TestClient) -> None:
    payload = _event_payload(action="rotate api_key=supersecretvalue123")
    resp = client.post("/api/v2/brain/events", json=payload)
    assert resp.status_code == 422
    detail_text = json.dumps(resp.json())
    # The matched substring MUST NOT appear in the response.
    assert "supersecretvalue123" not in detail_text
    assert "supersecretvalue123" not in resp.text


def test_bearer_token_in_payload_rejected(client: TestClient) -> None:
    payload = _event_payload(
        result="token bearer abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG",
    )
    resp = client.post("/api/v2/brain/events", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Source refs: ready proposal must reference an execution or document in scope
# ---------------------------------------------------------------------------


def _register_doc(store_factory, *, doc_id, version=1) -> None:
    store = store_factory()
    try:
        store.register_source_document(
            doc_id=doc_id,
            url="https://example.invalid/spec",
            version=version,
            excerpt="spec",
        )
    finally:
        store.close()


def test_ready_proposal_with_document_source_ref_succeeds(store_factory) -> None:
    doc_id = uuid4()
    _register_doc(store_factory, doc_id=doc_id)

    adapter = _FixedAdapter(actor="alice", workspace="ws-team", project="brain")
    app = FastAPI()
    app.include_router(
        build_router(store_factory=store_factory, principal_adapter=adapter)
    )
    c = TestClient(app)

    payload = _proposal_payload(
        draft=False,
        source_refs=[{"type": "document", "id": str(doc_id)}],
    )
    resp = c.post("/api/v2/brain/proposals", json=payload)
    assert resp.status_code == 200, resp.text


def test_ready_proposal_with_unknown_source_ref_returns_409(client: TestClient) -> None:
    payload = _proposal_payload(
        draft=False,
        source_refs=[{"type": "execution", "id": str(uuid4())}],
    )
    resp = client.post("/api/v2/brain/proposals", json=payload)
    assert resp.status_code == 409