from __future__ import annotations

from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.pipeline import sync_approved_proposals
from hermes.repository import HermesRepository
from hermes.templates import proposal_lifecycle_page


def _proposal(proposal_id: str, *, state: str, summary: str | None = None) -> dict[str, str | int | float | None]:
    return {
        "proposal_id": proposal_id,
        "source_agent": "test",
        "source_host": "ci",
        "created_at": "2026-07-11T00:00:00+00:00",
        "project_key": "brain",
        "category": "rule",
        "risk_level": "medium",
        "summary": summary or f"Summary for {proposal_id}",
        "observation": "Observed durable behavior.",
        "why_it_matters": "It should become maintained knowledge after approval.",
        "suggested_memory": f"Durable guidance for {proposal_id}.",
        "scope": "project",
        "evidence": "[]",
        "state": state,
        "semantic_hash": f"hash-{proposal_id}",
        "semantic_duplicate_of": None,
        "supersedes": None,
        "weight": 4.0,
        "reviewer_priority": 1.0,
        "retrieval_count_30d": 0,
        "inserted_at": "2026-07-11T00:00:00+00:00",
    }


def test_sync_generates_only_approved_knowledge_and_is_idempotent(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    repo.insert_proposal(_proposal("approved-export", state="approved_for_export"))
    repo.insert_proposal(_proposal("approved-db", state="approved_db_only"))
    repo.insert_proposal(_proposal("pending", state="pending"))
    repo.insert_proposal(_proposal("rejected", state="rejected"))

    first = sync_approved_proposals(repo)
    second = sync_approved_proposals(repo)
    status = repo.proposal_sync_status()

    assert first["eligible"] == 2
    assert first["synced"] == 2
    assert first["failed"] == 0
    assert second["synced"] == 0
    assert second["already_linked"] == 2
    assert status["approved"] == 2
    assert status["linked"] == 2
    assert status["missing"] == 0
    assert len(repo.list_knowledge_nodes(limit=20)) == 2
    assert repo.get_proposal_knowledge_link("approved-export") is not None
    assert repo.get_proposal_knowledge_link("pending") is None


def test_sync_materializes_legacy_source_link_without_duplicate(tmp_path: Path) -> None:
    from hermes.repository import KnowledgeNode

    repo = HermesRepository(tmp_path / "brain.sqlite3")
    proposal_id = "12345678-1234-1234-1234-123456789abc"
    repo.insert_proposal(_proposal(proposal_id, state="approved_db_only"))
    repo.insert_knowledge_node(KnowledgeNode(
        id="legacy-node",
        parent_id=None,
        content="Legacy approved content.",
        summary="Legacy approved content",
        category="rule",
        domain="brain",
        stage="canonized",
        operation="draft",
        confidence=0.8,
        source=f"proposal:{proposal_id[:12]}",
        evidence="[]",
        supersedes=None,
        merged_from="[]",
        contradicts="[]",
        verified_by="[]",
        created_at="2026-07-01T00:00:00+00:00",
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

    result = sync_approved_proposals(repo)

    assert result["synced"] == 0
    assert result["already_linked"] == 1
    assert len(repo.list_knowledge_nodes(limit=20)) == 1
    assert repo.get_proposal_knowledge_link(proposal_id)["knowledge_id"] == "legacy-node"


def test_pipeline_api_and_frontend_expose_sync_and_vector_state(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    repo.insert_proposal(_proposal("approved", state="approved_for_export"))
    sync_approved_proposals(repo)
    app = create_app(repo=repo, sync_root=tmp_path / "sync")
    client = TestClient(app)

    payload = client.get("/api/knowledge/pipeline").json()
    page = client.get("/proposals").text

    assert payload["proposals"]["approved"] == 1
    assert payload["proposals"]["missing"] == 0
    assert payload["proposals"]["state"] == "healthy"
    assert "Automation" in page
    assert "1 / 1 linked" in page
    assert "Vector Index" in page
    assert 'data-filter="all" class="kg-pill active"' in page
    assert "kgSetFilter('all', this)" in page


def test_embedding_status_counts_only_unrecorded_rows_as_pending(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BRAIN_DISABLE_EMBEDDINGS", "1")
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    for proposal_id in ("ready", "failed", "missing"):
        repo.insert_proposal(_proposal(proposal_id, state="pending"))

    repo._store_embedding(
        "proposal", "ready", "hash-ready", "test-model",
        vector=[0.1, 0.2], status="ready",
    )
    repo._store_embedding(
        "proposal", "failed", "hash-failed", "test-model",
        vector=None, status="failed", error="provider unavailable",
    )
    # Production also has source rows with no entity_embeddings record at all.
    with repo._connect() as connection:
        connection.execute(
            "DELETE FROM entity_embeddings WHERE entity_type = 'proposal' AND entity_id = 'missing'"
        )

    status = repo.embedding_status()
    entities = cast(dict[str, object], status["entities"])
    proposals = cast(dict[str, object], entities["proposal"])

    assert proposals["total"] == 3
    assert proposals["ready"] == 1
    assert proposals["failed"] == 1
    assert proposals["pending"] == 1
    top_counts = cast(dict[str, int], status)
    assert sum(top_counts[key] for key in ("ready", "failed", "pending")) == top_counts["total"]


def test_pipeline_frontend_renders_all_vector_states() -> None:
    graph = {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0}}
    cases = {
        "healthy": {"enabled": True, "configured": True, "disabled": False, "ready": 2, "pending": 0, "failed": 0},
        "syncing": {"enabled": True, "configured": True, "disabled": False, "ready": 1, "pending": 1, "failed": 0},
        "degraded": {"enabled": True, "configured": True, "disabled": False, "ready": 1, "pending": 0, "failed": 1},
        "disabled": {"enabled": False, "configured": True, "disabled": True, "ready": 0, "pending": 2, "failed": 0},
        "not_configured": {"enabled": False, "configured": False, "disabled": False, "ready": 0, "pending": 2, "failed": 0},
    }
    for state, values in cases.items():
        total = values["ready"] + values["pending"] + values["failed"]
        provider = {key: values[key] for key in ("enabled", "configured", "disabled")}
        provider["model"] = "test-model"
        embeddings = {
            "state": state,
            "provider": provider,
            "total": total,
            "ready": values["ready"],
            "pending": values["pending"],
            "failed": values["failed"],
            "entities": {"proposal": {"ready": 0, "total": 0}, "knowledge": {"ready": 0, "total": 0}},
        }
        html = proposal_lifecycle_page(
            {"proposal_sync": {"approved": 0, "linked": 0, "missing": 0, "coverage": 100.0, "state": "healthy"}, "embeddings": embeddings},
            graph_data=graph,
        )
        assert f'data-state="{state}"' in html
        assert state.replace("_", " ") in html
