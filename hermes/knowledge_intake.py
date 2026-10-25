"""Consume accepted-proposal intake jobs into draft knowledge.

Accepting a proposal only enqueues ``knowledge_intake``. This worker is
the consumer. It writes one draft experience revision for the accepted
lesson and its source refs, then marks the job done. It does not promote
that draft to candidate or formal, and it does not touch any other job
kind. A second run for the same proposal version reuses the first
knowledge id.
"""

from __future__ import annotations

from typing import Any

from hermes.contracts import SourceRef
from hermes.event_store import (
    ConflictError,
    EventStore,
    SensitiveRejectedError,
    _deserialise,
    _now_utc,
)
from hermes.knowledge_store import KnowledgeStore


JOB_KIND = "knowledge_intake"

_LINK_DDL = """
CREATE TABLE IF NOT EXISTS proposal_knowledge_intake (
    principal_workspace TEXT NOT NULL,
    principal_project TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    proposal_version INTEGER NOT NULL,
    knowledge_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (
        principal_workspace, principal_project, proposal_id, proposal_version
    )
)
"""


class KnowledgeIntake:
    """One principal scope, one queued job per ``run_once`` call."""

    def __init__(self, events: EventStore) -> None:
        self.events = events
        self.knowledge = KnowledgeStore(events.db_path, connection=events._conn)

    def run_once(self) -> dict[str, Any] | None:
        principal = self.events._resolve_principal()
        conn = self.events._conn
        self._ensure_schema(conn)
        job = conn.execute(
            """
            SELECT id, payload FROM durable_jobs
            WHERE kind = ? AND state = 'queued'
              AND principal_workspace = ? AND principal_project = ?
            ORDER BY enqueued_at ASC, id ASC
            LIMIT 1
            """,
            (JOB_KIND, principal.workspace, principal.project),
        ).fetchone()
        if job is None:
            return None

        with conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT state FROM durable_jobs WHERE id = ?",
                (job["id"],),
            ).fetchone()
            if current is None or current["state"] != "queued":
                return None

            reason, revision, refs = self._prepare(
                conn, principal, _deserialise(job["payload"])
            )
            if reason is not None:
                self._finish(conn, job["id"], "failed", error=reason)
                return {"id": job["id"], "state": "failed"}

            assert revision is not None and refs is not None
            existing = conn.execute(
                """
                SELECT knowledge_id FROM proposal_knowledge_intake
                WHERE principal_workspace = ? AND principal_project = ?
                  AND proposal_id = ? AND proposal_version = ?
                """,
                (
                    principal.workspace,
                    principal.project,
                    revision["proposal_id"],
                    revision["version"],
                ),
            ).fetchone()
            if existing is not None:
                self._finish(conn, job["id"], "done")
                return {
                    "id": job["id"],
                    "state": "done",
                    "knowledge_id": existing["knowledge_id"],
                }

            try:
                created = self.knowledge.create(
                    principal, revision["lesson"], refs
                )
            except SensitiveRejectedError:
                self._finish(conn, job["id"], "failed", error="sensitive")
                return {"id": job["id"], "state": "failed"}
            except ValueError:
                self._finish(conn, job["id"], "failed", error="invalid_lesson")
                return {"id": job["id"], "state": "failed"}

            conn.execute(
                """
                INSERT INTO proposal_knowledge_intake(
                    principal_workspace, principal_project, proposal_id,
                    proposal_version, knowledge_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    principal.workspace,
                    principal.project,
                    revision["proposal_id"],
                    revision["version"],
                    created["id"],
                    _now_utc().isoformat(),
                ),
            )
            self._finish(conn, job["id"], "done")
            return {
                "id": job["id"],
                "state": "done",
                "knowledge_id": created["id"],
            }

    def _ensure_schema(self, conn) -> None:
        if conn.in_transaction:
            conn.commit()
        conn.execute(_LINK_DDL)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(durable_jobs)")}
        if "error" not in columns:
            conn.execute("ALTER TABLE durable_jobs ADD COLUMN error TEXT")
        conn.commit()

    def _prepare(self, conn, principal, payload: Any):
        if not isinstance(payload, dict):
            return "missing_proposal", None, None
        proposal_id = payload.get("proposal_id")
        version = payload.get("proposal_version")
        if not isinstance(proposal_id, str) or not proposal_id:
            return "missing_proposal", None, None
        if type(version) is not int or version < 1:
            return "version_mismatch", None, None

        row = conn.execute(
            """
            SELECT pr.version, pr.lesson, pr.source_refs, pr.workflow_state,
                   pc.version AS current_version,
                   pc.workflow_state AS current_state
            FROM proposal_revisions pr
            JOIN proposal_current pc ON pc.id = pr.id
            WHERE pr.id = ? AND pr.version = ?
              AND pr.principal_workspace = ? AND pr.principal_project = ?
            """,
            (proposal_id, version, principal.workspace, principal.project),
        ).fetchone()
        if row is None:
            return "missing_proposal", None, None
        if int(row["current_version"]) != version:
            return "version_mismatch", None, None
        if row["workflow_state"] != "accepted" or row["current_state"] != "accepted":
            return "not_accepted", None, None
        lesson = row["lesson"]
        if not isinstance(lesson, str) or not lesson.strip():
            return "missing_lesson", None, None
        refs = _deserialise(row["source_refs"]) or []
        if not isinstance(refs, list) or not any(
            isinstance(ref, dict) and ref.get("type") == "execution" for ref in refs
        ):
            return "missing_evidence", None, None
        try:
            for ref in refs:
                SourceRef.model_validate(ref)
        except ValueError:
            return "invalid_evidence", None, None
        revision = {"proposal_id": proposal_id, "version": version, "lesson": lesson}
        return None, revision, refs

    def _finish(self, conn, job_id: str, state: str, *, error: str | None = None) -> None:
        changed = conn.execute(
            """
            UPDATE durable_jobs
            SET state = ?, error = ?
            WHERE id = ? AND state = 'queued'
            """,
            (state, error, job_id),
        )
        if changed.rowcount != 1:
            raise ConflictError("intake job changed concurrently")
