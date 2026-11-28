from __future__ import annotations

import json

import pytest

from hermes.retrieval_lexical import query_terms, term_coverage
from scripts.eval_brain_retrieval import DEFAULT_FIXTURE, evaluate_fixture, fixture_stores, run_case


FIXTURE = json.loads(DEFAULT_FIXTURE.read_text())
CASES = [
    pytest.param(case, lane, id=f"{lane}-{case['id']}")
    for case in FIXTURE["cases"] for lane in case.get("lanes", ["legacy", "v2"])
]


@pytest.fixture(scope="module")
def stores():
    with fixture_stores(FIXTURE) as value:
        yield value


@pytest.mark.parametrize("case,lane", CASES)
def test_labelled_retrieval(case, lane, stores):
    result = run_case(case, lane, *stores)
    assert result["passed"], result


@pytest.mark.parametrize("query,expected", [
    ("How do I inspect a gateway lock file?", ["inspect", "gateway", "lock", "file"]),
    ("Could you please help me?", []),
    ("CAN can `do` \"the\"", ["can", "do", "the"]),
    ("Café café CAF", ["café", "caf"]),
    ("session_id brain-query 检索反馈", ["session_id", "brain-query", "检索反馈"]),
    ("检索反馈session_id", ["检索反馈", "session_id"]),
])
def test_query_terms_preserve_literals(query, expected):
    assert query_terms(query) == expected


def test_text_stopwords_stay_available_to_explicit_queries():
    assert term_coverage(query_terms('`do` "the" CAN'), "Do the CAN check.") == 3
    assert term_coverage(query_terms("session_id"), "session id") == 0
    assert term_coverage(query_terms("brain-query"), "Brain query") == 0
    assert term_coverage(query_terms("café"), "CAF cabinet") == 0


def test_evaluator_exposes_known_gaps_without_writing_metrics():
    report = evaluate_fixture()
    assert report["passed"] is True
    assert report["fixture_event_counts"] == {
        "knowledge_retrieval_events": 0, "retrieval_log": 0, "outcome_log": 0,
    }


def test_combined_retrieval_uses_the_same_chinese_and_literal_boundaries(stores):
    repo, store, principal, aliases = stores
    feedback = next(key for key, value in aliases.items() if value == "feedback")
    result = repo.record_retrieval_for_query(
        "检索反馈", agent=principal.actor, host="fixture-host", session_id="fixture-session",
        v2_principal=principal, limit=2,
    )
    assert set(result["node_ids"]) == {"feedback", feedback}
    for row in result["results"]:
        assert 1 <= row["score"] < 1.5
    empty = repo.record_retrieval_for_query("Could you please help me?", v2_principal=principal)
    assert empty["node_ids"] == []
    assert empty["event_id"] == ""


def test_directives_remain_visible_for_queries_with_only_stopwords(stores):
    _, store, principal, _ = stores

    class Directives:
        def list_active(self, actor):
            assert actor == principal
            return [{"id": "explicit-owner-directive"}]

    from hermes.knowledge_retrieval_v2 import retrieve

    result = retrieve(store, principal, "Could you please help me?", directives=Directives())
    assert result == {"directives": [{"id": "explicit-owner-directive"}], "formal": [], "candidates": []}
