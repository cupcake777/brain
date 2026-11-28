"""Explicit provenance for learning-loop telemetry; unknown history stays unknown."""
from __future__ import annotations

REQUEST_SCHEMA = """CREATE TABLE IF NOT EXISTS brain_retrieval_requests (
 id TEXT PRIMARY KEY, event_id TEXT NOT NULL, traffic_kind TEXT NOT NULL,
 session_id TEXT NOT NULL, task_id TEXT NOT NULL, environment TEXT NOT NULL,
 created_at TEXT NOT NULL);"""

TRAFFIC_KINDS = ("task", "audit", "probe", "evaluation", "unknown")
TASK_RESULTS = ("success", "failure", "partial", "unknown")


def validate_provenance(traffic_kind="unknown", task_id="", session_id=""):
    if not isinstance(traffic_kind, str) or traffic_kind not in TRAFFIC_KINDS:
        raise ValueError(f"traffic_kind must be one of {TRAFFIC_KINDS}")
    if not isinstance(task_id, str) or len(task_id) > 200:
        raise ValueError("task_id must be a string of at most 200 characters")
    if traffic_kind == "task" and not str(session_id).strip():
        raise ValueError("session_id is required for task traffic")
    return traffic_kind, task_id.strip()


def validate_verification(task_success="unknown", user_validated=None, verification_note=""):
    if not isinstance(task_success, str) or task_success not in TASK_RESULTS:
        raise ValueError(f"task_success must be one of {TASK_RESULTS}")
    if user_validated is not None and not isinstance(user_validated, bool):
        raise ValueError("user_validated must be a boolean or null")
    if not isinstance(verification_note, str) or len(verification_note) > 2000:
        raise ValueError("verification_note must be a string of at most 2000 characters")
    return task_success, user_validated, verification_note.strip()


def feedback_metrics(connection):
    """Count requests and feedback separately; never label self-report a causal gain."""
    groups = []
    for kind in TRAFFIC_KINDS:
        retrievals = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(session_id<>''),0), COUNT(DISTINCT NULLIF(task_id,'')), "
            "COALESCE(SUM(event_id=''),0) FROM ("
            "SELECT event_id,session_id,task_id,traffic_kind FROM brain_retrieval_requests UNION ALL "
            "SELECT id,session_id,task_id,traffic_kind FROM knowledge_retrieval_events e "
            "WHERE NOT EXISTS (SELECT 1 FROM brain_retrieval_requests r WHERE r.event_id=e.id)) "
            "WHERE traffic_kind=?", (kind,),
        ).fetchone()
        outcomes = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(o.task_success<>'unknown'),0), "
            "COALESCE(SUM(o.user_validated=1),0), COALESCE(SUM(o.verification_note<>''),0) "
            "FROM outcome_log o JOIN knowledge_retrieval_events r ON r.id=o.retrieval_log_id "
            "WHERE r.traffic_kind=?", (kind,),
        ).fetchone()
        groups.append(dict(traffic_kind=kind, retrieval_requests=retrievals[0],
                           with_session=retrievals[1], task_ids=retrievals[2], empty_retrieval_requests=retrievals[3],
                           candidate_outcomes=outcomes[0], task_result_reports=outcomes[1],
                           user_validated_reports=outcomes[2], with_verification_note=outcomes[3]))
    return {"schema": 1, "groups": groups,
            "interpretation": "Caller reports and evidence notes; not independently verified task gains. "
                              "Historical unclassified traffic stays unknown. Empty requests are counted separately; historical empty requests were not recorded."}
