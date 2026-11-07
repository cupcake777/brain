from __future__ import annotations

import asyncio
import json
from pathlib import Path

from hermes.integrate import integrate
from hermes.integrate import recompute_confidence
from hermes.mcp_server import TOOLS, _execute_tool
from hermes.repository import HermesRepository


def _call(repo: HermesRepository, name: str, arguments: dict) -> dict:
    content = asyncio.run(_execute_tool(repo, name, arguments))
    assert len(content) == 1
    return json.loads(content[0].text)


def _seed(repo: HermesRepository) -> str:
    result = integrate(
        content="Inspect live configuration and logs before changing a provider.",
        source="test-seed",
        category="rule",
        domain="tech",
        evidence=["test://mcp-learning-loop/seed"],
        repo=repo,
    )
    repo.update_knowledge_node(result.node_id, stage="verified")
    return result.node_id


def test_mcp_retrieve_returns_candidate_ids_and_records_event(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    node_id = _seed(repo)

    tool_names = {tool.name for tool in TOOLS}
    assert "retrieve_knowledge" in tool_names

    result = _call(
        repo,
        "retrieve_knowledge",
        {
            "query": "provider configuration logs",
            "agent": "xiaohe",
            "host_id": "control-plane",
            "session_id": "session-a",
            "limit": 5,
        },
    )

    assert result["retrieval_id"]
    assert result["outcome_required"] is True
    assert any(item["node_id"] == node_id for item in result["results"])
    event = repo.get_retrieval_event(result["retrieval_id"])
    assert event is not None
    assert event.session_id == "session-a"
    assert event.host_id == "control-plane"


def test_mcp_outcome_records_feedback_for_returned_candidate(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    node_id = _seed(repo)
    retrieval = _call(
        repo,
        "retrieve_knowledge",
        {
            "query": "provider configuration logs",
            "agent": "xiaohe",
            "host_id": "control-plane",
            "session_id": "session-feedback",
        },
    )

    assert "report_knowledge_outcome" in {tool.name for tool in TOOLS}
    result = _call(
        repo,
        "report_knowledge_outcome",
        {
            "retrieval_id": retrieval["retrieval_id"],
            "node_id": node_id,
            "status": "applied",
            "note": "Live configuration was inspected before editing.",
        },
    )

    assert result == {
        "schema": 1,
        "recorded": 1,
        "retrieval_id": retrieval["retrieval_id"],
        "node_id": node_id,
        "status": "applied",
        "proposal_recommended": False,
    }
    stored = repo.get_knowledge_node(node_id)
    assert stored is not None
    assert stored.outcome_count == 1


def test_mcp_finalize_reports_complete_only_after_all_candidates_have_outcomes(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    node_id = _seed(repo)
    retrieval = _call(
        repo,
        "retrieve_knowledge",
        {
            "query": "provider configuration logs",
            "agent": "xiaohe",
            "host_id": "control-plane",
            "session_id": "session-finalize",
            "limit": 1,
        },
    )
    _call(
        repo,
        "report_knowledge_outcome",
        {
            "retrieval_id": retrieval["retrieval_id"],
            "node_id": node_id,
            "status": "not_used",
        },
    )

    assert "finalize_knowledge_session" in {tool.name for tool in TOOLS}
    result = _call(
        repo,
        "finalize_knowledge_session",
        {
            "agent": "xiaohe",
            "host_id": "control-plane",
            "session_id": "session-finalize",
        },
    )

    assert result["schema"] == 1
    assert result["final_result"] == "complete"
    assert result["retrieval_events"] == 1
    assert result["expected_outcomes"] == result["reported_outcomes"] == 1
    assert result["missing_pairs"] == []


def test_mcp_partial_help_is_a_terminal_positive_outcome(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    node_id = _seed(repo)
    retrieval = _call(
        repo,
        "retrieve_knowledge",
        {"query": "provider configuration logs", "session_id": "session-partial"},
    )

    result = _call(
        repo,
        "report_knowledge_outcome",
        {
            "retrieval_id": retrieval["retrieval_id"],
            "node_id": node_id,
            "status": "partially_helped",
        },
    )

    assert result["recorded"] == 1
    assert repo.get_knowledge_node(node_id).outcome_count == 1


def test_failed_outcome_does_not_become_positive_bonus_on_recompute(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    node_id = _seed(repo)
    before = repo.get_knowledge_node(node_id)
    assert before is not None
    baseline = recompute_confidence(before, repo)
    retrieval = _call(
        repo,
        "retrieve_knowledge",
        {"query": "provider configuration logs", "session_id": "session-failed"},
    )
    _call(
        repo,
        "report_knowledge_outcome",
        {
            "retrieval_id": retrieval["retrieval_id"],
            "node_id": node_id,
            "status": "failed",
        },
    )

    after = repo.get_knowledge_node(node_id)
    assert after is not None
    assert recompute_confidence(after, repo) <= baseline
