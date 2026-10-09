from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.integrate import integrate
from hermes.repository import HermesRepository


def _client(tmp_path: Path) -> tuple[TestClient, HermesRepository]:
    config = HermesConfig(
        sync_root=tmp_path / "sync",
        db_path=tmp_path / "brain.sqlite3",
        auth_token="token",
    )
    repo = HermesRepository(config.db_path)
    return TestClient(create_app(repo=repo, sync_root=config.sync_root, config=config)), repo


def test_health_separates_liveness_telemetry_and_learning_loop(tmp_path: Path) -> None:
    client, repo = _client(tmp_path)
    with repo._connect() as connection:
        connection.execute(
            "CREATE TABLE source_events (id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO source_events(id, occurred_at) VALUES (?, ?)",
            ("event-1", "2026-09-25T10:00:00+00:00"),
        )

    response = client.get("/api/v1/brain/health", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["liveness"]["status"] == "ok"
    assert payload["liveness"]["database"] == "ok"
    assert payload["telemetry"]["status"] == "active"
    assert payload["telemetry"]["source_events"] == 1
    assert payload["learning_loop"]["status"] == "idle"
    assert payload["learning_loop"]["retrievals"] == 0
    assert payload["learning_loop"]["outcomes"] == 0
    assert payload["learning_loop"]["finalized_sessions"] == 0
    assert payload["learning_loop"]["proposal_links"] == 0


def test_health_reports_real_closed_loop_activity(tmp_path: Path) -> None:
    client, repo = _client(tmp_path)
    node = integrate(
        content="Inspect current state before changing configuration.",
        source="test-health",
        category="rule",
        domain="tech",
        evidence=["test://health/closed-loop"],
        repo=repo,
    )
    repo.update_knowledge_node(node.node_id, stage="verified")
    retrieval = client.post(
        "/api/v1/brain/retrieve",
        headers={"Authorization": "Bearer token"},
        json={
            "query": "current state configuration",
            "agent": "codex",
            "host_hash": "host-a",
            "session_id": "session-a",
        },
    ).json()
    outcome = client.post(
        "/api/v1/brain/outcome",
        headers={"Authorization": "Bearer token"},
        json={
            "retrieval_id": retrieval["retrieval_id"],
            "node_id": node.node_id,
            "status": "applied",
            "note": "Used successfully.",
        },
    )
    assert outcome.status_code == 200
    finalized = client.post(
        "/api/v1/brain/finalize",
        headers={"Authorization": "Bearer token"},
        json={"agent": "codex", "host_hash": "host-a", "session_id": "session-a"},
    )
    assert finalized.status_code == 200

    payload = client.get("/api/v1/brain/health", headers={"Authorization": "Bearer token"}).json()

    assert payload["status"] == "ok"
    assert payload["telemetry"]["status"] == "idle"
    assert payload["learning_loop"]["status"] == "active"
    assert payload["learning_loop"]["retrievals"] == 1
    assert payload["learning_loop"]["outcomes"] == 1
    assert payload["learning_loop"]["finalized_sessions"] == 1
    assert payload["learning_loop"]["complete_sessions"] == 1
    assert payload["learning_loop"]["incomplete_sessions"] == 0
