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


def test_protocol_health_and_retrieve_require_auth(tmp_path: Path) -> None:
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

    assert client.get("/api/v1/brain/health").status_code == 401
    health = client.get(
        "/api/v1/brain/health",
        headers={"Authorization": "Bearer test-token"},
    )
    assert health.status_code == 200
    assert health.json()["schema"] == 1

    assert client.post("/api/v1/brain/retrieve", json={"query": "provider config logs"}).status_code == 401
    response = client.post(
        "/api/v1/brain/retrieve",
        headers={"Authorization": "Bearer test-token"},
        json={"query": "provider config logs", "agent": "clean-agent", "host_hash": "host-a"},
    )
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
    retrieval = client.post(
        "/api/v1/brain/retrieve",
        headers={"Authorization": "Bearer test-token"},
        json={"query": "atomic generated configuration"},
    ).json()

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
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    proposal_path = sync_root / "inbox" / "proposals" / f"{payload['proposal_id']}.md"
    assert proposal_path.is_file()
    assert "Preserve exact identifiers" in proposal_path.read_text(encoding="utf-8")

    queued = client.get(
        f"/api/v1/brain/proposals/{payload['proposal_id']}",
        headers=headers,
    )
    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"


def test_protocol_proposal_status_tracks_ingestion_and_link(tmp_path: Path) -> None:
    client, repo, sync_root = client_with_token(tmp_path)
    headers = {"Authorization": "Bearer test-token"}
    response = client.post(
        "/api/v1/brain/propose",
        headers=headers,
        json={
            "summary": "Track proposal status after durable ingestion",
            "observation": "Transport acknowledgement is distinct from database ingestion.",
            "why_it_matters": "Clients need a durable state before reporting success.",
            "suggested_memory": "Wait for ingested_pending, approved, linked, duplicate, or rejected.",
            "category": "workflow_hint",
            "risk_level": "low",
            "evidence": [{"source_type": "test", "source_uri": "test://status", "quoted_excerpt": "proposal status test"}],
        },
    )
    proposal_id = response.json()["proposal_id"]

    from hermes.runtime import HermesRuntime
    runtime = HermesRuntime(
        config=HermesConfig(sync_root=sync_root, db_path=tmp_path / "hermes.sqlite3", auth_token="test-token"),
        repo=repo,
    )
    assert runtime.run_scan_cycle().ingested_count == 1

    ingested = client.get(f"/api/v1/brain/proposals/{proposal_id}", headers=headers)
    assert ingested.status_code == 200
    assert ingested.json()["status"] == "ingested_pending"

    repo.transition_state(proposal_id, "approved_db_only")
    runtime.run_knowledge_pipeline(backfill_embeddings=False)
    linked = client.get(f"/api/v1/brain/proposals/{proposal_id}", headers=headers)
    assert linked.json()["status"] == "linked"
    assert linked.json()["knowledge_id"]


def test_protocol_proposal_rejects_unstructured_evidence_entry(tmp_path: Path) -> None:
    client, _, _ = client_with_token(tmp_path)
    response = client.post(
        "/api/v1/brain/propose",
        headers={"Authorization": "Bearer test-token"},
        json={
            "summary": "Reject malformed proposal evidence",
            "observation": "A nonempty evidence list can still lack provenance.",
            "why_it_matters": "Malformed evidence cannot support durable knowledge.",
            "suggested_memory": "Require source_type and source_uri for every proposal.",
            "evidence": [{"note": "missing provenance"}],
        },
    )

    assert response.status_code == 422


def test_skill_package_requires_auth_and_references_support_files(tmp_path: Path) -> None:
    client, _, _ = client_with_token(tmp_path)
    assert client.get("/skills/brain-loop/SKILL.md").status_code == 401
    headers = {"Authorization": "Bearer test-token"}
    skill = client.get("/skills/brain-loop/SKILL.md", headers=headers)
    assert skill.status_code == 200
    assert "scripts/brain.py" in skill.text
    script = client.get("/skills/brain-loop/scripts/brain.py", headers=headers)
    assert script.status_code == 200
    assert "api/v1/brain/retrieve" in script.text
