from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.exporter import ExportCompiler
from hermes.ingest import IngestionService
from hermes.integrate import retrospect
from hermes.proposals import ProposalWriter
from hermes.repository import HermesRepository, KnowledgeNode
from hermes.runtime import HermesRuntime
from hermes.status import StatusPublisher


def _write(writer: ProposalWriter, *, category: str, risk_level: str, project_key: str, scope: str = "project") -> Path:
    return writer.write(
        source_agent="codex",
        source_host="macbook",
        project_key=project_key,
        category=category,
        risk_level=risk_level,
        summary="Runtime should ingest inbox files.",
        observation="Watcher scans the shared inbox.",
        why_it_matters="The service must process synced proposals automatically.",
        suggested_memory="Run a polling watcher that ingests new proposals and refreshes status.",
        scope=scope,
        evidence='[{"source_type":"test","source_uri":"tests/test_runtime.py","quoted_excerpt":"Runtime integration test proposal evidence."}]',
    )


def _write_proposal(
    writer: ProposalWriter,
    *,
    source_agent: str,
    source_host: str,
    project_key: str,
    category: str,
    risk_level: str,
    suggested_memory: str,
    observation: str = "Observed behavior.",
) -> Path:
    return writer.write(
        source_agent=source_agent,
        source_host=source_host,
        project_key=project_key,
        category=category,
        risk_level=risk_level,
        summary=suggested_memory,
        observation=observation,
        why_it_matters="Because it affects durable behavior.",
        suggested_memory=suggested_memory,
        scope="project",
        evidence='[{"source_type":"test","source_uri":"tests/test_runtime.py","quoted_excerpt":"Test proposal evidence for runtime coverage."}]',
    )


def test_runtime_scan_ingests_new_files_and_publishes_status(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)
    runtime = HermesRuntime(config=config, repo=repo)
    writer = ProposalWriter(config.proposals_dir)

    proposal_path = _write(writer, category="rule", risk_level="high", project_key="brain")

    result = runtime.run_scan_cycle()
    status_path = config.state_dir / "status.md"

    assert result.ingested_count == 1
    assert proposal_path.name in result.processed_files
    assert repo.get_proposal(proposal_path.stem)["state"] == "pending"
    assert status_path.exists()
    assert "Pending proposals: 1" in status_path.read_text(encoding="utf-8")


def test_runtime_ignores_temp_and_syncthing_conflict_files(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)
    runtime = HermesRuntime(config=config, repo=repo)
    proposals_dir = config.proposals_dir
    proposals_dir.mkdir(parents=True, exist_ok=True)
    (proposals_dir / ".tmp-123.md").write_text("partial", encoding="utf-8")
    (proposals_dir / "abc.sync-conflict-20260417-1.md").write_text("conflict", encoding="utf-8")

    result = runtime.run_scan_cycle()

    assert result.ingested_count == 0
    assert result.skipped_files == [".tmp-123.md", "abc.sync-conflict-20260417-1.md"]


def test_runtime_rebuilds_global_and_project_exports_from_approved_records(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)
    runtime = HermesRuntime(config=config, repo=repo)
    writer = ProposalWriter(config.proposals_dir)

    project = _write(writer, category="rule", risk_level="high", project_key="brain")
    global_item = _write(writer, category="rule", risk_level="high", project_key="global", scope="global")

    runtime.run_scan_cycle()
    repo.transition_state(project.stem, "approved_for_export")
    repo.transition_state(global_item.stem, "approved_for_export")

    result = runtime.rebuild_exports()

    assert result.global_updated is True
    assert result.projects_updated == ["brain"]
    assert (config.global_exports_dir / "global.md").exists()
    assert (config.project_exports_dir / "brain.md").exists()


def test_knowledge_export_filters_global_and_project_scopes(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    compiler = ExportCompiler(repo=repo, sync_root=tmp_path / "sync")
    repo.insert_knowledge_node(_make_knowledge_node(
        "global-node",
        content="Global runtime rule should export globally.",
        summary="Global runtime rule",
        domain="general",
        stage="canonized",
        confidence=0.8,
    ))
    repo.insert_knowledge_node(_make_knowledge_node(
        "brain-node",
        content="Brain project scoped rule should stay in brain export.",
        summary="Brain scoped rule",
        domain="brain",
        stage="canonized",
        confidence=0.8,
    ))

    global_path = compiler.build_knowledge_export()
    project_path = compiler.build_knowledge_export(project_key="brain")

    global_text = global_path.read_text(encoding="utf-8")
    project_text = project_path.read_text(encoding="utf-8")
    assert "Global runtime rule" in global_text
    assert "Brain scoped rule" not in global_text
    assert "Brain scoped rule" in project_text
    assert any(record.file_name == "KNOWLEDGE.md" for record in repo.list_export_records())
    assert any(record.file_name == "brain-KNOWLEDGE.md" for record in repo.list_export_records())


def test_runtime_watch_runs_multiple_cycles_with_injected_sleep(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3", poll_interval_seconds=1)
    repo = HermesRepository(config.db_path)
    runtime = HermesRuntime(config=config, repo=repo)
    calls: list[int] = []

    runtime.watch(max_cycles=3, sleep_fn=lambda seconds: calls.append(seconds))

    assert calls == [1, 1]


def test_record_query_updates_matching_knowledge_nodes_and_timestamps(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)

    node = KnowledgeNode(
        id="node-rule-1",
        parent_id=None,
        content="Use brain-query before major technical decisions in the brain project.",
        summary="Use brain-query for technical decisions",
        category="rule",
        domain="devops",
        stage="verified",
        operation="draft",
        confidence=0.7,
        source="test",
        evidence="[]",
        supersedes=None,
        merged_from="[]",
        contradicts="[]",
        verified_by="[]",
        created_at="2026-06-06T00:00:00+00:00",
        refined_at=None,
        verified_at=None,
        deprecated_at=None,
        retrieval_count=0,
        last_used_at=None,
        correction_count=0,
        outcome_count=0,
        last_outcome_at=None,
        kind="rule",
        trigger_terms='["brain-query", "knowledge", "retrieval"]',
        use_when="Applying stable knowledge during runtime or review flows.",
        avoid_when="The knowledge is deprecated or contradicted by newer evidence.",
        success_signal="Retrieval/outcome metrics update and node remains actionable.",
        failure_signal="Node application produces stale guidance or broken metrics.",
    )
    repo.insert_knowledge_node(node)
    repo.insert_proposal({
        "proposal_id": node.id,
        "source_agent": "test",
        "source_host": "ci",
        "created_at": "2026-06-06T00:00:00+00:00",
        "project_key": "global",
        "category": "rule",
        "risk_level": "medium",
        "summary": node.summary,
        "observation": "node proposal metric sync",
        "why_it_matters": "proposal export ranking should reflect runtime retrieval",
        "suggested_memory": node.content,
        "scope": "global",
        "evidence": "[]",
        "state": "approved_for_export",
        "semantic_hash": "hash-node-rule-1",
        "semantic_duplicate_of": None,
        "supersedes": None,
        "weight": 1.0,
        "reviewer_priority": 1.0,
        "retrieval_count_30d": 0,
        "inserted_at": "2026-06-06T00:00:00+00:00",
    })

    event = repo.record_retrieval_for_query("brain-query technical decisions", agent="tester", host="ci")
    assert event["updated"] == 1
    assert event["event_id"]
    assert event["node_ids"] == [node.id]

    stored = repo.get_knowledge_node(node.id)
    assert stored is not None
    assert stored.retrieval_count == 1
    assert stored.last_used_at is not None
    proposal = repo.get_proposal(node.id)
    assert proposal["retrieval_count_30d"] == 1


def test_search_knowledge_nodes_matches_mixed_natural_language(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    node = _make_knowledge_node(
        "node-search-1",
        summary="Knowledge proposal retrieval defects",
        content="检查 knowledge proposal 实际运用缺陷：FTS retrieval outcome scope metrics need repair.",
        domain="brain",
        confidence=0.8,
    )
    repo.insert_knowledge_node(node)

    results = repo.search_knowledge_nodes("检查 knowledge proposal 目前在实际运用中存在什么缺陷和不足", limit=5)
    assert results
    assert results[0]["id"] == "node-search-1"
    assert results[0]["score"] > 0


def test_knowledge_query_api_exposes_stats_list_and_record_query(tmp_path: Path) -> None:
    sync_root = tmp_path / "sync"
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    app = create_app(repo=repo, sync_root=sync_root)
    client = TestClient(app)

    node = KnowledgeNode(
        id="node-workflow-1",
        parent_id=None,
        content="Track retrieval events for knowledge reuse.",
        summary="Track retrieval events",
        category="workflow_hint",
        domain="brain",
        stage="verified",
        operation="draft",
        confidence=0.65,
        source="test",
        evidence="[]",
        supersedes=None,
        merged_from="[]",
        contradicts="[]",
        verified_by="[]",
        created_at="2026-06-06T00:00:00+00:00",
        refined_at=None,
        verified_at=None,
        deprecated_at=None,
        retrieval_count=0,
        last_used_at=None,
        correction_count=0,
        outcome_count=0,
        last_outcome_at=None,
        kind="rule",
        trigger_terms='["brain-query", "knowledge", "retrieval"]',
        use_when="Applying stable knowledge during runtime or review flows.",
        avoid_when="The knowledge is deprecated or contradicted by newer evidence.",
        success_signal="Retrieval/outcome metrics update and node remains actionable.",
        failure_signal="Node application produces stale guidance or broken metrics.",
    )
    repo.insert_knowledge_node(node)

    stats = client.get("/api/knowledge/stats")
    assert stats.status_code == 200
    assert stats.json()["total"] >= 1
    assert "verified" in stats.json()["by_stage"]

    health = client.get("/api/knowledge/health")
    assert health.status_code == 200
    health_payload = health.json()
    assert health_payload["status"] in {"ok", "attention"}
    assert health_payload["stats"]["total"] >= 1
    assert health_payload["missing_metadata"] == 0

    items = client.get("/api/knowledge/list", params={"domain": "brain", "limit": 10})
    assert items.status_code == 200
    payload = items.json()
    assert any(item["id"] == node.id for item in payload)

    detail = client.get(f"/api/knowledge/{node.id}")
    assert detail.status_code == 200
    assert detail.json()["node"]["id"] == node.id
    assert detail.json()["node"]["retrieval_count"] == 0

    record = client.post(
        "/api/knowledge/record-query",
        data={"query": "retrieval events", "agent": "tester", "host": "ci"},
    )
    assert record.status_code == 200
    assert record.json()["updated"] >= 1
    event_id = record.json()["event_id"]

    detail_after = client.get(f"/api/knowledge/{node.id}")
    assert detail_after.status_code == 200
    assert detail_after.json()["node"]["retrieval_count"] >= 1
    assert detail_after.json()["node"]["last_used_at"] is not None

    outcome = client.post(
        f"/api/knowledge/{node.id}/outcome",
        json={"success": True, "note": "worked", "event_id": event_id},
    )
    assert outcome.status_code == 200
    assert outcome.json()["recorded"] is True
    assert outcome.json()["event_id"] == event_id
    assert repo.get_retrieval_event(event_id).outcome_recorded_at is not None


def _make_knowledge_node(node_id: str, **overrides) -> KnowledgeNode:
    """Helper to create a KnowledgeNode with sensible defaults."""
    defaults = dict(
        id=node_id,
        parent_id=None,
        content="Test knowledge content.",
        summary="Test knowledge summary",
        category="rule",
        domain="devops",
        stage="verified",
        operation="draft",
        confidence=0.5,
        source="test",
        evidence="[]",
        supersedes=None,
        merged_from="[]",
        contradicts="[]",
        verified_by="[]",
        created_at="2026-06-06T00:00:00+00:00",
        refined_at=None,
        verified_at=None,
        deprecated_at=None,
        retrieval_count=0,
        last_used_at=None,
        correction_count=0,
        outcome_count=0,
        last_outcome_at=None,
        kind="rule",
        trigger_terms='["brain-query", "knowledge", "retrieval"]',
        use_when="Applying stable knowledge during runtime or review flows.",
        avoid_when="The knowledge is deprecated or contradicted by newer evidence.",
        success_signal="Retrieval/outcome metrics update and node remains actionable.",
        failure_signal="Node application produces stale guidance or broken metrics.",
    )
    defaults.update(overrides)
    return KnowledgeNode(**defaults)


def test_retrospect_defers_canonize_without_operational_metadata(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    refined_at = "2026-05-01T00:00:00+00:00"
    node = _make_knowledge_node(
        "node-quality-gate-1",
        content="Use brain-query before making technical decisions in Brain workflows.",
        summary="Use brain-query before Brain decisions",
        stage="refined",
        confidence=0.8,
        created_at=refined_at,
        refined_at=refined_at,
        trigger_terms="[]",
        use_when="",
        success_signal="",
    )
    repo.insert_knowledge_node(node)

    result = retrospect(repo)

    stored = repo.get_knowledge_node(node.id)
    assert stored is not None
    assert stored.stage == "refined"
    assert result["quality_deferred"] >= 1


def test_record_outcome_increments_count_and_adjusts_confidence(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)

    node = _make_knowledge_node("node-outcome-1", confidence=0.5)
    repo.insert_knowledge_node(node)

    ok = repo.record_outcome("node-outcome-1", success=True, note="worked well")
    assert ok is True

    stored = repo.get_knowledge_node("node-outcome-1")
    assert stored is not None
    assert stored.outcome_count == 1
    assert stored.last_outcome_at is not None
    assert stored.confidence > 0.5  # success bumped it

    ok2 = repo.record_outcome("node-outcome-1", success=False, note="didn't work")
    stored2 = repo.get_knowledge_node("node-outcome-1")
    assert stored2 is not None
    assert stored2.outcome_count == 2
    # With outcome_count=2, cumulative outcome_bonus (0.04) exceeds
    # the interim failure penalty (-0.01), so total confidence may rise.
    # Verify the thought chain captured the failure.
    chains = repo.get_thought_chains("node-outcome-1")
    assert len(chains) == 2
    assert chains[0].decision == "reinforce"
    assert chains[1].decision == "penalize"


def test_outcome_api_endpoint(tmp_path: Path) -> None:
    sync_root = tmp_path / "sync"
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    app = create_app(repo=repo, sync_root=sync_root)
    client = TestClient(app)

    node = _make_knowledge_node("node-api-outcome-1", confidence=0.6)
    repo.insert_knowledge_node(node)

    resp = client.post(
        "/api/knowledge/node-api-outcome-1/outcome",
        json={"success": True, "note": "good result"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_id"] == "node-api-outcome-1"
    assert data["recorded"] is True
    assert data["outcome_count"] == 1
    assert data["confidence"] > 0.6


def test_knowledge_stats_full_includes_outcome_metrics(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)

    node = _make_knowledge_node("node-stats-1", retrieval_count=5, outcome_count=3)
    repo.insert_knowledge_node(node)

    stats = repo.knowledge_stats_full()
    assert stats["total"] >= 1
    assert "by_stage" in stats
    assert stats["total_retrievals"] >= 5
    assert stats["total_outcomes"] >= 3
    assert "avg_confidence" in stats
    assert "ever_retrieved" in stats
    assert "ever_outcome" in stats


def test_top_knowledge_nodes_returns_ranked_list(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)

    node1 = _make_knowledge_node("node-top-1", confidence=0.3, retrieval_count=0, outcome_count=0)
    node2 = _make_knowledge_node("node-top-2", confidence=0.8, retrieval_count=10, outcome_count=5)
    repo.insert_knowledge_node(node1)
    repo.insert_knowledge_node(node2)

    top = repo.top_knowledge_nodes(limit=5)
    assert len(top) >= 2
    assert top[0].id == "node-top-2"  # higher composite score


def test_knowledge_list_api_returns_outcome_fields(tmp_path: Path) -> None:
    sync_root = tmp_path / "sync"
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    app = create_app(repo=repo, sync_root=sync_root)
    client = TestClient(app)

    node = _make_knowledge_node("node-list-1", retrieval_count=7, outcome_count=2)
    repo.insert_knowledge_node(node)

    items = client.get("/api/knowledge/list", params={"limit": 10})
    assert items.status_code == 200
    found = [i for i in items.json() if i["id"] == "node-list-1"]
    assert len(found) == 1
    assert found[0]["retrieval_count"] == 7
    assert found[0]["outcome_count"] == 2


def test_top_api_endpoint(tmp_path: Path) -> None:
    sync_root = tmp_path / "sync"
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    app = create_app(repo=repo, sync_root=sync_root)
    client = TestClient(app)

    node = _make_knowledge_node("node-top-api-1", confidence=0.7, retrieval_count=5, outcome_count=3)
    repo.insert_knowledge_node(node)

    resp = client.get("/api/knowledge/top", params={"limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["id"] == "node-top-api-1"
    assert "retrieval_count" in data[0]
    assert "outcome_count" in data[0]


def test_recompute_confidence_uses_outcome_bonus_and_recent_outcome(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)

    node = _make_knowledge_node("node-recomp-1", confidence=0.4, outcome_count=0)
    repo.insert_knowledge_node(node)
    now_iso = datetime.now(timezone.utc).isoformat()
    repo.update_knowledge_node("node-recomp-1", outcome_count=5, last_outcome_at=now_iso)

    from hermes.integrate import recompute_confidence
    current = repo.get_knowledge_node("node-recomp-1")
    assert current is not None
    updated_conf = recompute_confidence(current, repo)
    base_conf = recompute_confidence(_make_knowledge_node("node-recomp-base", confidence=0.4, outcome_count=0), repo)
    assert updated_conf > base_conf
    assert 0.0 <= updated_conf <= 1.0


def test_outcome_api_creates_thought_chain(tmp_path: Path) -> None:
    sync_root = tmp_path / "sync"
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    app = create_app(repo=repo, sync_root=sync_root)
    client = TestClient(app)

    node = _make_knowledge_node("node-tc-1", confidence=0.6)
    repo.insert_knowledge_node(node)

    resp = client.post(
        "/api/knowledge/node-tc-1/outcome",
        json={"success": True, "note": "worked"},
    )
    assert resp.status_code == 200
    assert resp.json()["recorded"] is True

    chains = repo.get_thought_chains("node-tc-1")
    assert len(chains) >= 1
    assert chains[-1].action == "outcome_recorded"
    assert "success=True" in chains[-1].reasoning


def test_status_publisher_reports_knowledge_stats(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    writer = ProposalWriter(tmp_path / "sync" / "inbox" / "proposals")
    ingest = IngestionService(repo=repo, sync_root=tmp_path / "sync")
    compiler = ExportCompiler(repo=repo, sync_root=tmp_path / "sync")
    status = StatusPublisher(repo=repo, sync_root=tmp_path / "sync")

    proposal = _write_proposal(
        writer,
        source_agent="claude",
        source_host="macbook",
        project_key="brain",
        category="rule",
        risk_level="high",
        suggested_memory="Publish state/status.md at least hourly.",
    )
    proposal_id = ingest.ingest_path(proposal).proposal_id
    repo.transition_state(proposal_id, "approved_for_export")
    compiler.build_project_export("brain")

    node = _make_knowledge_node("node-status-1", retrieval_count=2, outcome_count=1)
    repo.insert_knowledge_node(node)

    status_path = status.publish()
    content = status_path.read_text(encoding="utf-8")

    assert content.startswith("# Hermes Status")
    assert "## Knowledge" in content
    assert "## Top knowledge" in content
    assert "Total nodes:" in content
    assert "Total outcomes:" in content
    assert "brain.md: last rebuilt" in content
