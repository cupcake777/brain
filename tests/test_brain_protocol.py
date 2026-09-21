from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.integrate import integrate
from hermes.repository import HermesRepository


def client_with_token(tmp_path: Path) -> tuple[TestClient, HermesRepository, Path]:
    sync_root = tmp_path / "sync"
    config = HermesConfig(sync_root=sync_root, db_path=tmp_path / "hermes.sqlite3", auth_token="test-token")
    repo = HermesRepository(config.db_path)
    app = create_app(repo=repo, sync_root=sync_root, config=config)
    return TestClient(app), repo, sync_root


def test_protocol_health_and_public_retrieve(tmp_path: Path) -> None:
    client, repo, _ = client_with_token(tmp_path)
    result = integrate(
        content="Before changing a provider configuration, inspect the live config and logs.",
        source="test",
        category="rule",
        domain="tech",
        evidence=["test://retrieve: inspect config first"],
        repo=repo,
    )
    repo.update_knowledge_node(result.node_id, stage="verified")

    health = client.get("/api/v1/brain/health")
    assert health.status_code == 200
    assert health.json()["schema"] == 1

    response = client.post("/api/v1/brain/retrieve", json={"query": "provider config logs", "agent": "clean-agent", "host_hash": "host-a"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_id"]
    assert payload["outcome_required"] is True
    assert any(item["node_id"] == result.node_id for item in payload["results"])


def test_protocol_outcome_is_bound_to_retrieval(tmp_path: Path) -> None:
    client, repo, _ = client_with_token(tmp_path)
    result = integrate(
        content="Use an atomic temporary file and rename when replacing generated configuration.",
        source="test",
        category="workflow_hint",
        domain="tech",
        evidence=["test://outcome: atomic rename"],
        repo=repo,
    )
    repo.update_knowledge_node(result.node_id, stage="verified")
    retrieval = client.post("/api/v1/brain/retrieve", json={"query": "atomic generated configuration"}).json()

    unauthenticated = client.post("/api/v1/brain/outcome", json={"retrieval_id": retrieval["retrieval_id"], "node_id": result.node_id, "status": "applied"})
    assert unauthenticated.status_code == 401

    response = client.post(
        "/api/v1/brain/outcome",
        headers={"Authorization": "Bearer test-token"},
        json={"retrieval_id": retrieval["retrieval_id"], "node_id": result.node_id, "status": "applied", "task_success": "success"},
    )
    assert response.status_code == 200
    assert response.json()["recorded"] == 1
    stored = repo.get_knowledge_node(result.node_id)
    assert stored is not None
    assert stored.outcome_count == 1

    wrong = client.post(
        "/api/v1/brain/outcome",
        headers={"Authorization": "Bearer test-token"},
        json={"retrieval_id": retrieval["retrieval_id"], "node_id": "not-a-candidate", "status": "applied"},
    )
    assert wrong.status_code == 400


def test_protocol_proposal_requires_evidence_and_queues_file(tmp_path: Path) -> None:
    client, _, sync_root = client_with_token(tmp_path)
    headers = {"Authorization": "Bearer test-token"}
    base = {
        "summary": "Preserve exact identifiers during lookup",
        "observation": "A malformed identifier was silently normalized and targeted the wrong record.",
        "why_it_matters": "The error can mutate unrelated state.",
        "suggested_memory": "Validate identifiers before lookup and preserve their literal value.",
        "category": "rule",
        "risk_level": "high",
    }
    rejected = client.post("/api/v1/brain/propose", headers=headers, json=base)
    assert rejected.status_code == 400

    response = client.post(
        "/api/v1/brain/propose",
        headers=headers,
        json=base | {"evidence": [{"source_type": "test", "source_uri": "test://proposal", "quoted_excerpt": "wrong record"}]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "submitted"
    proposal_path = sync_root / "inbox" / "proposals" / f"{payload['proposal_id']}.md"
    assert proposal_path.is_file()
    assert "Preserve exact identifiers" in proposal_path.read_text(encoding="utf-8")


def test_skill_package_is_public_and_references_support_files(tmp_path: Path) -> None:
    client, _, _ = client_with_token(tmp_path)
    skill = client.get("/skills/brain-loop/SKILL.md")
    assert skill.status_code == 200
    assert "scripts/brain.py" in skill.text
    script = client.get("/skills/brain-loop/scripts/brain.py")
    assert script.status_code == 200
    assert "api/v1/brain/retrieve" in script.text
