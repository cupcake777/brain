from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig, build_config
from hermes.event_store import EventStore, Principal, StaticPrincipalAdapter
from hermes.knowledge_extraction import ExtractionQueue
from hermes.knowledge_sources import RegisteredSources
from hermes.knowledge_store import KnowledgeStore
from hermes.repository import HermesRepository


def _v2_config(tmp_path, *, enabled=True, complete_principal=True):
    values = dict(
        sync_root=tmp_path,
        db_path=tmp_path / "brain.sqlite3",
        auth_token="test-token",
        brain_v2_enabled=enabled,
    )
    if complete_principal:
        values.update(
            brain_v2_actor="agent-a",
            brain_v2_workspace="workspace-a",
            brain_v2_project="brain",
        )
    return HermesConfig(**values)


def _event_payload(identity):
    return {
        "id": identity,
        "project_id": "brain",
        "agent_id": "agent-a",
        "occurred_at": datetime(2026, 9, 20, tzinfo=timezone.utc).isoformat(),
        "target_id": None,
        "action": "verify staged v2 router",
        "result": "passed",
        "source_refs": [],
    }


def test_v2_router_is_absent_by_default(tmp_path):
    config = _v2_config(tmp_path, enabled=False)
    app = create_app(
        repo=HermesRepository(config.db_path),
        sync_root=tmp_path,
        config=config,
    )
    response = TestClient(app).get(
        "/api/v2/brain/events",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 404


def test_v2_router_enabled_without_complete_principal_fails_closed(tmp_path):
    config = _v2_config(tmp_path, enabled=True, complete_principal=False)
    app = create_app(
        repo=HermesRepository(config.db_path),
        sync_root=tmp_path,
        config=config,
    )
    response = TestClient(app).get(
        "/api/v2/brain/events",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "principal unavailable"


def test_v2_router_enabled_uses_server_principal_and_exact_receipt(tmp_path):
    config = _v2_config(tmp_path)
    app = create_app(
        repo=HermesRepository(config.db_path),
        sync_root=tmp_path,
        config=config,
    )
    client = TestClient(app)
    identity = str(uuid4())
    headers = {"Authorization": "Bearer test-token"}
    first = client.post(
        "/api/v2/brain/events",
        json=_event_payload(identity),
        headers=headers,
    )
    assert first.status_code == 200, first.text
    receipt = first.json()
    assert receipt["status"] == "recorded"
    assert receipt["id"] == identity
    assert receipt["version"] == 1
    assert len(receipt["digest"]) == 64

    duplicate = client.post(
        "/api/v2/brain/events",
        json=_event_payload(identity),
        headers=headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == identity
    assert duplicate.json()["version"] == 1
    assert duplicate.json()["digest"] == receipt["digest"]


def test_build_config_reads_v2_gate_and_principal(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAIN_V2_ENABLED", "true")
    monkeypatch.setenv("BRAIN_V2_ACTOR", "agent-a")
    monkeypatch.setenv("BRAIN_V2_WORKSPACE", "workspace-a")
    monkeypatch.setenv("BRAIN_V2_PROJECT", "brain")
    config = build_config(tmp_path)
    assert config.brain_v2_enabled is True
    assert (config.brain_v2_actor, config.brain_v2_workspace, config.brain_v2_project) == (
        "agent-a",
        "workspace-a",
        "brain",
    )


def test_registered_sources_resolve_current_event_version(tmp_path):
    principal = Principal("agent-a", "workspace-a", "brain")
    adapter = StaticPrincipalAdapter(
        actor=principal.actor,
        workspace=principal.workspace,
        project=principal.project,
    )
    events = EventStore(tmp_path / "events.sqlite3", principal=adapter)
    identity = str(uuid4())
    occurred_at = datetime(2026, 9, 20, tzinfo=timezone.utc)
    events.record_event(
        id=identity,
        project_id="brain",
        agent_id="agent-a",
        occurred_at=occurred_at,
        action="first",
        result="unknown",
    )
    events.record_event(
        id=identity,
        project_id="brain",
        agent_id="agent-a",
        occurred_at=occurred_at,
        action="second",
        result="verified",
        expected_version=1,
    )
    versions = RegisteredSources(events)(
        principal,
        [{"type": "execution", "id": identity}],
    )
    assert versions == {identity: 2}
    events.close()


def test_extraction_rejects_hallucinated_source_and_retains_job(tmp_path):
    principal = Principal("agent-a", "workspace-a", "brain")
    event_id = str(uuid4())
    fake_event = {
        "id": event_id,
        "project_id": "brain",
        "action": "test",
        "result": "passed",
    }
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    queue = ExtractionQueue(store, event_reader=lambda _p, _i: fake_event)
    queue.enqueue(principal, event_id)
    result = queue.run_once(
        principal,
        lambda _event: [
            {
                "content": "do not trust invented sources",
                "source_refs": [
                    {"type": "execution", "id": str(uuid4())},
                ],
            }
        ],
    )
    assert result["state"] == "pending"
    assert store.list_current(principal) == []
    store.close()
