from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class ExportRecord:
    scope_type: str
    project_key: str
    file_name: str
    rebuilt_at: str
    size_bytes: int


class HermesRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    source_agent TEXT NOT NULL,
                    source_host TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    project_key TEXT NOT NULL,
                    category TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    observation TEXT NOT NULL,
                    why_it_matters TEXT NOT NULL,
                    suggested_memory TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    state TEXT NOT NULL,
                    semantic_hash TEXT NOT NULL,
                    semantic_duplicate_of TEXT,
                    supersedes TEXT,
                    reviewer_priority REAL NOT NULL DEFAULT 1.0,
                    retrieval_count_30d INTEGER NOT NULL DEFAULT 0,
                    inserted_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS exports (
                    scope_type TEXT NOT NULL,
                    project_key TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    rebuilt_at TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    PRIMARY KEY (scope_type, project_key, file_name)
                );
                """
            )

    def has_proposal(self, proposal_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        return row is not None

    def find_by_semantic_hash(self, semantic_hash: str, *, excluding: str | None = None) -> str | None:
        query = "SELECT proposal_id FROM proposals WHERE semantic_hash = ?"
        params: list[str] = [semantic_hash]
        if excluding is not None:
            query += " AND proposal_id != ?"
            params.append(excluding)
        with self._connect() as connection:
            row = connection.execute(query, tuple(params)).fetchone()
        return None if row is None else str(row["proposal_id"])

    def insert_proposal(self, record: dict[str, str | int | float | None]) -> None:
        payload = dict(record)
        payload.setdefault("inserted_at", datetime.now(timezone.utc).isoformat())
        columns = ", ".join(payload)
        placeholders = ", ".join("?" for _ in payload)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO proposals ({columns}) VALUES ({placeholders})",
                tuple(payload.values()),
            )

    def get_proposal(self, proposal_id: str) -> dict[str, str | int | float | None]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return dict(row)

    def list_proposals_by_state(self, state: str) -> list[dict[str, str | int | float | None]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM proposals WHERE state = ? ORDER BY inserted_at ASC",
                (state,),
            ).fetchall()
        return [dict(row) for row in rows]

    def transition_state(self, proposal_id: str, state: str, *, supersedes: str | None = None) -> None:
        with self._connect() as connection:
            if supersedes is None:
                connection.execute(
                    "UPDATE proposals SET state = ? WHERE proposal_id = ?",
                    (state, proposal_id),
                )
            else:
                connection.execute(
                    "UPDATE proposals SET state = ?, supersedes = ? WHERE proposal_id = ?",
                    (state, supersedes, proposal_id),
                )

    def list_exportable(self, project_key: str | None = None) -> list[dict[str, str | int | float | None]]:
        query = "SELECT * FROM proposals WHERE state = 'approved_for_export'"
        params: list[str] = []
        if project_key is None:
            query += " AND scope = 'global'"
        else:
            query += " AND project_key = ?"
            params.append(project_key)
        query += " ORDER BY inserted_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_exportable_project_keys(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT project_key
                FROM proposals
                WHERE state = 'approved_for_export' AND scope != 'global'
                ORDER BY project_key ASC
                """
            ).fetchall()
        return [str(row["project_key"]) for row in rows]

    def record_export(
        self,
        *,
        scope_type: str,
        project_key: str,
        file_name: str,
        size_bytes: int,
        rebuilt_at: str | None = None,
    ) -> None:
        rebuilt = rebuilt_at or datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO exports (scope_type, project_key, file_name, rebuilt_at, size_bytes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(scope_type, project_key, file_name)
                DO UPDATE SET rebuilt_at = excluded.rebuilt_at, size_bytes = excluded.size_bytes
                """,
                (scope_type, project_key, file_name, rebuilt, size_bytes),
            )

    def list_export_records(self) -> list[ExportRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT scope_type, project_key, file_name, rebuilt_at, size_bytes FROM exports ORDER BY file_name ASC"
            ).fetchall()
        return [ExportRecord(**dict(row)) for row in rows]

    def counts_by_state(self) -> dict[str, int]:
        counts = {"pending": 0, "approved_db_only": 0, "approved_for_export": 0, "rejected": 0, "superseded": 0}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT state, COUNT(*) AS total FROM proposals GROUP BY state"
            ).fetchall()
        for row in rows:
            counts[str(row["state"])] = int(row["total"])
        return counts

    def oldest_pending_age_seconds(self) -> int | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT inserted_at FROM proposals WHERE state = 'pending' ORDER BY inserted_at ASC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        inserted = datetime.fromisoformat(str(row["inserted_at"]))
        return int((datetime.now(timezone.utc) - inserted).total_seconds())

    def delete_export(self, scope_type: str, project_key: str, file_name: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM exports WHERE scope_type = ? AND project_key = ? AND file_name = ?",
                (scope_type, project_key, file_name),
            )

    def update_retrieval_count(self, proposal_id: str, delta: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE proposals SET retrieval_count_30d = retrieval_count_30d + ? WHERE proposal_id = ?",
                (delta, proposal_id),
            )

    def count_proposals_by_state_for_project(self, project_key: str) -> dict[str, int]:
        counts = {"pending": 0, "approved_db_only": 0, "approved_for_export": 0, "rejected": 0, "superseded": 0}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT state, COUNT(*) AS total FROM proposals WHERE project_key = ? GROUP BY state",
                (project_key,),
            ).fetchall()
        for row in rows:
            counts[str(row["state"])] = int(row["total"])
        return counts

    def list_proposals_ordered_for_demotion(self, project_key: str | None = None) -> list[dict[str, str | int | float | None]]:
        if project_key is None:
            query = """
                SELECT * FROM proposals
                WHERE state = 'approved_for_export' AND scope = 'global'
                ORDER BY retrieval_count_30d ASC, inserted_at ASC
                """
            params: tuple = ()
        else:
            query = """
                SELECT * FROM proposals
                WHERE state = 'approved_for_export' AND project_key = ?
                ORDER BY retrieval_count_30d ASC, inserted_at ASC
                """
            params = (project_key,)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]
