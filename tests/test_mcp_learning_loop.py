from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from hermes.event_store import Principal
from hermes.integrate import integrate
from hermes.integrate import recompute_confidence
from hermes.knowledge_store import KnowledgeStore
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


def test_mcp_retrieve_includes_checked_v2_candidate_without_legacy_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "brain.sqlite3"
    repo = HermesRepository(db)
    principal = Principal("xiaohe", "workspace-a", "brain")
    store = KnowledgeStore(db)
    row = store.create(
        principal,
        "Use narrative acceptance gates before compiling multi-deck presentations.",
        [],
    )
    with store.conn:
        store.conn.execute(
            "INSERT INTO brain_v2_knowledge_states VALUES (?, ?, 'candidate')",
            (row["id"], row["version"]),
        )
    store.close()
    monkeypatch.setenv("BRAIN_V2_ENABLED", "true")
    monkeypatch.setenv("BRAIN_V2_WORKSPACE", principal.workspace)
    monkeypatch.setenv("BRAIN_V2_PROJECT", principal.project)

    result = _call(
        repo,
        "retrieve_knowledge",
        {
            "query": "narrative acceptance gates multi-deck",
            "agent": principal.actor,
            "host_id": "control-plane",
            "session_id": "session-v2-candidate",
            "limit": 5,
        },
    )

    candidate = next(item for item in result["results"] if item["node_id"] == row["id"])
    assert candidate["stage"] == "candidate"
    assert candidate["unverified"] is True
    assert repo.get_knowledge_node(row["id"]) is None
    event = repo.get_retrieval_event(result["retrieval_id"])
    assert event is not None
    assert row["id"] in json.loads(event.node_ids)


def test_mcp_outcome_closes_v2_candidate_retrieval_without_promoting_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "brain.sqlite3"
    repo = HermesRepository(db)
    principal = Principal("xiaohe", "workspace-a", "brain")
    store = KnowledgeStore(db)
    row = store.create(principal, "Check narrative evidence before slide generation.", [])
    with store.conn:
        store.conn.execute(
            "INSERT INTO brain_v2_knowledge_states VALUES (?, ?, 'candidate')",
            (row["id"], row["version"]),
        )
    store.close()
    monkeypatch.setenv("BRAIN_V2_ENABLED", "true")
    monkeypatch.setenv("BRAIN_V2_WORKSPACE", principal.workspace)
    monkeypatch.setenv("BRAIN_V2_PROJECT", principal.project)

    retrieval = _call(
        repo,
        "retrieve_knowledge",
        {
            "query": "narrative evidence slide generation",
            "agent": principal.actor,
            "host_id": "control-plane",
            "session_id": "session-v2-outcome",
        },
    )
    outcome = _call(
        repo,
        "report_knowledge_outcome",
        {
            "retrieval_id": retrieval["retrieval_id"],
            "node_id": row["id"],
            "status": "not_used",
        },
    )
    finalized = _call(
        repo,
        "finalize_knowledge_session",
        {
            "agent": principal.actor,
            "host_id": "control-plane",
            "session_id": "session-v2-outcome",
        },
    )

    assert outcome["recorded"] == 1
    assert finalized["final_result"] == "complete"
    reopened = KnowledgeStore(db)
    assert reopened.get(principal, row["id"])["state"] == "candidate"
    reopened.close()


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


def test_mcp_retrieve_schema_requires_session_id() -> None:
    """The advertised JSON schema must make session_id mandatory.

    Without it, MCP clients (Hermes) omit session_id, retrievals get recorded
    with an empty session, and finalize_knowledge_session can never close the
    learning loop for them.
    """
    tool = next(t for t in TOOLS if t.name == "retrieve_knowledge")
    required = tool.inputSchema.get("required", [])
    assert "session_id" in required, (
        f"retrieve_knowledge schema must require session_id; required={required}"
    )
    assert not tool.inputSchema["properties"]["session_id"].get("default"), (
        "retrieve_knowledge session_id must not advertise a default"
    )


def test_mcp_retrieve_execution_rejects_missing_or_blank_session_id(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")

    for bad_arguments in (
        {"query": "provider configuration logs"},
        {"query": "provider configuration logs", "session_id": ""},
        {"query": "provider configuration logs", "session_id": "   "},
    ):
        with pytest.raises(ValueError, match="session_id"):
            _call(repo, "retrieve_knowledge", bad_arguments)


@pytest.mark.parametrize('limit', [1, 2])
def test_mixed_lanes_rank_v2_even_when_legacy_fills_limit(tmp_path, limit):
    repo = HermesRepository(tmp_path / 'mixed.sqlite3')
    legacy = [_seed(repo) for _ in range(3)]
    principal = Principal('tester', 'workspace', 'brain')
    store = KnowledgeStore(repo.db_path)
    row = store.create(principal, 'provider configuration logs diagnostics', [])
    other = store.create(Principal('other', 'private', 'brain'), 'provider configuration logs diagnostics', [])
    with store.conn:
        for node in (row, other):
            store.conn.execute("INSERT INTO brain_v2_knowledge_states VALUES (?, ?, 'candidate')", (node['id'], node['version']))
    store.close()
    result = repo.record_retrieval_for_query('provider configuration logs diagnostics', limit=limit, v2_principal=principal)
    assert result['node_ids'][0] == row['id']
    assert other['id'] not in result['node_ids']
    assert result['updated'] == limit - 1
    assert sum(repo.get_knowledge_node(n).retrieval_count for n in legacy) == limit - 1
    with repo._connect() as conn:
        mode = conn.execute('SELECT retrieval_mode FROM retrieval_log WHERE id=?', (result['event_id'],)).fetchone()[0]
    assert mode == ('v2' if limit == 1 else 'mixed')


def test_legacy_missing_session_call_writes_no_event(tmp_path):
    repo = HermesRepository(tmp_path / 'compat.sqlite3')
    _seed(repo)
    with pytest.raises(ValueError, match='^session_id is required$'):
        _call(repo, 'retrieve_knowledge', {'query': 'provider configuration logs'})
    with repo._connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM knowledge_retrieval_events').fetchone()[0] == 0
        assert connection.execute('SELECT COUNT(*) FROM retrieval_log').fetchone()[0] == 0
