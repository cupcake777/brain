from __future__ import annotations

import json

import pytest

from hermes.feedback_attribution import feedback_metrics
from hermes.integrate import integrate
from hermes.repository import HermesRepository
from tests.test_brain_protocol import client_with_token
from tests.test_mcp_learning_loop import _call


def seed(repo):
    node = integrate(content="Preserve session identifiers for feedback attribution.", source="test",
                     category="rule", domain="tech", evidence=["test://attribution"], repo=repo)
    repo.update_knowledge_node(node.node_id, stage="verified")
    return node.node_id


def test_mcp_records_actual_verification_and_separates_traffic(tmp_path):
    repo = HermesRepository(tmp_path / "db")
    node = seed(repo)
    for kind in ("task", "audit", "probe", "evaluation"):
        result = _call(repo, "retrieve_knowledge", {
            "query": "session identifiers feedback", "session_id": "actual-session",
            "traffic_kind": kind, "task_id": "issue-42" if kind == "task" else "",
        })
        assert result["results"][0]["node_id"] == node
        outcome = _call(repo, "report_knowledge_outcome", {
            "retrieval_id": result["retrieval_id"], "node_id": node, "status": "applied",
            "task_success": "success", "user_validated": False,
            "verification_note": "Acceptance command exited 0; user has not reviewed.",
        })
        assert outcome["recorded"] == 1
    with repo._connect() as connection:
        rows = feedback_metrics(connection)["groups"]
        saved = connection.execute("SELECT verification_note,user_validated FROM outcome_log").fetchall()
    assert all(row[0].startswith("Acceptance command") and row[1] == 0 for row in saved)
    for row in rows:
        if row["traffic_kind"] != "unknown":
            assert row["retrieval_requests"] == row["task_result_reports"] == row["with_verification_note"] == 1
            assert row["user_validated_reports"] == 0
            assert row["task_ids"] == (1 if row["traffic_kind"] == "task" else 0)


def test_http_provenance_validation_and_owner_metrics(tmp_path):
    client, repo, _ = client_with_token(tmp_path)
    seed(repo)
    headers = {"Authorization": "Bearer test-token"}
    body = {"query": "session identifiers feedback", "traffic_kind": "task", "task_id": "issue-42"}
    assert client.post("/api/v1/brain/retrieve", headers=headers, json=body).status_code == 400
    for invalid in ["", "production", [], None]:
        assert client.post("/api/v1/brain/retrieve", headers=headers,
                           json={**body, "session_id": "actual", "traffic_kind": invalid}).status_code == 400
    response = client.post("/api/v1/brain/retrieve", headers=headers,
                           json={**body, "session_id": "actual"}).json()
    event = repo.get_retrieval_event(response["retrieval_id"])
    assert (event.traffic_kind, event.task_id) == ("task", "issue-42")
    metrics = client.get("/api/v1/brain/metrics", headers=headers)
    assert metrics.status_code == 200
    assert next(g for g in metrics.json()["groups"] if g["traffic_kind"] == "task")["retrieval_requests"] == 1
    assert client.get("/api/v1/brain/metrics").status_code == 401


def test_telemetry_migration_preserves_unclassified_history(tmp_path):
    path = tmp_path / "db"
    repo = HermesRepository(path)
    node = seed(repo)
    result = repo.record_retrieval_for_query("session identifiers feedback")
    repo.record_outcome_pair(result["event_id"], node, "not_used", used=False)
    with repo._connect() as connection:
        before = dict(connection.execute("SELECT * FROM outcome_log").fetchone())
        for table, column in [("knowledge_retrieval_events", "traffic_kind"),
                              ("knowledge_retrieval_events", "task_id"), ("outcome_log", "verification_note")]:
            connection.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    repo = HermesRepository(path)
    with repo._connect() as connection:
        after = dict(connection.execute("SELECT * FROM outcome_log").fetchone())
        assert after == before
        event = connection.execute("SELECT traffic_kind,task_id FROM knowledge_retrieval_events").fetchone()
        assert tuple(event) == ("unknown", "")
        assert next(g for g in feedback_metrics(connection)["groups"] if g["traffic_kind"] == "unknown")["retrieval_requests"] == 1


@pytest.mark.parametrize("fields", [{"task_success": True}, {"user_validated": "yes"}, {"verification_note": []}])
def test_mcp_rejects_invalid_verification_before_writing(tmp_path, fields):
    repo = HermesRepository(tmp_path / "db")
    node = seed(repo)
    result = repo.record_retrieval_for_query("session identifiers feedback", session_id="real")
    with pytest.raises(ValueError):
        _call(repo, "report_knowledge_outcome", {"retrieval_id": result["event_id"], "node_id": node,
                                               "status": "applied", **fields})
    with repo._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM outcome_log").fetchone()[0] == 0


def test_empty_requests_count_without_creating_outcome_candidates(tmp_path):
    repo=HermesRepository(tmp_path/'db')
    result=repo.record_retrieval_for_query('no known experience',session_id='actual',traffic_kind='task')
    assert result['event_id']=='' and result['node_ids']==[]
    with repo._connect() as connection:
        metrics=next(g for g in feedback_metrics(connection)['groups'] if g['traffic_kind']=='task')
        assert metrics['retrieval_requests']==metrics['empty_retrieval_requests']==1
        assert metrics['candidate_outcomes']==0
        assert connection.execute('SELECT COUNT(*) FROM knowledge_retrieval_events').fetchone()[0]==0


def test_migration_uses_host_evidence_and_preserves_actual_session(tmp_path):
    repo=HermesRepository(tmp_path/'db')
    seed(repo)
    event=repo.record_retrieval_for_query('session identifiers feedback',agent='codex',host='server-a',session_id='actual')
    with repo._connect() as connection:
        connection.execute("UPDATE knowledge_retrieval_events SET host_id='codex' WHERE id=?",(event['event_id'],))
        connection.execute("UPDATE retrieval_log SET session_id='different' WHERE id=?",(event['event_id'],))
    repo=HermesRepository(tmp_path/'db')
    saved=repo.get_retrieval_event(event['event_id'])
    assert saved.host_id=='server-a' and saved.session_id=='actual'
    with repo._connect() as connection:
        connection.execute("UPDATE knowledge_retrieval_events SET host_id='',host='',session_id='' WHERE id=?",(event['event_id'],))
    repo=HermesRepository(tmp_path/'db')
    saved=repo.get_retrieval_event(event['event_id'])
    assert saved.host_id=='' and saved.session_id=='different'
