#!/usr/bin/env python3
"""Evaluate lexical retrieval in disposable databases, without live metrics.

These synthetic labels exercise matching contracts, not real task improvement.
Both the fixture and results can be frozen for before/after comparisons.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hermes.event_store import Principal
from hermes.knowledge_retrieval_v2 import retrieve
from hermes.knowledge_store import KnowledgeStore
from hermes.repository import HermesRepository, KnowledgeNode

DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "retrieval_relevance.json"


@contextmanager
def fixture_stores(fixture):
    """Build only synthetic knowledge; do not call tracked retrieval or APIs."""
    previous = os.environ.get("BRAIN_DISABLE_EMBEDDINGS")
    os.environ["BRAIN_DISABLE_EMBEDDINGS"] = "1"
    try:
        with tempfile.TemporaryDirectory(prefix="brain-retrieval-eval-") as directory:
            db = Path(directory) / "fixture.sqlite3"
            repo = HermesRepository(db)
            store = KnowledgeStore(db)
            principal = Principal("fixture-agent", "fixture-workspace", "fixture-project")
            aliases = {}
            try:
                for node in fixture["nodes"]:
                    repo.insert_knowledge_node(KnowledgeNode(
                        id=node["id"], parent_id=None, summary=node["summary"], content=node["content"],
                        category="rule", domain="tech", stage=node.get("stage", "canonized"),
                        operation="draft", confidence=0.8, source="synthetic-retrieval-fixture",
                        evidence="[]", supersedes=None, merged_from="[]", contradicts="[]", verified_by="[]",
                        created_at="2026-01-01T00:00:00+00:00", refined_at=None, verified_at=None,
                        deprecated_at=None, retrieval_count=0, last_used_at=None, correction_count=0,
                        outcome_count=0, last_outcome_at=None, kind="lesson",
                        trigger_terms=json.dumps(node.get("trigger_terms", [])), use_when="", avoid_when="",
                        success_signal="", failure_signal="",
                    ))
                    row = store.create(principal, node["summary"] + "\n" + node["content"], [])
                    aliases[row["id"]] = node["id"]
                    state = "archived" if node.get("stage") == "deprecated" else "formal"
                    with store.conn:
                        store.conn.execute("INSERT INTO brain_v2_knowledge_states VALUES (?, ?, ?)",
                                           (row["id"], row["version"], state))
                yield repo, store, principal, aliases
            finally:
                store.close()
    finally:
        if previous is None:
            os.environ.pop("BRAIN_DISABLE_EMBEDDINGS", None)
        else:
            os.environ["BRAIN_DISABLE_EMBEDDINGS"] = previous


def run_case(case, lane, repo, store, principal, aliases):
    limit = case.get("limit", 5)
    if lane == "legacy":
        actual = [row["id"] for row in repo.search_knowledge_nodes(case["query"], limit=limit)]
    else:
        result = retrieve(store, principal, case["query"], limit=limit)
        actual = [aliases[row["id"]] for row in result["formal"]]
    expected = case["expected"]
    return {"id": case["id"], "lane": lane, "query": case["query"], "limit": limit,
            "expected": expected, "actual": actual, "missing": sorted(set(expected) - set(actual)),
            "unexpected": sorted(set(actual) - set(expected)), "passed": set(actual) == set(expected)}


def evaluate_fixture(path=DEFAULT_FIXTURE):
    fixture = json.loads(Path(path).read_text())
    cases = []
    with fixture_stores(fixture) as (repo, store, principal, aliases):
        for case in fixture["cases"]:
            for lane in case.get("lanes", ["legacy", "v2"]):
                cases.append(run_case(case, lane, repo, store, principal, aliases))
        with repo._connect() as connection:
            events = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in ("knowledge_retrieval_events", "retrieval_log", "outcome_log")}
    summary = {}
    for lane in ("legacy", "v2"):
        rows = [row for row in cases if row["lane"] == lane]
        known = [row for row in rows if row["expected"]]
        empty = [row for row in rows if not row["expected"]]
        returned = sum(len(row["actual"]) for row in rows)
        relevant = sum(len(set(row["actual"]) & set(row["expected"])) for row in rows)
        summary[lane] = {
            "cases": len(rows), "passed": sum(row["passed"] for row in rows),
            "recall_at_limit": sum((len(set(row["actual"]) & set(row["expected"])) / len(row["expected"]))
                               for row in known) / len(known) if known else None,
            "precision_returned": relevant / returned if returned else None,
            "no_answer_cases": len(empty), "no_answer_abstained": sum(not row["actual"] for row in empty),
        }
    return {"schema": 1, "fixture": str(path), "synthetic": True, "embeddings": False,
            "creates_production_events": False, "fixture_event_counts": events,
            "summary": summary, "cases": cases, "passed": all(row["passed"] for row in cases)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true", help="Exit nonzero for any labelled relevance gap")
    args = parser.parse_args()
    report = evaluate_fixture(args.fixture)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
        print(json.dumps(report["summary"], ensure_ascii=False))
    else:
        print(text, end="")
    return 1 if args.check and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
