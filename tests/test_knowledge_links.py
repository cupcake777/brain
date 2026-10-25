from pathlib import Path

from hermes.knowledge_links import backfill_lineage, topical_pairs
from hermes.repository import HermesRepository, KnowledgeNode


def _node(node_id: str, **overrides: object) -> KnowledgeNode:
    fields = dict(
        id=node_id,
        parent_id=None,
        content=f"content for {node_id}",
        summary=f"summary for {node_id}",
        category="rule",
        domain="tech",
        stage="canonized",
        operation="canonize",
        confidence=0.8,
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
    )
    fields.update(overrides)
    return KnowledgeNode(**fields)


def test_topical_pairs_keep_only_strong_neighbors_and_cap_degree() -> None:
    nodes = [
        {"id": "oauth", "summary": "OAuth refresh token pool must not run on two gateways", "content": "single use refresh token invalidates the account"},
        {"id": "oauth-2", "summary": "OAuth refresh token pool must stay on one gateway", "content": "single use refresh token invalidates the account"},
        {"id": "plink", "summary": "PLINK keep file needs FID and IID columns", "content": "one column IID file fails the keep parser"},
        {"id": "mem", "summary": "Project memory belongs in a mem file", "content": "do not create a project local codex directory"},
    ]
    pairs = topical_pairs(nodes, floor=0.2, degree=1)
    linked = {tuple(sorted((left, right))) for left, right, _score in pairs}
    assert ("oauth", "oauth-2") in linked
    assert all("plink" not in pair or pair == ("plink", "plink") for pair in linked)
    assert all(sum(node_id in pair for pair in linked) <= 1 for node_id in ("oauth", "oauth-2", "plink", "mem"))


def test_backfill_lineage_records_edges_for_existing_nodes(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    repo.insert_knowledge_node(_node("keeper"))
    repo.insert_knowledge_node(_node("older", supersedes="keeper", contradicts='["keeper"]', stage="deprecated"))
    repo.update_knowledge_node("keeper", merged_from='["older"]')
    counts = backfill_lineage(repo)
    kinds = {edge["edge_type"] for edge in repo.list_memory_edges()}
    assert counts["supersedes"] == 1
    assert counts["contradicts"] == 1
    assert counts["merged_from"] == 1
    assert kinds == {"supersedes", "contradicts", "merged_from"}
