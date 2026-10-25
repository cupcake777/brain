"""Lineage backfill and topical links for the knowledge graph.

The knowledge page draws ``memory_edges`` whose endpoints are both knowledge
nodes. ``derived_from`` stays out of that picture: those edges point at
proposals. Topic links use text overlap because the embedding provider is off.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict

GRAPH_EDGE_TYPES = frozenset({
    "related_to",
    "supersedes",
    "contradicts",
    "duplicates",
    "merged_from",
    "parent_id",
})

_TOKEN = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]")
_STOP = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with",
    "from", "by", "as", "at", "is", "are", "was", "were", "be", "been",
    "being", "it", "its", "this", "that", "these", "those", "if", "when",
    "do", "does", "not", "no", "into", "over", "than", "then", "so", "but",
    "we", "you", "your", "our", "they", "their", "must", "should", "can",
    "may", "will", "only", "also", "before", "after", "during", "per", "via",
    "all", "any", "each", "such", "than", "too", "very",
})


def _json_ids(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item]


def tokens(text: str) -> set[str]:
    """Content tokens, without English function words."""
    return {
        part for part in _TOKEN.findall((text or "").lower())
        if part not in _STOP and not part.isdigit()
    }


def text_similarity(left: str, right: str) -> float:
    """Jaccard similarity of content tokens."""
    a, b = tokens(left), tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def topical_pairs(
    nodes: list,
    *,
    floor: float = 0.22,
    degree: int = 3,
    min_overlap: int = 4,
) -> list[tuple[str, str, float]]:
    """Return undirected pairs, at most ``degree`` links per node.

    A pair is kept when it is among a node's strongest neighbors and clears
    both the similarity floor and the minimum token overlap.
    """
    if degree < 1:
        return []
    prepared: list[tuple[str, set[str]]] = []
    for node in nodes:
        node_id = str(getattr(node, "id", None) or node.get("id") or "")
        if not node_id:
            continue
        summary = getattr(node, "summary", None)
        content = getattr(node, "content", None)
        if summary is None and isinstance(node, dict):
            summary = node.get("summary")
            content = node.get("content")
        words = tokens(f"{summary or ''}\n{content or ''}")
        if len(words) >= min_overlap:
            prepared.append((node_id, words))

    candidates: list[tuple[float, str, str]] = []
    for i, (left_id, left_words) in enumerate(prepared):
        for right_id, right_words in prepared[i + 1:]:
            overlap = len(left_words & right_words)
            if overlap < min_overlap:
                continue
            score = overlap / len(left_words | right_words)
            if score < floor:
                continue
            candidates.append((score, left_id, right_id))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))

    degree_of: dict[str, int] = defaultdict(int)
    chosen: list[tuple[str, str, float]] = []
    for score, left_id, right_id in candidates:
        if degree_of[left_id] >= degree or degree_of[right_id] >= degree:
            continue
        degree_of[left_id] += 1
        degree_of[right_id] += 1
        chosen.append((left_id, right_id, score))
    return chosen


def backfill_lineage(repo) -> dict[str, int]:
    """Copy node fields that already name another node into ``memory_edges``."""
    nodes = repo.list_knowledge_nodes(limit=10000)
    known = {node.id for node in nodes}
    counts = {"supersedes": 0, "contradicts": 0, "merged_from": 0}
    for node in nodes:
        target = (node.supersedes or "").strip()
        if target and target in known and target != node.id:
            repo.insert_memory_edge(node.id, target, "supersedes")
            counts["supersedes"] += 1
        for other_id in _json_ids(node.contradicts):
            if other_id in known and other_id != node.id:
                repo.insert_memory_edge(node.id, other_id, "contradicts")
                counts["contradicts"] += 1
        for absorbed_id in _json_ids(node.merged_from):
            if absorbed_id in known and absorbed_id != node.id:
                repo.insert_memory_edge(absorbed_id, node.id, "merged_from")
                counts["merged_from"] += 1
    return counts


def link_topics(repo, *, floor: float = 0.22, degree: int = 3) -> int:
    """Write ``related_to`` edges among canonized nodes. Existing edges stay."""
    nodes = repo.list_knowledge_nodes(stage="canonized", limit=10000)
    pairs = topical_pairs(nodes, floor=floor, degree=degree)
    for left, right, score in pairs:
        repo.insert_memory_edge(left, right, "related_to", evidence_id=f"text={score:.3f}")
    return len(pairs)
