"""Accepted proposals become draft knowledge only when intake runs.

The accept transition enqueues ``knowledge_intake`` and stops there.
``KnowledgeIntake.run_once`` is the consumer: one draft per accepted
proposal version, no candidate or formal promotion, no second node on
replay.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from hermes.event_store import EventStore, Principal, StaticPrincipalAdapter
from hermes.knowledge_intake import KnowledgeIntake


def _principal(actor="alice", workspace="ws-1", project="proj-1"):
    return StaticPrincipalAdapter(actor=actor, workspace=workspace, project=project)


def _utcnow() -> datetime:
    return datetime(2026, 10, 21, 3, 0, tzinfo=timezone.utc)


def _accept(store: EventStore):
    event_id = uuid4()
    proposal_id = uuid4()
    store.record_event(
        id=event_id,
        project_id="proj-1",
        agent_id="agent-x",
        occurred_at=_utcnow(),
        action="ran the validator",
        result="malformed output was rejected",
        source_refs=[],
        origin="hook",
        classification="production",
    )
    store.create_proposal(
        id=proposal_id,
        version=1,
        project_id="proj-1",
        agent_id="agent-x",
        occurred_at=_utcnow(),
        action="validate generated configuration",
        result="the validator rejected the malformed file",
        lesson="Run the validator before restarting the service.",
        draft=False,
        source_refs=[{"type": "execution", "id": event_id}],
    )
    receipt = store.transition_proposal(
        proposal_id=str(proposal_id),
        expected_version=1,
        to_state="accepted",
        note="human approval",
    )
    return proposal_id, event_id, receipt


def _knowledge_rows(store: EventStore) -> int:
    row = store._conn.execute(
        "SELECT count(*) FROM brain_v2_knowledge_revisions"
    ).fetchone()
    return int(row[0])


def test_intake_writes_one_draft_and_replay_reuses_it(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "intake.sqlite3", principal=_principal())
    proposal_id, event_id, receipt = _accept(store)
    assert receipt["workflow_state"] == "accepted"
    assert receipt["version"] == 2

    intake = KnowledgeIntake(store)
    principal = Principal("alice", "ws-1", "proj-1")
    assert intake.knowledge.list_current(principal) == []

    store.enqueue_durable_job(
        kind="knowledge_intake",
        payload={"proposal_id": str(proposal_id), "proposal_version": 2},
    )
    first = intake.run_once()
    assert first is not None
    assert first["state"] == "done"
    second = intake.run_once()
    assert second is not None
    assert second["state"] == "done"
    assert second["knowledge_id"] == first["knowledge_id"]
    assert intake.run_once() is None

    knowledge = intake.knowledge.get(principal, first["knowledge_id"])
    assert knowledge["content"] == "Run the validator before restarting the service."
    assert knowledge["state"] == "draft"
    assert knowledge["kind"] == "experience"
    assert knowledge["source_refs"] == [
        {"type": "execution", "id": str(event_id)}
    ]
    assert _knowledge_rows(store) == 1
    assert store._conn.execute(
        "SELECT count(*) FROM brain_v2_knowledge_states"
    ).fetchone()[0] == 0
    jobs = store.list_durable_jobs(kind="knowledge_intake")
    assert [job["state"] for job in jobs] == ["done", "done"]


def test_rejected_job_does_not_write_knowledge(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "intake.sqlite3", principal=_principal())
    event_id = uuid4()
    proposal_id = uuid4()
    store.record_event(
        id=event_id,
        project_id="proj-1",
        agent_id="agent-x",
        occurred_at=_utcnow(),
        action="inspected the failure",
        result="the failure was not reproducible",
        source_refs=[],
        origin="hook",
        classification="production",
    )
    store.create_proposal(
        id=proposal_id,
        version=1,
        project_id="proj-1",
        agent_id="agent-x",
        occurred_at=_utcnow(),
        action="keep the rejected note",
        result="review declined the lesson",
        lesson="Do not keep a lesson that review declined.",
        draft=False,
        source_refs=[{"type": "execution", "id": event_id}],
    )
    store.transition_proposal(
        proposal_id=str(proposal_id),
        expected_version=1,
        to_state="rejected",
        note="not reusable",
    )
    store.enqueue_durable_job(
        kind="knowledge_intake",
        payload={"proposal_id": str(proposal_id), "proposal_version": 2},
    )
    store.enqueue_durable_job(
        kind="knowledge_intake",
        payload={"proposal_id": str(proposal_id), "proposal_version": 1},
    )

    intake = KnowledgeIntake(store)
    rejected = intake.run_once()
    stale = intake.run_once()
    assert rejected == {"id": rejected["id"], "state": "failed"}
    assert stale == {"id": stale["id"], "state": "failed"}
    assert _knowledge_rows(store) == 0

    def error(job_id: str) -> str:
        return store._conn.execute(
            "SELECT error FROM durable_jobs WHERE id = ?", (job_id,)
        ).fetchone()[0]

    assert error(rejected["id"]) == "not_accepted"
    assert error(stale["id"]) == "version_mismatch"


def test_secret_lesson_is_rejected_without_a_knowledge_row(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "intake.sqlite3", principal=_principal())
    proposal_id = str(uuid4())
    event_id = str(uuid4())
    now = "2026-10-21T03:00:00+00:00"
    lesson = "token=abcd"
    store._conn.execute(
        """
        INSERT INTO proposal_current(id, version, digest, workflow_state, updated_at)
        VALUES (?, 1, 'digest', 'accepted', ?)
        """,
        (proposal_id, now),
    )
    store._conn.execute(
        """
        INSERT INTO proposal_revisions(
            id, version, project_id, agent_id, occurred_at, action, result,
            lesson, draft, source_refs, workflow_state, payload_digest,
            principal_actor, principal_workspace, principal_project, received_at
        ) VALUES (?, 1, 'proj-1', 'agent-x', ?, 'act', 'result', ?, 0, ?,
                  'accepted', 'digest', 'alice', 'ws-1', 'proj-1', ?)
        """,
        (proposal_id, now, lesson, json.dumps([{"type": "execution", "id": event_id}]), now),
    )
    store._conn.execute(
        """
        INSERT INTO durable_jobs(
            id, kind, payload, state, enqueued_at,
            principal_actor, principal_workspace, principal_project
        ) VALUES ('job-secret', 'knowledge_intake', ?, 'queued', ?,
                  'alice', 'ws-1', 'proj-1')
        """,
        (json.dumps({"proposal_id": proposal_id, "proposal_version": 1}), now),
    )
    store._conn.commit()

    outcome = KnowledgeIntake(store).run_once()
    assert outcome == {"id": "job-secret", "state": "failed"}
    assert _knowledge_rows(store) == 0
    error = store._conn.execute(
        "SELECT error FROM durable_jobs WHERE id = 'job-secret'"
    ).fetchone()[0]
    assert error == "sensitive"
    assert lesson not in error


def test_other_scope_job_stays_queued(tmp_path: Path) -> None:
    db = tmp_path / "intake.sqlite3"
    owner = EventStore(db, principal=_principal())
    proposal_id, _event_id, _receipt = _accept(owner)
    other = EventStore(db, principal=_principal(actor="bob", workspace="ws-b", project="proj-b"))

    assert KnowledgeIntake(other).run_once() is None
    owner_jobs = owner.list_durable_jobs(kind="knowledge_intake")
    assert len(owner_jobs) == 1
    assert owner_jobs[0]["state"] == "queued"
    assert owner_jobs[0]["payload"]["proposal_id"] == str(proposal_id)

    done = KnowledgeIntake(owner).run_once()
    assert done is not None and done["state"] == "done"
    assert _knowledge_rows(owner) == 1
