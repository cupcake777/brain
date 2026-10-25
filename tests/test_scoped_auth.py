from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.repository import HermesRepository
from hermes.scoped_auth import ScopedPrincipalRegistry


def _registry(path, token="agent-token", *, projects=None, permissions=None):
    payload = {
        "version": 1,
        "tokens": [
            {
                "name": "codex",
                "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                "actor": "codex",
                "workspace": "personal",
                "projects": projects or ["brain", "paper"],
                "default_project": "brain",
                "permissions": permissions
                or ["events:write", "events:read", "proposals:write", "proposals:read"],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    return path


def _app(tmp_path, registry_path):
    config = HermesConfig(
        sync_root=tmp_path,
        db_path=tmp_path / "brain.sqlite3",
        auth_token="admin-token",
        brain_v2_enabled=True,
        brain_scoped_tokens_file=str(registry_path),
    )
    repo = HermesRepository(config.db_path)
    return create_app(repo=repo, sync_root=tmp_path, config=config)


def _event(project="brain"):
    return {
        "id": str(uuid4()),
        "project_id": project,
        "agent_id": "claimed-agent",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "target_id": None,
        "action": "run verified fixture",
        "result": "passed",
        "source_refs": [],
    }


def test_scoped_token_binds_actor_workspace_and_header_project(tmp_path):
    app = _app(tmp_path, _registry(tmp_path / "tokens.json"))
    client = TestClient(app)
    headers = {
        "Authorization": "Bearer agent-token",
        "X-Brain-Project": "paper",
    }
    payload = _event(project="paper")
    created = client.post("/api/v2/brain/events", json=payload, headers=headers)
    assert created.status_code == 200, created.text
    listed = client.get("/api/v2/brain/events", headers=headers)
    assert listed.status_code == 200
    row = listed.json()[0]
    assert row["principal_actor"] == "codex"
    assert row["principal_workspace"] == "personal"
    assert row["principal_project"] == "paper"
    assert row["agent_id"] == "claimed-agent"


def test_scoped_token_cannot_escape_allowed_projects(tmp_path):
    app = _app(tmp_path, _registry(tmp_path / "tokens.json", projects=["brain"]))
    response = TestClient(app).post(
        "/api/v2/brain/events",
        json=_event(project="secret-project"),
        headers={
            "Authorization": "Bearer agent-token",
            "X-Brain-Project": "secret-project",
        },
    )
    assert response.status_code == 503


def test_scoped_read_only_token_cannot_write(tmp_path):
    app = _app(
        tmp_path,
        _registry(tmp_path / "tokens.json", permissions=["events:read"]),
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer agent-token"}
    assert client.get("/api/v2/brain/events", headers=headers).status_code == 200
    assert client.post("/api/v2/brain/events", json=_event(), headers=headers).status_code == 401


def test_scoped_knowledge_read_can_retrieve_experience(tmp_path):
    app = _app(
        tmp_path,
        _registry(tmp_path / "tokens.json", permissions=["knowledge:read"]),
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer agent-token"}
    denied = TestClient(
        _app(tmp_path, _registry(tmp_path / "events.json", permissions=["events:read"]))
    )
    assert denied.post(
        "/api/v1/brain/retrieve",
        json={"query": "provider configuration"},
        headers=headers,
    ).status_code == 401

    from hermes.repository import HermesRepository, KnowledgeNode

    repo = HermesRepository(tmp_path / "brain.sqlite3")
    repo.insert_knowledge_node(KnowledgeNode(
        id="node-1",
        parent_id=None,
        content="Inspect the live provider configuration before changing it.",
        summary="Inspect provider configuration before changing it.",
        category="rule",
        domain="tech",
        stage="canonized",
        operation="canonize",
        confidence=0.9,
        source="test",
        evidence="[]",
        supersedes=None,
        merged_from="[]",
        contradicts="[]",
        verified_by="[]",
        created_at="2026-10-18T00:00:00+00:00",
        refined_at=None,
        verified_at=None,
        deprecated_at=None,
        retrieval_count=0,
        last_used_at=None,
        correction_count=0,
        outcome_count=0,
        last_outcome_at=None,
        kind="rule",
        trigger_terms="[]",
        use_when="",
        avoid_when="",
        success_signal="",
        failure_signal="",
    ))
    response = client.post(
        "/api/v1/brain/retrieve",
        json={"query": "provider configuration"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert any(item["node_id"] == "node-1" for item in response.json()["results"])


def test_registry_reloads_after_atomic_rotation(tmp_path):
    path = _registry(tmp_path / "tokens.json", token="old-token")
    registry = ScopedPrincipalRegistry(path)
    class OldRequest:
        headers = {"authorization": "Bearer old-token"}
        class URL:
            path = "/api/v2/brain/events"
        url = URL()
        method = "GET"
    assert registry.record_for_request(OldRequest()) is not None

    payload = json.loads(path.read_text())
    payload["tokens"][0]["token_sha256"] = hashlib.sha256(b"new-token").hexdigest()
    replacement = path.with_suffix(".new")
    replacement.write_text(json.dumps(payload), encoding="utf-8")
    replacement.replace(path)

    app = _app(tmp_path, path)
    client = TestClient(app)
    assert client.get(
        "/api/v2/brain/events", headers={"Authorization": "Bearer new-token"}
    ).status_code == 200
    assert client.get(
        "/api/v2/brain/events", headers={"Authorization": "Bearer old-token"}
    ).status_code == 401


def test_transition_requires_review_permission(tmp_path):
    path = _registry(
        tmp_path / "tokens.json",
        permissions=["proposals:write", "proposals:read"],
    )
    registry = ScopedPrincipalRegistry(path)

    class TransitionRequest:
        headers = {"authorization": "Bearer agent-token"}
        class URL:
            path = "/api/v2/brain/proposals/proposal-1/transition"
        url = URL()
        method = "POST"

    assert registry.authorize_http(TransitionRequest()) is False

    payload = json.loads(path.read_text())
    payload["tokens"][0]["permissions"].append("proposals:review")
    path.write_text(json.dumps(payload))
    assert registry.authorize_http(TransitionRequest()) is True
