from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.event_store import EventStore, StaticPrincipalAdapter
from hermes.repository import HermesRepository
from hermes.runtime import HermesRuntime
from hermes.scoped_auth import ScopedPrincipalRegistry


def _seed(tmp_path):
    config = HermesConfig(
        sync_root=tmp_path / "sync",
        db_path=tmp_path / "brain.sqlite3",
        brain_v2_enabled=True,
        brain_v2_actor="reviewer",
        brain_v2_workspace="ws-1",
        brain_v2_project="brain",
    )
    principal = StaticPrincipalAdapter(
        actor="reviewer", workspace="ws-1", project="brain"
    )
    store = EventStore(config.db_path, principal=principal)
    event_id = uuid4()
    proposal_id = uuid4()
    store.record_event(
        id=event_id,
        project_id="brain",
        agent_id="agent-1",
        occurred_at=datetime(2026, 10, 25, tzinfo=timezone.utc),
        action="verify workflow",
        result="completed",
    )
    store.create_proposal(
        id=proposal_id,
        project_id="brain",
        agent_id="agent-1",
        occurred_at=datetime(2026, 10, 25, tzinfo=timezone.utc),
        action="verify workflow",
        result="completed",
        lesson="Run the verification before changing production configuration.",
        draft=True,
        source_refs=[{"type": "execution", "id": str(event_id)}],
    )
    store.close()
    app = create_app(
        repo=HermesRepository(config.db_path),
        sync_root=config.sync_root,
        config=config,
    )
    return config, proposal_id, TestClient(app)


def test_v2_proposal_queue_and_detail_are_reviewable(tmp_path) -> None:
    _config, proposal_id, client = _seed(tmp_path)

    queue = client.get("/v2-proposals")
    assert queue.status_code == 200
    assert str(proposal_id) in queue.text
    assert "draft" in queue.text

    detail = client.get(f"/v2-proposals/{proposal_id}")
    assert detail.status_code == 200
    assert "Run the verification" in detail.text
    assert "to_state" in detail.text
    assert "ready" in detail.text


def test_existing_proposals_entry_opens_v2_review_queue(tmp_path) -> None:
    _config, proposal_id, client = _seed(tmp_path)

    queue = client.get("/proposals")
    assert queue.status_code == 200
    assert str(proposal_id) in queue.text
    assert f"/proposals/{proposal_id}" in queue.text
    assert "Proposal review" in queue.text

    detail = client.get(f"/proposals/{proposal_id}")
    assert detail.status_code == 200
    assert "Run the verification" in detail.text
    assert "Mark ready" in detail.text


def test_v2_proposal_ui_uses_cas_transition_api(tmp_path) -> None:
    _config, proposal_id, client = _seed(tmp_path)

    response = client.post(
        f"/api/v2/brain/proposals/{proposal_id}/transition",
        json={"expected_version": 1, "to_state": "ready", "note": "checked"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["workflow_state"] == "ready"


def test_browser_session_can_review_scoped_v2_proposal(tmp_path) -> None:
    registry_path = tmp_path / "tokens.json"
    registry_path.write_text(
        json.dumps(
            {
                "version": 1,
                "tokens": [
                    {
                        "name": "agent",
                        "token_sha256": ScopedPrincipalRegistry.token_digest("agent-token"),
                        "actor": "agent",
                        "workspace": "personal",
                        "projects": ["general"],
                        "default_project": "general",
                        "permissions": ["proposals:read", "proposals:write"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config = HermesConfig(
        sync_root=tmp_path / "sync",
        db_path=tmp_path / "brain.sqlite3",
        auth_token="owner-token",
        brain_v2_enabled=True,
        brain_v2_actor="owner-reviewer",
        brain_v2_workspace="personal",
        brain_v2_project="general",
        brain_scoped_tokens_file=str(registry_path),
    )
    principal = StaticPrincipalAdapter(actor="agent", workspace="personal", project="general")
    store = EventStore(config.db_path, principal=principal)
    event_id = uuid4()
    proposal_id = uuid4()
    store.record_event(
        id=event_id,
        project_id="general",
        agent_id="agent",
        occurred_at=datetime(2026, 10, 25, tzinfo=timezone.utc),
        action="review browser auth",
        result="completed",
    )
    store.create_proposal(
        id=proposal_id,
        project_id="general",
        agent_id="agent",
        occurred_at=datetime(2026, 10, 25, tzinfo=timezone.utc),
        action="review browser auth",
        result="completed",
        lesson="Owner can review this proposal in the browser.",
        draft=True,
        source_refs=[{"type": "execution", "id": str(event_id)}],
    )
    store.close()
    repo = HermesRepository(config.db_path)
    repo.insert_proposal(
        {
            "proposal_id": "existing-pending-proposal",
            "source_agent": "agent",
            "source_host": "test",
            "created_at": datetime(2026, 10, 25, tzinfo=timezone.utc).isoformat(),
            "project_key": "general",
            "category": "rule",
            "risk_level": "low",
            "domain": "general",
            "summary": "Existing proposal remains reviewable",
            "observation": "Existing proposal record",
            "why_it_matters": "It must not disappear from the unified queue.",
            "suggested_memory": "Keep existing pending proposals visible.",
            "scope": "global",
            "evidence": "[]",
            "state": "pending",
            "semantic_hash": "existing-pending-hash",
        }
    )
    client = TestClient(
        create_app(
            repo=repo,
            sync_root=config.sync_root,
            config=config,
        )
    )
    login = client.post(
        "/login",
        data={"username": "owner", "password": "owner-token"},
        headers={"Origin": "http://testserver"},
    )
    assert login.status_code == 200

    queue = client.get("/proposals")
    assert queue.status_code == 200
    assert str(proposal_id) in queue.text
    assert "existing-pending-proposal" in queue.text
    assert "Existing proposal remains reviewable" in queue.text

    transitioned = client.post(
        f"/api/review/v2/{proposal_id}/transition",
        json={"expected_version": 1, "to_state": "ready", "note": "checked"},
        headers={"Origin": "http://testserver"},
    )
    assert transitioned.status_code == 200, transitioned.text
    assert transitioned.json()["workflow_state"] == "ready"

    accepted = client.post(
        f"/api/review/v2/{proposal_id}/transition",
        json={"expected_version": 2, "to_state": "accepted", "note": "approved"},
        headers={"Origin": "http://testserver"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["workflow_state"] == "accepted"

    result = HermesRuntime(config=config).run_knowledge_intake_cycle()
    assert result == {"status": "ok", "processed": 1, "done": 1, "failed": 0}
    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM proposal_knowledge_intake WHERE proposal_id = ?",
            (str(proposal_id),),
        ).fetchone()[0] == 1