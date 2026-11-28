from __future__ import annotations

import importlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from hermes.editorial_relations import EditorialRelations
from hermes.environment_scope import assign
from hermes.exporter import ExportCompiler
from hermes.pipeline import sync_approved_proposals
from hermes.repository import HermesRepository, KnowledgeNode

integration = importlib.import_module("hermes.integrate")


@pytest.fixture(autouse=True)
def _local_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise real materialization without invoking cloud providers."""
    monkeypatch.setenv("BRAIN_LLM_ENABLED", "0")
    monkeypatch.setenv("BRAIN_DISABLE_EMBEDDINGS", "1")
    monkeypatch.setattr(integration, "_LLM_AVAILABLE", False)

    def unexpected_network(*args, **kwargs):
        pytest.fail("Curation/export regression tests must stay local")

    monkeypatch.setattr("httpx.Client.send", unexpected_network)
    monkeypatch.setattr("httpx.AsyncClient.send", unexpected_network)


def _proposal(
    proposal_id: str,
    *,
    state: str = "approved_db_only",
    evidence: str = "[]",
    domain: str = "tech",
    memory: str = "Retain curationquartz guidance for database retrieval.",
) -> dict:
    return {
        "proposal_id": proposal_id,
        "source_agent": "test",
        "source_host": "ci",
        "created_at": "2026-11-28T00:00:00+00:00",
        "project_key": "brain",
        "category": "rule",
        "risk_level": "medium",
        "summary": memory,
        "observation": "Observed in a disposable local database.",
        "why_it_matters": "Database approval and publication are separate decisions.",
        "suggested_memory": memory,
        "scope": "global",
        "domain": domain,
        "evidence": evidence,
        "state": state,
        "semantic_hash": f"hash-{proposal_id}",
        "semantic_duplicate_of": None,
        "supersedes": None,
        "weight": 4.0,
        "reviewer_priority": 1.0,
        "retrieval_count_30d": 0,
        "inserted_at": "2026-11-28T00:00:00+00:00",
    }


def _node(repo: HermesRepository, node_id: str, **changes) -> str:
    """Seed existing knowledge without depending on integration heuristics."""
    fields = dict(
        id=node_id, parent_id=None,
        content=f"Standalone guidance {node_id}.", summary=f"Standalone guidance {node_id}.",
        category="rule", domain="tech", stage="refined", operation="draft",
        confidence=0.8, source="user_direct:local-fixture", evidence="[]",
        supersedes=None, merged_from="[]", contradicts="[]", verified_by="[]",
        created_at="2026-11-28T00:00:00+00:00", refined_at=None,
        verified_at=None, deprecated_at=None, retrieval_count=0, last_used_at=None,
        correction_count=0, outcome_count=0, last_outcome_at=None, kind="rule",
        trigger_terms="[]", use_when="", avoid_when="", success_signal="", failure_signal="",
    )
    fields.update(changes)
    repo.insert_knowledge_node(KnowledgeNode(**fields))
    return node_id


def _all_agent_exports(compiler: ExportCompiler) -> list[Path]:
    return [
        compiler.build_knowledge_export(),
        *compiler.build_lane_exports(),
        compiler.build_global_export(),
        compiler.build_project_export("brain"),
        compiler.build_claude_md_export(),
        compiler.export_brain_context(),
    ]


@pytest.mark.parametrize("domain", ["tech", "science", "curation"])
def test_db_only_materializes_and_is_searchable_without_agent_exports(tmp_path: Path, domain: str) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    proposal = _proposal("only-db", state="pending", domain=domain)
    repo.insert_proposal(proposal)
    assert sync_approved_proposals(repo)["synced"] == 0
    repo.transition_state("only-db", "approved_db_only")

    result = sync_approved_proposals(repo)
    link = repo.get_proposal_knowledge_link("only-db")
    node = repo.get_knowledge_node(link["knowledge_id"])
    assert result["synced"] == 1
    assert result["failed"] == 0
    assert node.stage == "refined" and node.confidence >= 0.5
    assert node.id in {row["id"] for row in repo.search_knowledge_nodes("curationquartz")}

    compiler = ExportCompiler(repo=repo, sync_root=tmp_path / "sync")
    paths = _all_agent_exports(compiler)
    assert f"{domain}.md" in {path.name for path in paths}
    for path in paths:
        assert "curationquartz" not in path.read_text(), path
    assert "curationquartz" not in compiler.build_knowledge_export(domain).read_text()
    assert repo.get_knowledge_node(node.id) is not None


@pytest.mark.parametrize("withdrawn_state", ["approved_db_only", "pending", "rejected", "superseded"])
def test_explicit_export_approval_is_current_and_lane_files_are_rewritten(
    tmp_path: Path, withdrawn_state: str,
) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    repo.insert_proposal(_proposal("authorization", domain="curation"))
    sync_approved_proposals(repo)
    node_id = repo.get_proposal_knowledge_link("authorization")["knowledge_id"]
    compiler = ExportCompiler(repo=repo, sync_root=tmp_path / "sync")
    _all_agent_exports(compiler)

    repo.transition_state("authorization", "approved_for_export")
    assert sync_approved_proposals(repo)["already_linked"] == 1
    for path in _all_agent_exports(compiler):
        if path.name not in {"tech.md", "science.md"}:
            assert "curationquartz" in path.read_text(), path
    assert repo.get_proposal_knowledge_link("authorization")["knowledge_id"] == node_id
    lane_path = tmp_path / "sync" / "exports" / "global" / "curation.md"
    assert "curationquartz" in lane_path.read_text()

    repo.transition_state("authorization", withdrawn_state)
    for path in _all_agent_exports(compiler):
        assert "curationquartz" not in path.read_text(), path
    assert "curationquartz" not in lane_path.read_text()
    assert repo.get_knowledge_node(node_id) is not None


@pytest.mark.parametrize(
    "other_state,restricted,retired,expected",
    [
        ("approved_db_only", False, False, False),
        ("pending", False, False, False),
        ("rejected", False, False, False),
        ("superseded", False, False, False),
        ("approved_for_export", False, False, True),
        ("approved_for_export", True, False, False),
        ("approved_for_export", False, True, False),
    ],
)
def test_shared_node_needs_at_least_one_current_eligible_proposal(
    tmp_path: Path, other_state: str, restricted: bool, retired: bool, expected: bool,
) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    node_id = _node(repo, "multi-linked")
    for proposal_id, state in (("db-source", "approved_db_only"), ("other-source", other_state)):
        repo.insert_proposal(_proposal(proposal_id, state=state))
        repo.link_proposal_knowledge(proposal_id, node_id, action="merged")
    if restricted:
        # Even a globally scoped node cannot borrow a scoped proposal's approval.
        with repo._connect() as connection:
            assign(connection, "proposal", "other-source", {"server_id": "private-host"})
    if retired:
        repo.retire_proposal_knowledge("other-source", "Reviewer withdrew this source")

    compiler = ExportCompiler(repo=repo, sync_root=tmp_path / "sync")
    for path in (compiler.build_knowledge_export(), *compiler.build_lane_exports()):
        if path.name != "science.md":
            assert ("Standalone guidance multi-linked." in path.read_text()) is expected, path


def test_scope_retirement_and_stage_limits_remain_effective(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    compiler = ExportCompiler(repo=repo, sync_root=tmp_path / "sync")
    nodes = {
        "standalone", "deprecated", "draft", "low-confidence", "private-node", "retired-node",
    }
    for node_id in nodes:
        _node(repo, node_id)
    repo.update_knowledge_node("deprecated", stage="deprecated")
    repo.update_knowledge_node("draft", stage="draft")
    repo.update_knowledge_node("low-confidence", confidence=0.49)
    with repo._connect() as connection:
        assign(connection, "knowledge", "private-node", {"server_id": "private-host"})
    for node_id in ("deprecated", "private-node", "retired-node"):
        repo.insert_proposal(_proposal(node_id, state="approved_for_export"))
        repo.link_proposal_knowledge(node_id, node_id, action="legacy")
    repo.retire_proposal_knowledge("retired-node", "Retired during review")

    for path in (compiler.build_knowledge_export(), *compiler.build_lane_exports()):
        text = path.read_text()
        if path.name != "science.md":
            assert "Standalone guidance standalone." in text
        for node_id in nodes - {"standalone"}:
            assert f"Standalone guidance {node_id}." not in text, path


def test_db_only_superseder_does_not_hide_exportable_knowledge(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    original = _node(repo, "original")
    replacement = _node(repo, "replacement", supersedes=original)
    repo.insert_proposal(_proposal("replacement-source"))
    repo.link_proposal_knowledge("replacement-source", replacement, action="created")
    compiler = ExportCompiler(repo=repo, sync_root=tmp_path / "sync")

    for path in (compiler.build_knowledge_export(), *compiler.build_lane_exports()):
        if path.name != "science.md":
            assert "Standalone guidance original." in path.read_text()
        assert "Standalone guidance replacement." not in path.read_text()

    repo.transition_state("replacement-source", "approved_for_export")
    for path in (compiler.build_knowledge_export(), *compiler.build_lane_exports()):
        assert "Standalone guidance original." not in path.read_text()
        if path.name != "science.md":
            assert "Standalone guidance replacement." in path.read_text()


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            json.dumps([{"source_type": "test", "source_uri": "tests/local.log:4", "quoted_excerpt": "Observed 3 rows; no validation was performed."}]),
            [{"source_type": "test", "source_uri": "tests/local.log:4", "quoted_excerpt": "Observed 3 rows; no validation was performed."}],
        ),
        ('["tests/local.log:4", "Observed output only"]', ["tests/local.log:4", "Observed output only"]),
        ("  tests/local.log:4\n原始记录，仅观察。  ", ["  tests/local.log:4\n原始记录，仅观察。  "]),
        ('[truncated JSON evidence', ['[truncated JSON evidence']),
        ('{"source_uri":"tests/local.log:4"}', ['{"source_uri":"tests/local.log:4"}']),
        ('"JSON scalar evidence"', ['"JSON scalar evidence"']),
        ("[]", []),
        (" \n", []),
    ],
)
def test_materialization_preserves_evidence_without_inventing_verification(
    tmp_path: Path, raw: str, expected: list,
) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    repo.insert_proposal(_proposal("evidence-source", evidence=raw))
    first = sync_approved_proposals(repo)
    node_id = repo.get_proposal_knowledge_link("evidence-source")["knowledge_id"]
    node = repo.get_knowledge_node(node_id)

    assert first["synced"] == 1 and first["failed"] == 0
    assert json.loads(node.evidence) == expected
    assert node.source == "proposal:evidence-sou"
    assert json.loads(node.verified_by) == []
    assert node.verified_at is None and node.stage == "refined"
    assert repo.get_proposal("evidence-source")["evidence"] == raw
    assert sync_approved_proposals(repo)["already_linked"] == 1
    assert repo.get_knowledge_node(node_id).evidence == node.evidence


@pytest.mark.parametrize("path", ["merge", "legacy"])
def test_evidence_is_preserved_when_reusing_existing_knowledge(tmp_path: Path, path: str) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    incoming = [{"source_type": "test", "source_uri": "tests/second.log:7", "quoted_excerpt": "Second observation, unvalidated."}]
    proposal = _proposal("reuse-source", evidence=json.dumps(incoming),
                         memory="Retain curationquartz guidance for database retrieval on port 4242.")
    repo.insert_proposal(proposal)
    content = proposal["suggested_memory"] + "\n\nObservation: " + proposal["observation"]
    node_id = _node(
        repo, "reused-node", content=content, summary=content[:120].rstrip(),
        evidence='["tests/first.log:2"]',
        source="proposal:reuse-source" if path == "legacy" else "user_direct:fixture",
    )
    result = sync_approved_proposals(repo)
    assert result["failed"] == 0
    assert result["synced"] == (1 if path == "merge" else 0)
    assert result["already_linked"] == (0 if path == "merge" else 1)
    link = repo.get_proposal_knowledge_link("reuse-source")
    assert link["knowledge_id"] == node_id
    if path == "merge":
        assert link["sync_action"] == "merged"
    node = repo.get_knowledge_node(node_id)
    assert json.loads(node.evidence) == ["tests/first.log:2", *incoming]
    assert json.loads(node.verified_by) == [] and node.verified_at is None
    assert len(repo.list_knowledge_nodes()) == 1
    sync_approved_proposals(repo)
    assert repo.get_knowledge_node(node_id).evidence == node.evidence


@pytest.mark.parametrize("state", ["approved_db_only", "approved_for_export"])
@pytest.mark.parametrize("proposal_evidence", [
    "Original proposal text awaiting a separate historical backfill decision.",
    '[{"source_uri":"tests/original.log:3","quoted_excerpt":"Original submission."}]',
])
@pytest.mark.parametrize("node_evidence", [
    "[]",
    '[ { "source_uri": "tests/curation.log:8", "quoted_excerpt": "Curated observation." } ]',
])
def test_already_linked_sync_preserves_evidence_review_digest_and_relations(
    tmp_path: Path, state: str, proposal_evidence: str, node_evidence: str,
) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    proposal = _proposal("curated-source", state=state, evidence=proposal_evidence)
    repo.insert_proposal(proposal)
    node_id = _node(repo, "curated-node", evidence=node_evidence)
    repo.link_proposal_knowledge("curated-source", node_id, action="curation")
    original_node = repo.get_knowledge_node(node_id)
    original_link = repo.get_proposal_knowledge_link("curated-source")

    relations = EditorialRelations(repo)
    notes = relations.notes
    node_item = asdict(original_node)
    original_digest = notes.digest("knowledge", node_item)
    review_id = notes.record(
        "knowledge", node_item, reviewer="test-curator", session_id="curation-test",
        title_zh="保留已整理证据", summary_zh="证据已经独立整理，原始提案仅作为来源。",
        disposition="retain", reasoning="当前节点证据已完成整理，周期同步应保持审核摘要。",
        next_step="历史证据回填由独立运维流程处理。", expected_digest=original_digest,
    )
    edge_id = relations.link(
        "proposal", "curated-source", "knowledge", node_id, "related_to",
        source_digest=notes.digest("proposal", proposal), target_digest=original_digest,
        reasoning="此提案是已整理知识节点的来源。",
        evidence=[{"source_uri": "tests/curation.log:8", "quoted_excerpt": "Curated observation."}],
        reviewer="test-curator", session_id="curation-test",
    )
    original_edges = relations.snapshot()["edges"]
    assert len(original_edges) == 1 and original_edges[0]["id"] == edge_id

    for _ in range(2):
        result = sync_approved_proposals(repo)
        current = repo.get_knowledge_node(node_id)
        assert result["already_linked"] == 1
        assert result["synced"] == 0 and result["failed"] == 0
        assert current == original_node
        assert current.evidence == node_evidence
        assert repo.get_proposal_knowledge_link("curated-source") == original_link
        assert notes.digest("knowledge", asdict(current)) == original_digest
        attached = notes.attach("knowledge", [asdict(current)])[0]
        assert attached["editorial_review"]["id"] == review_id
        assert attached["review_outdated"] is False
        snapshot = relations.snapshot()
        assert snapshot["stale"] == 0 and snapshot["edges"] == original_edges
