from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.integrate import integrate
from hermes.repository import HermesRepository
from hermes.runtime import HermesRuntime


def test_retrieve_outcome_propose_review_link_retrieve_loop(tmp_path: Path) -> None:
    sync_root = tmp_path / "sync"
    config = HermesConfig(
        sync_root=sync_root,
        db_path=tmp_path / "hermes.sqlite3",
        auth_token="test-token",
    )
    repo = HermesRepository(config.db_path)
    runtime = HermesRuntime(config=config, repo=repo)
    client = TestClient(create_app(repo=repo, sync_root=sync_root, config=config))
    auth = {"Authorization": "Bearer test-token"}

    seed = integrate(
        content="Inspect live configuration and logs before changing a provider.",
        source="test-seed",
        category="rule",
        domain="tech",
        evidence=["test://closed-loop/seed"],
        repo=repo,
    )
    repo.update_knowledge_node(seed.node_id, stage="verified")

    retrieval = client.post(
        "/api/v1/brain/retrieve",
        headers=auth,
        json={
            "query": "provider configuration logs",
            "agent": "codex",
            "host_hash": "host-a",
            "session_id": "session-a",
        },
    )
    assert retrieval.status_code == 200
    retrieval_body = retrieval.json()
    assert any(item["node_id"] == seed.node_id for item in retrieval_body["results"])

    outcome = client.post(
        "/api/v1/brain/outcome",
        headers=auth,
        json={
            "retrieval_id": retrieval_body["retrieval_id"],
            "node_id": seed.node_id,
            "status": "applied",
            "note": "Verified the live config before editing.",
        },
    )
    assert outcome.status_code == 200
    assert outcome.json()["recorded"] == 1

    proposal = client.post(
        "/api/v1/brain/propose",
        headers=auth,
        json={
            "summary": "Verify generated configuration before service restart",
            "observation": "A syntax check caught a malformed generated file before restart.",
            "why_it_matters": "A malformed restart can turn a safe edit into downtime.",
            "suggested_memory": "Run the native syntax validator after generating configuration and before restarting the service.",
            "project": "global",
            "scope": "global",
            "category": "workflow_hint",
            "risk_level": "low",
            "agent": "codex",
            "host_hash": "host-a",
            "evidence": [{
                "source_type": "test",
                "source_uri": "test://closed-loop/proposal",
                "quoted_excerpt": "The validator rejected malformed generated configuration before restart.",
            }],
        },
    )
    assert proposal.status_code == 202
    proposal_id = proposal.json()["proposal_id"]
    assert runtime.run_scan_cycle().ingested_count == 1
    assert client.get(f"/api/v1/brain/proposals/{proposal_id}", headers=auth).json()["status"] == "ingested_pending"

    approved = client.post(f"/api/review/{proposal_id}/approve-db-only", headers=auth)
    assert approved.status_code == 200
    pipeline = runtime.run_knowledge_pipeline(backfill_embeddings=False)
    assert pipeline["proposals"]["failed"] == 0

    status = client.get(f"/api/v1/brain/proposals/{proposal_id}", headers=auth)
    assert status.status_code == 200
    assert status.json()["status"] == "linked"
    knowledge_id = status.json()["knowledge_id"]

    second = client.post(
        "/api/v1/brain/retrieve",
        headers=auth,
        json={
            "query": "syntax validator generated configuration restart",
            "agent": "codex",
            "host_hash": "host-a",
            "session_id": "session-b",
        },
    )
    assert second.status_code == 200
    assert any(item["node_id"] == knowledge_id for item in second.json()["results"])

    finalized = client.post(
        "/api/v1/brain/finalize",
        headers=auth,
        json={"agent": "codex", "host_hash": "host-a", "session_id": "session-a"},
    )
    assert finalized.status_code == 200
    final_body = finalized.json()
    assert final_body["final_result"] == "complete"
    assert final_body["retrieval_events"] == 1
    assert final_body["expected_outcomes"] == final_body["reported_outcomes"]
    assert final_body["missing_pairs"] == []


def test_pending_proposal_is_not_linked_before_explicit_review(tmp_path: Path) -> None:
    sync_root = tmp_path / "sync"
    config = HermesConfig(sync_root=sync_root, db_path=tmp_path / "brain.sqlite3", auth_token="token")
    repo = HermesRepository(config.db_path)
    runtime = HermesRuntime(config=config, repo=repo)
    client = TestClient(create_app(repo=repo, sync_root=sync_root, config=config))
    response = client.post(
        "/api/v1/brain/propose",
        headers={"Authorization": "Bearer token"},
        json={
            "summary": "Do not link pending proposals",
            "observation": "Governance review has not occurred.",
            "why_it_matters": "Unreviewed rules must not enter retrieval.",
            "suggested_memory": "Only materialize approved proposals into knowledge.",
            "evidence": [{"source_type": "test", "source_uri": "test://pending"}],
        },
    )
    proposal_id = response.json()["proposal_id"]
    runtime.run_scan_cycle()

    pipeline = runtime.run_knowledge_pipeline(backfill_embeddings=False)

    assert pipeline["proposals"]["eligible"] == 0
    assert repo.get_proposal_knowledge_link(proposal_id) is None
    assert client.get(
        f"/api/v1/brain/proposals/{proposal_id}",
        headers={"Authorization": "Bearer token"},
    ).json()["status"] == "ingested_pending"


def test_finalize_reports_missing_outcome_without_fabricating_feedback(tmp_path: Path) -> None:
    sync_root = tmp_path / "sync"
    config = HermesConfig(sync_root=sync_root, db_path=tmp_path / "brain.sqlite3", auth_token="token")
    repo = HermesRepository(config.db_path)
    client = TestClient(create_app(repo=repo, sync_root=sync_root, config=config))
    node = integrate(
        content="Use exact candidate IDs when reporting outcomes.",
        source="test-seed",
        category="rule",
        domain="tech",
        evidence=["test://missing-outcome"],
        repo=repo,
    )
    repo.update_knowledge_node(node.node_id, stage="verified")
    retrieval = client.post(
        "/api/v1/brain/retrieve",
        headers={"Authorization": "Bearer token"},
        json={
            "query": "exact candidate IDs outcomes",
            "agent": "codex",
            "host_hash": "host-a",
            "session_id": "missing-session",
        },
    ).json()
    assert any(item["node_id"] == node.node_id for item in retrieval["results"])

    finalized = client.post(
        "/api/v1/brain/finalize",
        headers={"Authorization": "Bearer token"},
        json={"agent": "codex", "host_hash": "host-a", "session_id": "missing-session"},
    ).json()

    assert finalized["final_result"] == "incomplete"
    assert finalized["reported_outcomes"] == 0
    assert finalized["expected_outcomes"] >= 1
    assert finalized["missing_pairs"]
    stored = repo.get_knowledge_node(node.node_id)
    assert stored is not None
    assert stored.outcome_count == 0
