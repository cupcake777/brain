from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


def _reduce_outcomes_safe(observations):
    """Module-level shim around hermes.outcomes.reduce_outcomes.

    Importing at module top-level can cause circular imports during test
    collection (some fixtures import ``repository`` before ``outcomes`` is
    fully wired).  This wrapper makes the late-bound import explicit.
    """
    from hermes.outcomes import reduce_outcomes as _reduce

    return _reduce(observations)


@dataclass(frozen=True)
class ExportRecord:
    scope_type: str
    project_key: str
    file_name: str
    rebuilt_at: str
    size_bytes: int


@dataclass(frozen=True)
class KnowledgeNode:
    """V2 knowledge node with lifecycle stages and provenance."""
    id: str
    parent_id: str | None
    content: str
    summary: str
    category: str  # rule/workflow/preference/fact
    domain: str  # apa/devops/network/general/...
    stage: str  # draft/refined/verified/canonized/deprecated
    operation: str  # draft/refine/debug/merge/supersede
    confidence: float  # 0.0-1.0 dynamic
    source: str  # "conversation:session_id" / "reflection" / "user_direct"
    evidence: str  # JSON array
    supersedes: str | None
    merged_from: str  # JSON array of node IDs
    contradicts: str  # JSON array of node IDs
    verified_by: str  # JSON array of sources
    created_at: str
    refined_at: str | None
    verified_at: str | None
    deprecated_at: str | None
    retrieval_count: int
    last_used_at: str | None
    correction_count: int
    outcome_count: int
    last_outcome_at: str | None
    kind: str
    trigger_terms: str
    use_when: str
    avoid_when: str
    success_signal: str
    failure_signal: str




@dataclass(frozen=True)
class KnowledgeRetrievalEvent:
    id: str
    query: str
    agent: str
    host: str
    node_ids: str
    created_at: str
    outcome_recorded_at: str | None = None
    session_id: str = ""
    host_id: str = ""
    finalized_at: str | None = None
    final_result: str | None = None


@dataclass(frozen=True)
class ThoughtChain:
    """Reasoning trace for a knowledge integration decision."""
    id: str
    node_id: str
    action: str  # dedup_check/merge/refine/contradiction_detect/canonize
    reasoning: str
    evidence_used: str  # JSON array of node IDs
    decision: str  # create/merge/ignore/refine/flag_contradiction
    confidence_in_decision: float  # 0.0-1.0
    created_at: str


class HermesRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        # review: SQLite FKs are off by default per connection
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_db(self) -> None:
        # Backend stage-1 migration: extend production tables in-place to
        # carry explicit session/host scoping WITHOUT dropping existing rows.
        # Production DB has knowledge_retrieval_events without session_id/host_id
        # and outcome_log without a uniqueness constraint on (retrieval_log_id,
        # memory_id). Both are added as ALTER TABLE best-effort migrations
        # that preserve all 43 retrieval events and 2 outcome rows.
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
                    weight REAL NOT NULL DEFAULT 1.0,
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
            # -- V2 tables: knowledge_nodes and thought_chains --
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_nodes (
                    id TEXT PRIMARY KEY,
                    parent_id TEXT,
                    content TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'fact',
                    domain TEXT NOT NULL DEFAULT 'general',
                    stage TEXT NOT NULL DEFAULT 'draft',
                    operation TEXT NOT NULL DEFAULT 'draft',
                    confidence REAL NOT NULL DEFAULT 0.3,
                    source TEXT NOT NULL,
                    evidence TEXT DEFAULT '[]',
                    supersedes TEXT,
                    merged_from TEXT DEFAULT '[]',
                    contradicts TEXT DEFAULT '[]',
                    verified_by TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    refined_at TEXT,
                    verified_at TEXT,
                    deprecated_at TEXT,
                    retrieval_count INTEGER NOT NULL DEFAULT 0,
                    last_used_at TEXT,
                    correction_count INTEGER NOT NULL DEFAULT 0,
                    outcome_count INTEGER NOT NULL DEFAULT 0,
                    last_outcome_at TEXT,
                    kind TEXT NOT NULL DEFAULT 'fact',
                    trigger_terms TEXT NOT NULL DEFAULT '[]',
                    use_when TEXT NOT NULL DEFAULT '',
                    avoid_when TEXT NOT NULL DEFAULT '',
                    success_signal TEXT NOT NULL DEFAULT '',
                    failure_signal TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_kn_stage ON knowledge_nodes(stage);
                CREATE INDEX IF NOT EXISTS idx_kn_category ON knowledge_nodes(category);
                CREATE INDEX IF NOT EXISTS idx_kn_domain ON knowledge_nodes(domain);
                CREATE INDEX IF NOT EXISTS idx_kn_parent ON knowledge_nodes(parent_id);
                CREATE INDEX IF NOT EXISTS idx_kn_supersedes ON knowledge_nodes(supersedes);

                CREATE TABLE IF NOT EXISTS thought_chains (
                    id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    evidence_used TEXT DEFAULT '[]',
                    decision TEXT NOT NULL,
                    confidence_in_decision REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (node_id) REFERENCES knowledge_nodes(id)
                );

                CREATE INDEX IF NOT EXISTS idx_tc_node ON thought_chains(node_id);
                CREATE INDEX IF NOT EXISTS idx_tc_node ON thought_chains(node_id);
                CREATE INDEX IF NOT EXISTS idx_tc_action ON thought_chains(action);

                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_nodes_fts USING fts5(
                    id UNINDEXED,
                    summary,
                    content,
                    category,
                    domain
                );

                CREATE TABLE IF NOT EXISTS entity_embeddings (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dimension INTEGER NOT NULL DEFAULT 0,
                    vector BLOB,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (entity_type, entity_id)
                );
                CREATE INDEX IF NOT EXISTS idx_embeddings_status
                    ON entity_embeddings(entity_type, status);

                CREATE TABLE IF NOT EXISTS proposal_knowledge_links (
                    proposal_id TEXT PRIMARY KEY,
                    knowledge_id TEXT NOT NULL,
                    sync_action TEXT NOT NULL DEFAULT 'created',
                    synced_at TEXT NOT NULL,
                    FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id),
                    FOREIGN KEY (knowledge_id) REFERENCES knowledge_nodes(id)
                );
                CREATE INDEX IF NOT EXISTS idx_pkl_knowledge
                    ON proposal_knowledge_links(knowledge_id);
                """

            )
            # -- V3 tables: observations, memory_edges, retrieval_log, outcome_log --
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    source_span TEXT NOT NULL DEFAULT '',
                    quoted_excerpt TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL DEFAULT '',
                    proposal_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_obs_proposal ON observations(proposal_id);
                CREATE INDEX IF NOT EXISTS idx_obs_hash ON observations(content_hash);

                CREATE TABLE IF NOT EXISTS memory_edges (
                    from_id TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    evidence_id TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (from_id, to_id, edge_type)
                );
                CREATE INDEX IF NOT EXISTS idx_me_from ON memory_edges(from_id);
                CREATE INDEX IF NOT EXISTS idx_me_to ON memory_edges(to_id);
                CREATE INDEX IF NOT EXISTS idx_me_type ON memory_edges(edge_type);

                CREATE TABLE IF NOT EXISTS knowledge_retrieval_events (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    agent TEXT NOT NULL DEFAULT '',
                    host TEXT NOT NULL DEFAULT '',
                    node_ids TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    outcome_recorded_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_kre_created ON knowledge_retrieval_events(created_at);

                CREATE TABLE IF NOT EXISTS retrieval_log (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    retrieval_mode TEXT NOT NULL DEFAULT 'fts5',
                    candidate_ids TEXT NOT NULL DEFAULT '[]',
                    selected_ids TEXT NOT NULL DEFAULT '[]',
                    used_ids TEXT NOT NULL DEFAULT '[]',
                    agent TEXT NOT NULL DEFAULT '',
                    session_id TEXT NOT NULL DEFAULT '',
                    task_context TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rl_agent ON retrieval_log(agent);
                CREATE INDEX IF NOT EXISTS idx_rl_session ON retrieval_log(session_id);
                CREATE INDEX IF NOT EXISTS idx_rl_created ON retrieval_log(created_at);

                CREATE TABLE IF NOT EXISTS outcome_log (
                    id TEXT PRIMARY KEY,
                    retrieval_log_id TEXT NOT NULL,
                    memory_id TEXT NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,
                    helpfulness TEXT NOT NULL DEFAULT 'unknown',
                    user_validated INTEGER,
                    task_success TEXT NOT NULL DEFAULT 'unknown',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ol_retrieval ON outcome_log(retrieval_log_id);
                CREATE INDEX IF NOT EXISTS idx_ol_memory ON outcome_log(memory_id);
                CREATE INDEX IF NOT EXISTS idx_ol_helpfulness ON outcome_log(helpfulness);
                """
            )

            # -- Migrations: add columns if missing (pre-existing DBs) --
            for sql in (
                "ALTER TABLE proposals ADD COLUMN weight REAL NOT NULL DEFAULT 1.0",
                "ALTER TABLE knowledge_nodes ADD COLUMN outcome_count INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE knowledge_nodes ADD COLUMN last_outcome_at TEXT",
                "ALTER TABLE knowledge_nodes ADD COLUMN kind TEXT NOT NULL DEFAULT 'fact'",
                "ALTER TABLE knowledge_nodes ADD COLUMN trigger_terms TEXT NOT NULL DEFAULT '[]'",
                "ALTER TABLE knowledge_nodes ADD COLUMN use_when TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE knowledge_nodes ADD COLUMN avoid_when TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE knowledge_nodes ADD COLUMN success_signal TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE knowledge_nodes ADD COLUMN failure_signal TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE proposals ADD COLUMN domain TEXT NOT NULL DEFAULT ''",
            ):
                try:
                    connection.execute(sql)
                except Exception:
                    pass  # Column already exists
        self._migrate_stage1_schema()

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

    # Column whitelist to prevent SQL injection via dict keys
    _ALLOWED_COLUMNS = frozenset({
        "proposal_id", "source_agent", "source_host", "created_at",
        "project_key", "category", "risk_level", "domain", "summary", "observation",
        "why_it_matters", "suggested_memory", "scope", "evidence", "state",
        "semantic_hash", "semantic_duplicate_of", "supersedes", "weight",
        "reviewer_priority", "retrieval_count_30d", "inserted_at",
    })

    def insert_proposal(self, record: dict[str, str | int | float | None]) -> None:
        payload = {k: v for k, v in record.items() if k in self._ALLOWED_COLUMNS}
        if not payload:
            raise ValueError("No valid columns in proposal record")
        payload.setdefault("inserted_at", datetime.now(timezone.utc).isoformat())
        columns = ", ".join(payload)
        placeholders = ", ".join("?" for _ in payload)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO proposals ({columns}) VALUES ({placeholders})",
                tuple(payload.values()),
            )
        proposal_id = str(payload.get("proposal_id") or "")
        if proposal_id:
            self.refresh_entity_embedding(
                "proposal",
                proposal_id,
                self._proposal_embedding_text(payload),
                raise_errors=False,
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

    def relabel_lanes(self, *, dry_run: bool = False) -> dict[str, object]:
        """Rewrite proposal/knowledge domain to scene slugs.  Custom labels are kept."""
        from hermes.lane import assign_lane, lane_text

        proposal_changes: list[tuple[str, str, str]] = []
        knowledge_changes: list[tuple[str, str, str]] = []
        with self._connect() as connection:
            for row in connection.execute("SELECT * FROM proposals"):
                old = str(row["domain"] or "")
                new = assign_lane(
                    hinted=old,
                    project_key=row["project_key"],
                    text=lane_text(row["summary"], row["observation"], row["suggested_memory"]),
                )
                if new != old:
                    proposal_changes.append((str(row["proposal_id"]), old, new))
            knowledge_rows = list(connection.execute(
                "SELECT id, domain, summary, content, category FROM knowledge_nodes"
            ))
            for row in knowledge_rows:
                old = str(row["domain"] or "")
                new = assign_lane(hinted=old, text=lane_text(row["summary"], row["content"]))
                if new != old:
                    knowledge_changes.append((str(row["id"]), old, new, str(row["summary"]), str(row["content"]), str(row["category"])))
            if not dry_run:
                for pid, _old, new in proposal_changes:
                    connection.execute("UPDATE proposals SET domain = ? WHERE proposal_id = ?", (new, pid))
                for nid, _old, new, summary, content, category in knowledge_changes:
                    connection.execute("UPDATE knowledge_nodes SET domain = ? WHERE id = ?", (new, nid))
                    try:
                        connection.execute(
                            "INSERT OR REPLACE INTO knowledge_nodes_fts (id, summary, content, category, domain) VALUES (?, ?, ?, ?, ?)",
                            (nid, summary, content, category, new),
                        )
                    except sqlite3.OperationalError:
                        pass
        from collections import Counter
        return {
            "proposals_updated": len(proposal_changes),
            "knowledge_updated": len(knowledge_changes),
            "proposal_to": dict(Counter(new for _pid, _old, new in proposal_changes)),
            "knowledge_to": dict(Counter(new for _nid, _old, new, *_rest in knowledge_changes)),
            "dry_run": dry_run,
        }

    def insert_observations(self, observations: list[dict]) -> None:
        """Insert observation rows (immutable evidence for proposals)."""
        if not observations:
            return
        with self._connect() as connection:
            connection.executemany(
                """INSERT OR IGNORE INTO observations
                   (id, content, source_type, source_uri, source_span,
                    quoted_excerpt, content_hash, proposal_id, created_at)
                   VALUES (:id, :content, :source_type, :source_uri, :source_span,
                           :quoted_excerpt, :content_hash, :proposal_id, :created_at)""",
                observations,
            )

    def insert_memory_edge(
        self, from_id: str, to_id: str, edge_type: str,
        evidence_id: str | None = None,
    ) -> None:
        """Create a lineage edge between two memory nodes."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO memory_edges
                   (from_id, to_id, edge_type, evidence_id, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (from_id, to_id, edge_type, evidence_id, now),
            )

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

    def get_proposal_knowledge_link(self, proposal_id: str) -> dict[str, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT proposal_id, knowledge_id, sync_action, synced_at FROM proposal_knowledge_links WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        return dict(row) if row else None

    def link_proposal_knowledge(self, proposal_id: str, knowledge_id: str, *, action: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO proposal_knowledge_links (proposal_id, knowledge_id, sync_action, synced_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(proposal_id) DO UPDATE SET
                     knowledge_id=excluded.knowledge_id,
                     sync_action=excluded.sync_action,
                     synced_at=excluded.synced_at""",
                (proposal_id, knowledge_id, action, now),
            )

    def find_legacy_proposal_knowledge(self, proposal_id: str) -> str | None:
        """Resolve V2 nodes created before explicit Proposal↔Knowledge links."""
        with self._connect() as connection:
            exact = connection.execute(
                "SELECT id FROM knowledge_nodes WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            if exact:
                return str(exact["id"])
            source = connection.execute(
                "SELECT id FROM knowledge_nodes WHERE source = ? ORDER BY created_at LIMIT 1",
                (f"proposal:{proposal_id[:12]}",),
            ).fetchone()
        return str(source["id"]) if source else None

    def proposal_sync_status(self) -> dict[str, object]:
        """Return approved Proposal→Knowledge materialization coverage."""
        with self._connect() as connection:
            approved = int(connection.execute(
                "SELECT COUNT(*) FROM proposals WHERE state IN ('approved_db_only','approved_for_export')"
            ).fetchone()[0])
            linked = int(connection.execute(
                """SELECT COUNT(*) FROM proposal_knowledge_links pkl
                   JOIN proposals p ON p.proposal_id = pkl.proposal_id
                   JOIN knowledge_nodes kn ON kn.id = pkl.knowledge_id
                   WHERE p.state IN ('approved_db_only','approved_for_export')"""
            ).fetchone()[0])
            latest = connection.execute(
                "SELECT MAX(synced_at) FROM proposal_knowledge_links"
            ).fetchone()[0]
        missing = max(0, approved - linked)
        return {
            "approved": approved,
            "linked": linked,
            "missing": missing,
            "coverage": round((linked / approved * 100.0) if approved else 100.0, 1),
            "last_synced_at": str(latest or ""),
            "state": "healthy" if missing == 0 else "syncing",
        }

    def list_exportable(self, project_key: str | None = None) -> list[dict[str, str | int | float | None]]:
        query = "SELECT * FROM proposals WHERE state = 'approved_for_export'"
        params: list[str] = []
        if project_key is None:
            query += " AND scope = 'global'"
        else:
            query += " AND project_key = ?"
            params.append(project_key)
        query += " ORDER BY weight DESC, inserted_at DESC"
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

    def update_weight(self, proposal_id: str, weight: float) -> None:
        """Set the weight of a proposal. Weight is a 1.0-5.0 score where higher =
        more important; used for export ordering and eviction priority."""
        weight = max(0.0, min(5.0, weight))
        with self._connect() as connection:
            connection.execute(
                "UPDATE proposals SET weight = ? WHERE proposal_id = ?",
                (weight, proposal_id),
            )

    def recalculate_all_weights(self) -> int:
        """Recalculate weight for all proposals using composite scoring.

        Weight formula: base_score(category) + risk_bonus(risk_level) + retrieval_bonus
        - category: rule=2.0, workflow_hint=1.5, preference=1.0, fact=0.5
        - risk: high=+1.5, medium=+1.0, low=+0.0
        - retrieval: +0.1 per retrieval in 30d, capped at +1.0
        Final weight clamped to [0.5, 5.0].
        Returns the number of proposals updated.
        """
        from hermes.weight import compute_weight
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT proposal_id, category, risk_level, retrieval_count_30d FROM proposals"
            ).fetchall()
        updated = 0
        for row in rows:
            w = compute_weight(
                category=str(row["category"]),
                risk_level=str(row["risk_level"]),
                retrieval_count_30d=int(row["retrieval_count_30d"] or 0),
            )
            with self._connect() as connection:
                connection.execute(
                    "UPDATE proposals SET weight = ? WHERE proposal_id = ?",
                    (w, str(row["proposal_id"])),
                )
            updated += 1
        return updated

    def list_proposals_ordered_for_demotion(self, project_key: str | None = None) -> list[dict[str, str | int | float | None]]:
        """List proposals eligible for demotion, ordered by weight ASC (lowest weight
        demoted first), then retrieval_count ASC, then inserted_at ASC."""
        if project_key is None:
            query = """
                SELECT * FROM proposals
                WHERE state = 'approved_for_export' AND scope = 'global'
                ORDER BY weight ASC, retrieval_count_30d ASC, inserted_at ASC
                """
            params: tuple = ()
        else:
            query = """
                SELECT * FROM proposals
                WHERE state = 'approved_for_export' AND project_key = ?
                ORDER BY weight ASC, retrieval_count_30d ASC, inserted_at ASC
                """
            params = (project_key,)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    # -----------------------------------------------------------------------
    # V2: KnowledgeNode CRUD
    # -----------------------------------------------------------------------

    # Column whitelist for knowledge_nodes to prevent SQL injection
    _KN_COLUMNS = frozenset({
        "id", "parent_id", "content", "summary", "category", "domain",
        "stage", "operation", "confidence", "source", "evidence",
        "supersedes", "merged_from", "contradicts", "verified_by",
        "created_at", "refined_at", "verified_at", "deprecated_at",
        "retrieval_count", "last_used_at", "correction_count",
        "outcome_count", "last_outcome_at", "kind", "trigger_terms",
        "use_when", "avoid_when", "success_signal", "failure_signal",
    })

    def insert_knowledge_node(self, node: KnowledgeNode) -> None:
        """Insert a new knowledge node into the V2 table."""
        row = {
            "id": node.id,
            "parent_id": node.parent_id,
            "content": node.content,
            "summary": node.summary,
            "category": node.category,
            "domain": node.domain,
            "stage": node.stage,
            "operation": node.operation,
            "confidence": node.confidence,
            "source": node.source,
            "evidence": node.evidence if isinstance(node.evidence, str) else json.dumps(node.evidence),
            "supersedes": node.supersedes,
            "merged_from": node.merged_from if isinstance(node.merged_from, str) else json.dumps(node.merged_from),
            "contradicts": node.contradicts if isinstance(node.contradicts, str) else json.dumps(node.contradicts),
            "verified_by": node.verified_by if isinstance(node.verified_by, str) else json.dumps(node.verified_by),
            "created_at": node.created_at,
            "refined_at": node.refined_at,
            "verified_at": node.verified_at,
            "deprecated_at": node.deprecated_at,
            "retrieval_count": node.retrieval_count,
            "last_used_at": node.last_used_at,
            "correction_count": node.correction_count,
            "outcome_count": node.outcome_count,
            "last_outcome_at": node.last_outcome_at,
            "kind": node.kind,
            "trigger_terms": node.trigger_terms,
            "use_when": node.use_when,
            "avoid_when": node.avoid_when,
            "success_signal": node.success_signal,
            "failure_signal": node.failure_signal,
        }
        payload = {k: v for k, v in row.items() if k in self._KN_COLUMNS}
        columns = ", ".join(payload)
        placeholders = ", ".join("?" for _ in payload)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO knowledge_nodes ({columns}) VALUES ({placeholders})",
                tuple(payload.values()),
            )
            try:
                connection.execute(
                    "INSERT OR REPLACE INTO knowledge_nodes_fts (id, summary, content, category, domain) VALUES (?, ?, ?, ?, ?)",
                    (node.id, node.summary, node.content, node.category, node.domain),
                )
            except sqlite3.OperationalError:
                pass
        self.refresh_entity_embedding(
            "knowledge",
            node.id,
            self._knowledge_embedding_text(node.summary, node.content),
            raise_errors=False,
        )

    def get_knowledge_node(self, node_id: str) -> KnowledgeNode | None:
        """Get a single knowledge node by ID."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_nodes WHERE id = ?",
                (node_id,),
            ).fetchone()
        if row is None:
            return None
        return KnowledgeNode(**dict(row))

    def update_knowledge_node(self, node_id: str, **fields: object) -> None:
        """Update specific fields of a knowledge node."""
        valid_fields = {k: v for k, v in fields.items() if k in self._KN_COLUMNS and k != "id"}
        if not valid_fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in valid_fields)
        values = list(valid_fields.values()) + [node_id]
        with self._connect() as connection:
            connection.execute(
                f"UPDATE knowledge_nodes SET {set_clause} WHERE id = ?",
                tuple(values),
            )
        node = self.get_knowledge_node(node_id) if {"summary", "content", "category", "domain"} & valid_fields.keys() else None
        if node is not None:
            if "summary" in valid_fields or "content" in valid_fields:
                self.refresh_entity_embedding(
                    "knowledge",
                    node.id,
                    self._knowledge_embedding_text(node.summary, node.content),
                    raise_errors=False,
                )
            if "category" in valid_fields or "domain" in valid_fields or "summary" in valid_fields or "content" in valid_fields:
                with self._connect() as connection:
                    try:
                        connection.execute(
                            "INSERT OR REPLACE INTO knowledge_nodes_fts (id, summary, content, category, domain) VALUES (?, ?, ?, ?, ?)",
                            (node.id, node.summary, node.content, node.category, node.domain),
                        )
                    except sqlite3.OperationalError:
                        pass

    def delete_knowledge_node(self, node_id: str) -> bool:
        """Delete a knowledge node. Returns True if deleted."""
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM knowledge_nodes WHERE id = ?", (node_id,)
            )
            # Also delete thought chains and its persisted vector.
            connection.execute(
                "DELETE FROM thought_chains WHERE node_id = ?", (node_id,)
            )
            connection.execute(
                "DELETE FROM entity_embeddings WHERE entity_type = 'knowledge' AND entity_id = ?",
                (node_id,),
            )
            return cursor.rowcount > 0

    # -----------------------------------------------------------------------
    # Persistent embeddings (proposals + knowledge nodes)
    # -----------------------------------------------------------------------

    @staticmethod
    def _knowledge_embedding_text(summary: object, content: object) -> str:
        return "\n\n".join(part for part in (str(summary or "").strip(), str(content or "").strip()) if part)

    @staticmethod
    def _proposal_embedding_text(proposal: dict[str, object]) -> str:
        return "\n\n".join(
            str(proposal.get(key) or "").strip()
            for key in ("summary", "observation", "why_it_matters", "suggested_memory")
            if str(proposal.get(key) or "").strip()
        )

    @staticmethod
    def _embedding_hash(text: str) -> str:
        import hashlib
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _store_embedding(
        self,
        entity_type: str,
        entity_id: str,
        text_hash: str,
        model: str,
        *,
        vector: list[float] | None,
        status: str,
        error: str = "",
    ) -> None:
        from hermes.embedding import vector_to_blob

        now = datetime.now(timezone.utc).isoformat()
        blob = vector_to_blob(vector) if vector is not None else None
        dimension = len(vector) if vector is not None else 0
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO entity_embeddings
                   (entity_type, entity_id, text_hash, model, dimension, vector, status, error, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                     text_hash=excluded.text_hash, model=excluded.model,
                     dimension=excluded.dimension, vector=excluded.vector,
                     status=excluded.status, error=excluded.error,
                     updated_at=excluded.updated_at""",
                (entity_type, entity_id, text_hash, model, dimension, blob, status, error[:500], now),
            )

    def refresh_entity_embedding(
        self,
        entity_type: str,
        entity_id: str,
        text: str,
        *,
        raise_errors: bool = False,
    ) -> bool:
        """Create or refresh one persisted embedding; never break primary writes."""
        from hermes.embedding import embed_text, provider_config

        config = provider_config()
        model = str(config["model"])
        text_hash = self._embedding_hash(text)
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT text_hash, model, status FROM entity_embeddings WHERE entity_type = ? AND entity_id = ?",
                (entity_type, entity_id),
            ).fetchone()
        if existing and existing["text_hash"] == text_hash and existing["model"] == model and existing["status"] == "ready":
            return True
        if not config["enabled"]:
            self._store_embedding(entity_type, entity_id, text_hash, model, vector=None, status="pending")
            return False
        try:
            vector = embed_text(text)
            if vector is None:
                self._store_embedding(entity_type, entity_id, text_hash, model, vector=None, status="pending")
                return False
            self._store_embedding(entity_type, entity_id, text_hash, model, vector=vector, status="ready")
            return True
        except Exception as exc:
            self._store_embedding(entity_type, entity_id, text_hash, model, vector=None, status="failed", error=str(exc))
            if raise_errors:
                raise
            return False

    def backfill_embeddings(self, *, entity_type: str = "all", batch_size: int = 32) -> dict[str, object]:
        """Backfill missing/stale proposal and knowledge vectors in provider batches."""
        from hermes.embedding import embed_texts, provider_config

        if entity_type not in {"all", "proposal", "knowledge"}:
            raise ValueError("entity_type must be all, proposal, or knowledge")
        config = provider_config()
        if not config["enabled"]:
            raise RuntimeError("embedding provider is disabled or incomplete")
        model = str(config["model"])
        candidates: list[tuple[str, str, str]] = []
        with self._connect() as connection:
            if entity_type in {"all", "proposal"}:
                rows = connection.execute("SELECT * FROM proposals ORDER BY inserted_at").fetchall()
                candidates.extend(("proposal", str(row["proposal_id"]), self._proposal_embedding_text(dict(row))) for row in rows)
            if entity_type in {"all", "knowledge"}:
                rows = connection.execute("SELECT id, summary, content FROM knowledge_nodes ORDER BY created_at").fetchall()
                candidates.extend(("knowledge", str(row["id"]), self._knowledge_embedding_text(row["summary"], row["content"])) for row in rows)
            existing = {
                (str(row["entity_type"]), str(row["entity_id"])): (str(row["text_hash"]), str(row["model"]), str(row["status"]))
                for row in connection.execute("SELECT entity_type, entity_id, text_hash, model, status FROM entity_embeddings").fetchall()
            }
        pending = [
            item for item in candidates
            if existing.get((item[0], item[1])) != (self._embedding_hash(item[2]), model, "ready")
        ]
        embedded = failed = 0
        errors: list[str] = []
        for start in range(0, len(pending), max(1, batch_size)):
            batch = pending[start:start + max(1, batch_size)]
            try:
                vectors = embed_texts([item[2] for item in batch])
                if vectors is None:
                    raise RuntimeError("embedding provider became unavailable")
                for (kind, entity_id, text), vector in zip(batch, vectors):
                    self._store_embedding(kind, entity_id, self._embedding_hash(text), model, vector=vector, status="ready")
                    embedded += 1
            except Exception as exc:
                message = str(exc)[:500]
                errors.append(message)
                for kind, entity_id, text in batch:
                    self._store_embedding(kind, entity_id, self._embedding_hash(text), model, vector=None, status="failed", error=message)
                    failed += 1
        return {"total": len(candidates), "needed": len(pending), "embedded": embedded, "failed": failed, "errors": errors[:5], "model": model}

    def embedding_status(self) -> dict[str, object]:
        """Return provider and per-entity coverage without exposing credentials."""
        from hermes.embedding import provider_config

        with self._connect() as connection:
            source = {
                "proposal": int(connection.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]),
                "knowledge": int(connection.execute("SELECT COUNT(*) FROM knowledge_nodes").fetchone()[0]),
            }
            rows = connection.execute(
                "SELECT entity_type, status, COUNT(*) AS total, MAX(updated_at) AS updated_at FROM entity_embeddings GROUP BY entity_type, status"
            ).fetchall()
            latest_error = connection.execute(
                "SELECT error FROM entity_embeddings WHERE status = 'failed' AND error != '' ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        by_type: dict[str, dict[str, object]] = {}
        for kind in ("proposal", "knowledge"):
            by_type[kind] = {"total": source[kind], "ready": 0, "pending": 0, "failed": 0, "coverage": 0.0, "updated_at": ""}
        for row in rows:
            kind = str(row["entity_type"])
            if kind not in by_type:
                continue
            status = str(row["status"])
            by_type[kind][status] = int(row["total"])
            by_type[kind]["updated_at"] = str(row["updated_at"] or by_type[kind]["updated_at"])
        for values in by_type.values():
            total = int(values["total"])
            ready = int(values.get("ready", 0))
            recorded_pending = int(values.get("pending", 0))
            failed = int(values.get("failed", 0))
            unrecorded = max(0, total - ready - recorded_pending - failed)
            values["pending"] = recorded_pending + unrecorded
            values["coverage"] = round((ready / total * 100.0) if total else 100.0, 1)
        provider = provider_config()
        provider.pop("base_url", None)
        total = sum(source.values())
        ready = sum(int(str(item.get("ready", 0) or 0)) for item in by_type.values())
        pending = sum(int(str(item.get("pending", 0) or 0)) for item in by_type.values())
        failed = sum(int(str(item.get("failed", 0) or 0)) for item in by_type.values())
        if provider.get("disabled"):
            state = "disabled"
        elif not provider.get("configured"):
            state = "not_configured"
        elif failed:
            state = "degraded"
        elif pending:
            state = "syncing"
        else:
            state = "healthy"
        return {
            "state": state,
            "provider": provider,
            "entities": by_type,
            "total": total,
            "ready": ready,
            "pending": pending,
            "failed": failed,
            "latest_error": str(latest_error["error"] if latest_error else ""),
        }

    def _semantic_knowledge_scores(
        self,
        query: str,
        *,
        category: str | None = None,
        domain: str | None = None,
    ) -> dict[str, float]:
        from hermes.embedding import blob_to_vector, cosine_similarity, embed_text

        try:
            query_vector = embed_text(query)
        except Exception:
            return {}
        if query_vector is None:
            return {}
        filters = ["ee.entity_type = 'knowledge'", "ee.status = 'ready'", "kn.stage IN ('canonized', 'verified', 'refined')"]
        params: list[object] = []
        if category:
            filters.append("kn.category = ?")
            params.append(category)
        if domain:
            filters.append("kn.domain = ?")
            params.append(domain)
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT ee.entity_id, ee.vector, ee.dimension
                    FROM entity_embeddings ee JOIN knowledge_nodes kn ON kn.id = ee.entity_id
                    WHERE {' AND '.join(filters)}""",
                tuple(params),
            ).fetchall()
        scores: dict[str, float] = {}
        for row in rows:
            try:
                vector = blob_to_vector(bytes(row["vector"]), int(row["dimension"]))
                scores[str(row["entity_id"])] = cosine_similarity(query_vector, vector)
            except Exception:
                continue
        return scores

    def list_knowledge_nodes(
        self,
        *,
        stage: str | None = None,
        category: str | None = None,
        domain: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[KnowledgeNode]:
        """List knowledge nodes with optional filters."""
        conditions: list[str] = []
        params: list[object] = []
        if stage:
            conditions.append("stage = ?")
            params.append(stage)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if domain:
            conditions.append("domain = ?")
            params.append(domain)
        where = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM knowledge_nodes WHERE {where} ORDER BY {order_by} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [KnowledgeNode(**dict(row)) for row in rows]

    def count_knowledge_nodes_by_stage(self) -> dict[str, int]:
        """Count nodes grouped by stage."""
        counts = {"draft": 0, "refined": 0, "verified": 0, "canonized": 0, "deprecated": 0}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT stage, COUNT(*) AS total FROM knowledge_nodes GROUP BY stage"
            ).fetchall()
        for row in rows:
            key = str(row["stage"])
            if key in counts:
                counts[key] = int(row["total"])
            else:
                counts[key] = int(row["total"])
        return counts

    def find_superseded_nodes(self, superseded_id: str) -> list[KnowledgeNode]:
        """Find nodes that supersede the given node."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_nodes WHERE supersedes = ?",
                (superseded_id,),
            ).fetchall()
        return [KnowledgeNode(**dict(row)) for row in rows]

    def find_children(self, parent_id: str) -> list[KnowledgeNode]:
        """Find child nodes (evolved from parent)."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_nodes WHERE parent_id = ? ORDER BY created_at ASC",
                (parent_id,),
            ).fetchall()
        return [KnowledgeNode(**dict(row)) for row in rows]

    def search_knowledge_nodes_by_summary(self, query: str, limit: int = 10) -> list[KnowledgeNode]:
        """Simple text search on summary field (placeholder until embeddings)."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_nodes WHERE summary LIKE ? AND stage != 'deprecated' ORDER BY confidence DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [KnowledgeNode(**dict(row)) for row in rows]

    # -----------------------------------------------------------------------
    # V2: ThoughtChain CRUD
    # -----------------------------------------------------------------------

    def insert_thought_chain(self, tc: ThoughtChain) -> None:
        """Insert a thought chain entry."""
        row = {
            "id": tc.id,
            "node_id": tc.node_id,
            "action": tc.action,
            "reasoning": tc.reasoning,
            "evidence_used": tc.evidence_used if isinstance(tc.evidence_used, str) else json.dumps(tc.evidence_used),
            "decision": tc.decision,
            "confidence_in_decision": tc.confidence_in_decision,
            "created_at": tc.created_at,
        }
        columns = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO thought_chains ({columns}) VALUES ({placeholders})",
                tuple(row.values()),
            )

    def get_thought_chains(self, node_id: str) -> list[ThoughtChain]:
        """Get all thought chain entries for a node."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM thought_chains WHERE node_id = ? ORDER BY created_at ASC",
                (node_id,),
            ).fetchall()
        return [ThoughtChain(**dict(row)) for row in rows]

    # -----------------------------------------------------------------------
    # V2: Migration from proposals → knowledge_nodes
    # -----------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Knowledge search (FTS5)
    # ------------------------------------------------------------------

    @staticmethod
    def _fts_query(query: str) -> str:
        """Build an FTS5 query from a human search string."""
        terms = [t for t in query.strip().split() if t]
        if not terms:
            return ""
        quoted = []
        for t in terms:
            t_clean = t.strip('"').strip("'")
            if " " in t_clean:
                quoted.append(f'"{t_clean}"')
            else:
                quoted.append(t_clean + "*")
        return " AND ".join(quoted)

    def search_knowledge_nodes(
        self,
        query: str,
        *,
        limit: int = 10,
        category: str | None = None,
        domain: str | None = None,
    ) -> list[dict[str, object]]:
        """Search active knowledge nodes with FTS5 and tokenized fallback."""
        clean_query = (query or "").strip()
        if limit <= 0:
            return []
        filters = ["kn.stage IN ('canonized', 'verified', 'refined')"]
        filter_params: list[object] = []
        if category:
            filters.append("kn.category = ?")
            filter_params.append(category)
        if domain:
            filters.append("kn.domain = ?")
            filter_params.append(domain)
        where_filter = " AND ".join(filters)
        fts_query = self._fts_query(clean_query)
        rows = []
        with self._connect() as connection:
            if fts_query:
                try:
                    rows = connection.execute(
                        f"""SELECT kn.*, bm25(knowledge_nodes_fts) * -1 AS search_score
                           FROM knowledge_nodes_fts
                           JOIN knowledge_nodes kn ON kn.id = knowledge_nodes_fts.id
                           WHERE knowledge_nodes_fts MATCH ? AND {where_filter}
                           ORDER BY search_score DESC LIMIT ?""",
                        tuple([fts_query] + filter_params + [limit]),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            if not rows:
                rows = connection.execute(
                    f"""SELECT kn.*, 0.0 AS search_score FROM knowledge_nodes kn
                       WHERE {where_filter}
                       ORDER BY confidence DESC, retrieval_count DESC LIMIT ?""",
                    tuple(filter_params + [limit]),
                ).fetchall()
        semantic_scores = self._semantic_knowledge_scores(
            clean_query, category=category, domain=domain,
        ) if clean_query else {}
        if semantic_scores:
            semantic_ids = [
                node_id for node_id, _score in
                sorted(semantic_scores.items(), key=lambda item: item[1], reverse=True)[: max(limit * 3, 20)]
            ]
            with self._connect() as connection:
                placeholders = ",".join("?" for _ in semantic_ids)
                semantic_rows = connection.execute(
                    f"SELECT kn.*, 0.0 AS search_score FROM knowledge_nodes kn WHERE kn.id IN ({placeholders})",
                    tuple(semantic_ids),
                ).fetchall()
            by_id = {str(row["id"]): row for row in rows}
            for row in semantic_rows:
                by_id.setdefault(str(row["id"]), row)
            rows = list(by_id.values())

        terms = [t.lower() for t in re.findall(r"[A-Za-z0-9_\-]+|[一-鿿]{2,}", clean_query)]
        scored = []
        for row in rows:
            d = dict(row)
            hay = " ".join(str(d.get(k, "")) for k in ("summary", "content", "category", "domain", "trigger_terms")).lower()
            lexical_score = float(d.get("search_score") or 0)
            if terms:
                lexical_score += sum(1 for term in terms if term in hay)
            semantic_score = semantic_scores.get(str(d.get("id")), 0.0)
            if semantic_score > 0:
                d["semantic_score"] = round(semantic_score, 6)
                d["retrieval_mode"] = "hybrid"
                score = semantic_score * 10.0 + max(0.0, lexical_score)
            else:
                d["retrieval_mode"] = "fts5"
                score = lexical_score
            if score > 0 or not terms:
                d["score"] = score if score > 0 else float(d.get("confidence") or 0)
                scored.append(d)
        scored.sort(key=lambda d: (float(d.get("score") or 0), float(d.get("confidence") or 0)), reverse=True)
        return scored[:limit]

    # ------------------------------------------------------------------
    # Retrieval tracking (V3)
    # ------------------------------------------------------------------

    def record_retrieval_for_query(
        self,
        query: str,
        agent: str = "",
        host: str = "",
        *,
        limit: int = 10,
        category: str | None = None,
        domain: str | None = None,
        session_id: str = "",
    ) -> dict[str, object]:
        """Search nodes, increment retrieval_count, store retrieval_log."""
        import logging
        now = datetime.now(timezone.utc).isoformat()
        results = self.search_knowledge_nodes(query, limit=limit, category=category, domain=domain)
        node_ids = [str(item["id"]) for item in results]
        retrieval_mode = "hybrid" if any(item.get("retrieval_mode") == "hybrid" for item in results) else "fts5"
        event_id = str(uuid.uuid4()) if node_ids else ""
        with self._connect() as connection:
            if node_ids:
                ph = ",".join("?" * len(node_ids))
                connection.execute(
                    f"UPDATE knowledge_nodes SET retrieval_count = retrieval_count + 1, last_used_at = ? WHERE id IN ({ph})",
                    tuple([now] + node_ids),
                )
                connection.execute(
                    """INSERT INTO knowledge_retrieval_events (id, query, agent, host, node_ids, created_at, session_id, host_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, query, agent, host, json.dumps(node_ids), now, session_id, host),
                )
                connection.execute(
                    """INSERT INTO retrieval_log (id, query, retrieval_mode, candidate_ids, selected_ids, used_ids, agent, session_id, task_context, created_at)
                       VALUES (?, ?, ?, ?, '[]', '[]', ?, ?, '', ?)""",
                    (event_id, query, retrieval_mode, json.dumps(node_ids), agent or "unknown", session_id or "", now),
                )
                for node_id in node_ids:
                    updated_row = connection.execute(
                        "SELECT retrieval_count FROM knowledge_nodes WHERE id = ?", (node_id,)
                    ).fetchone()
                    if updated_row:
                        connection.execute(
                            "UPDATE proposals SET retrieval_count_30d = ? WHERE proposal_id = ?",
                            (int(updated_row["retrieval_count"] or 0), node_id),
                        )
                logging.info("retrieval: +1 for %d nodes matching '%s'", len(node_ids), query[:60])
        return {"updated": len(node_ids), "event_id": event_id, "node_ids": node_ids, "results": results}

    def get_retrieval_event(self, event_id: str) -> "KnowledgeRetrievalEvent | None":
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_retrieval_events WHERE id = ?", (event_id,)
            ).fetchone()
        return KnowledgeRetrievalEvent(**dict(row)) if row else None

    # ------------------------------------------------------------------
    # Outcome recording (V3)
    # ------------------------------------------------------------------

    def record_outcome(self, node_id: str, *, success: bool = True, note: str = "", event_id: str | None = None) -> bool:
        """Legacy outcome recording."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            if success:
                connection.execute(
                    "UPDATE knowledge_nodes SET outcome_count = outcome_count + 1, last_outcome_at = ?, confidence = MIN(1.0, confidence + 0.05) WHERE id = ?",
                    (now, node_id),
                )
            else:
                connection.execute(
                    "UPDATE knowledge_nodes SET outcome_count = outcome_count + 1, last_outcome_at = ?, confidence = MAX(0.1, confidence - 0.05) WHERE id = ?",
                    (now, node_id),
                )
            if event_id:
                connection.execute(
                    "UPDATE knowledge_retrieval_events SET outcome_recorded_at = ? WHERE id = ?",
                    (now, event_id),
                )
            connection.execute(
                """INSERT INTO thought_chains (id, node_id, action, reasoning, evidence_used, decision, confidence_in_decision, created_at)
                   VALUES (?, ?, 'outcome_recorded', ?, '[]', ?, NULL, ?)""",
                (str(uuid.uuid4()), node_id, f"success={success}; note={note[:500]}", "reinforce" if success else "penalize", now),
            )
        return True

    def record_outcome_v3(self, retrieval_log_id: str, outcomes: list[dict]) -> int:
        """Record per-memory outcomes (v3 protocol)."""
        if not outcomes:
            return 0
        import logging
        now = datetime.now(timezone.utc).isoformat()
        recorded = 0
        with self._connect() as connection:
            for outcome in outcomes:
                oid = str(uuid.uuid4())
                memory_id = str(outcome.get("memory_id", ""))
                used = 1 if outcome.get("used") else 0
                helpfulness = str(outcome.get("helpfulness", "unknown"))
                user_validated = outcome.get("user_validated")
                task_success = str(outcome.get("task_success", "unknown"))
                notes = str(outcome.get("notes", ""))[:1000]
                if not memory_id:
                    continue
                connection.execute(
                    """INSERT INTO outcome_log (id, retrieval_log_id, memory_id, used, helpfulness, user_validated, task_success, notes, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (oid, retrieval_log_id, memory_id, used, helpfulness, user_validated, task_success, notes, now),
                )
                connection.execute(
                    "UPDATE knowledge_nodes SET outcome_count = outcome_count + 1, last_outcome_at = ? WHERE id = ?",
                    (now, memory_id),
                )
                if used and helpfulness == "helpful" and user_validated:
                    connection.execute("UPDATE knowledge_nodes SET confidence = MIN(1.0, confidence + 0.05) WHERE id = ?", (memory_id,))
                    connection.execute("UPDATE proposals SET weight = weight * 1.05 WHERE proposal_id = ?", (memory_id,))
                elif helpfulness == "harmful":
                    connection.execute("UPDATE knowledge_nodes SET confidence = MAX(0.1, confidence - 0.1) WHERE id = ?", (memory_id,))
                    connection.execute("UPDATE proposals SET weight = weight * 0.5 WHERE proposal_id = ?", (memory_id,))
                    # Quarantine: 3+ harmful outcomes -> mark as quarantined
                    total_harmful = connection.execute(
                        "SELECT COUNT(*) FROM outcome_log WHERE memory_id = ? AND helpfulness = 'harmful'",
                        (memory_id,),
                    ).fetchone()[0]
                    if total_harmful >= 3:
                        connection.execute(
                            "UPDATE knowledge_nodes SET stage = 'quarantined' WHERE id = ? AND stage != 'quarantined'",
                            (memory_id,),
                        )
                recorded += 1
            used_ids = [str(o["memory_id"]) for o in outcomes if o.get("used") and o.get("memory_id")]
            if used_ids:
                connection.execute("UPDATE retrieval_log SET used_ids = ? WHERE id = ?", (json.dumps(used_ids), retrieval_log_id))
            connection.execute("UPDATE knowledge_retrieval_events SET outcome_recorded_at = ? WHERE id = ?", (now, retrieval_log_id))
        logging.info("outcome_v3: recorded %d outcomes for retrieval %s", recorded, retrieval_log_id[:8])
        return recorded

    # ------------------------------------------------------------------
    # Stage-1 schema migration (preserve production rows)
    # ------------------------------------------------------------------

    _STAGE1_MIGRATIONS: tuple[str, ...] = (
        # knowledge_retrieval_events in production lacks session_id/host_id
        # and the pair-identity columns needed by finalize_session.
        "ALTER TABLE knowledge_retrieval_events ADD COLUMN session_id TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE knowledge_retrieval_events ADD COLUMN host_id TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE knowledge_retrieval_events ADD COLUMN finalized_at TEXT",
        "ALTER TABLE knowledge_retrieval_events ADD COLUMN final_result TEXT",
        # outcome_log idempotency: same (retrieval, node) replay must not
        # double-count. Existing rows are preserved; the unique index only
        # rejects future duplicates.
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_ol_pair ON outcome_log(retrieval_log_id, memory_id)",
    )

    def _migrate_stage1_schema(self) -> None:
        """Best-effort ALTER TABLE migrations for the production DB.

        Per the user inspection, the production tables already contain
        43 retrieval rows and 2 outcome rows; we MUST NOT recreate the
        tables. Each statement is wrapped in try/except so a partially
        migrated DB can re-run init without raising.
        """
        with self._connect() as connection:
            for sql in self._STAGE1_MIGRATIONS:
                try:
                    connection.execute(sql)
                except Exception:
                    pass  # already applied / no-op
            # Backfill session_id/host_id from the parallel retrieval_log
            # table when available (it has both columns). Existing retrieval
            # rows without a matching retrieval_log row keep '' (legitimate
            # legacy default).
            try:
                connection.execute(
                    """
                    UPDATE knowledge_retrieval_events AS kre
                    SET session_id = COALESCE(NULLIF(rl.session_id, ''), kre.session_id),
                        host_id    = COALESCE(NULLIF(rl.agent, ''),    kre.host_id)
                    FROM retrieval_log AS rl
                    WHERE rl.id = kre.id
                      AND (kre.session_id = '' OR kre.host_id = '')
                    """
                )
            except Exception:
                # Older SQLite builds (<3.33) lack UPDATE...FROM; fall back
                # to a row-by-row backfill which is fine for ≤ 100 rows.
                rows = connection.execute(
                    "SELECT id FROM knowledge_retrieval_events WHERE session_id = '' OR host_id = ''"
                ).fetchall()
                for row in rows:
                    rl = connection.execute(
                        "SELECT session_id, agent FROM retrieval_log WHERE id = ?",
                        (row["id"],),
                    ).fetchone()
                    if rl is None:
                        continue
                    connection.execute(
                        "UPDATE knowledge_retrieval_events SET session_id = ?, host_id = ? WHERE id = ?",
                        (rl["session_id"] or "", rl["agent"] or "", row["id"]),
                    )

    # ------------------------------------------------------------------
    # Idempotent per-pair outcome recording + scoped finalisation
    # ------------------------------------------------------------------

    def record_outcome_pair(
        self,
        retrieval_log_id: str,
        node_id: str,
        status: str,
        *,
        agent: str = "",
        host_id: str = "",
        session_id: str = "",
        notes: str = "",
        used: bool = True,
        task_success: str = "unknown",
        user_validated: bool | None = None,
    ) -> dict[str, object]:
        """Idempotent per-pair outcome writer (stage-1 contract).

        Pair identity is ``(retrieval_log_id, node_id)``. Repeated writes
        for the same pair with the same status are no-ops (returns
        ``status="duplicate_same_status"``); a replay with a *different*
        terminal status is logged as a conflict anomaly and never
        overwrites the original row.

        Returns:
            dict with keys: recorded (bool), status ("recorded"/"duplicate_same_status"/
            "conflict_unresolved"/"missing_retrieval"/"missing_node"), conflict_status (str|None).
        """
        from hermes.outcomes import (
            OutcomeObservation,
            TERMINAL_CLEAN_STATUSES,
            normalise_status,
        )

        normalised = normalise_status(status, used=used)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            # FK: retrieval must exist and belong to the same scope.
            rl_row = connection.execute(
                "SELECT id, agent, session_id FROM retrieval_log WHERE id = ?",
                (retrieval_log_id,),
            ).fetchone()
            if rl_row is None:
                kre_row = connection.execute(
                    "SELECT id FROM knowledge_retrieval_events WHERE id = ?",
                    (retrieval_log_id,),
                ).fetchone()
                if kre_row is None:
                    return {"recorded": False, "status": "missing_retrieval", "conflict_status": None}
            else:
                # Scoped consistency: if both sides are provided, reject mismatches.
                if agent and rl_row["agent"] and rl_row["agent"] != agent:
                    return {"recorded": False, "status": "scope_mismatch", "conflict_status": None}
                if session_id and rl_row["session_id"] and rl_row["session_id"] != session_id:
                    return {"recorded": False, "status": "scope_mismatch", "conflict_status": None}
            # FK: node must exist (durable memory reference).
            kn_row = connection.execute(
                "SELECT id FROM knowledge_nodes WHERE id = ?", (node_id,),
            ).fetchone()
            if kn_row is None:
                return {"recorded": False, "status": "missing_node", "conflict_status": None}

            existing = connection.execute(
                "SELECT id, used, helpfulness FROM outcome_log WHERE retrieval_log_id = ? AND memory_id = ?",
                (retrieval_log_id, node_id),
            ).fetchone()
            if existing is not None:
                existing_norm = normalise_status(existing["helpfulness"], used=bool(existing["used"]))
                if existing_norm == normalised:
                    return {"recorded": False, "status": "duplicate_same_status", "conflict_status": None}
                # Terminal precedence: contradicted > failed > applied > not_used.
                # Lower-precedence replay must not overwrite a severer label.
                from hermes.outcomes import TERMINAL_PRECEDENCE
                if TERMINAL_PRECEDENCE.get(existing_norm, 0) >= TERMINAL_PRECEDENCE.get(normalised, 0):
                    return {"recorded": False, "status": "conflict_unresolved", "conflict_status": existing_norm}
                # Same-severity or higher-severity replay: reject — never overwrite silently.
                return {"recorded": False, "status": "conflict_unresolved", "conflict_status": existing_norm}

            # Reject non-terminal writes via outcomes helper.  We never
            # insert a "pending" row (would inflate denominators later).
            if normalised not in TERMINAL_CLEAN_STATUSES:
                return {"recorded": False, "status": "non_terminal_rejected", "conflict_status": None}

            # Persist as legacy-v3 helpfulness bucket so existing queries keep working.
            helpfulness = normalised

            oid = str(uuid.uuid4())
            connection.execute(
                """INSERT INTO outcome_log
                   (id, retrieval_log_id, memory_id, used, helpfulness, user_validated, task_success, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (oid, retrieval_log_id, node_id, int(bool(used)), helpfulness,
                 1 if user_validated else (0 if user_validated is False else None),
                 task_success, str(notes)[:1000], now),
            )
            # Confidence / weight updates use the same policy as v3.
            if normalised == "applied":
                connection.execute(
                    "UPDATE knowledge_nodes SET outcome_count = outcome_count + 1, last_outcome_at = ?, confidence = MIN(1.0, confidence + 0.05) WHERE id = ?",
                    (now, node_id),
                )
            elif normalised in {"failed", "contradicted"}:
                connection.execute(
                    "UPDATE knowledge_nodes SET outcome_count = outcome_count + 1, last_outcome_at = ?, confidence = MAX(0.1, confidence - 0.1) WHERE id = ?",
                    (now, node_id),
                )
                if normalised == "contradicted":
                    total_harmful = connection.execute(
                        "SELECT COUNT(*) FROM outcome_log WHERE memory_id = ? AND helpfulness = 'harmful'",
                        (node_id,),
                    ).fetchone()[0]
                    if total_harmful >= 3:
                        connection.execute(
                            "UPDATE knowledge_nodes SET stage = 'quarantined' WHERE id = ? AND stage != 'quarantined'",
                            (node_id,),
                        )
            else:
                connection.execute(
                    "UPDATE knowledge_nodes SET outcome_count = outcome_count + 1, last_outcome_at = ? WHERE id = ?",
                    (now, node_id),
                )
            # Mirror used_ids on retrieval_log (parity with record_outcome_v3).
            if used:
                used_row = connection.execute(
                    "SELECT used_ids FROM retrieval_log WHERE id = ?", (retrieval_log_id,),
                ).fetchone()
                if used_row is not None:
                    try:
                        current = json.loads(used_row["used_ids"] or "[]")
                    except json.JSONDecodeError:
                        current = []
                    if node_id not in current:
                        current.append(node_id)
                        connection.execute(
                            "UPDATE retrieval_log SET used_ids = ? WHERE id = ?",
                            (json.dumps(current), retrieval_log_id),
                        )
            connection.execute(
                "UPDATE knowledge_retrieval_events SET outcome_recorded_at = ? WHERE id = ?",
                (now, retrieval_log_id),
            )
        return {"recorded": True, "status": "recorded", "conflict_status": None}

    def finalize_session(self, agent: str, host_id: str, session_id: str) -> dict[str, object]:
        """Audit exact session scope; missing outcomes stay pending, never fabricated."""
        if not agent or not host_id or not session_id:
            raise ValueError("agent, host_id and session_id are required")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("CREATE TABLE IF NOT EXISTS brain_session_audits (agent TEXT NOT NULL, host_id TEXT NOT NULL, session_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(agent,host_id,session_id))")
            rows = c.execute("SELECT id,node_ids FROM knowledge_retrieval_events WHERE agent=? AND host_id=? AND session_id=?", (agent,host_id,session_id)).fetchall()
            expected={(r["id"],n) for r in rows for n in json.loads(r["node_ids"] or "[]")}
            observed=set()
            from hermes.outcomes import normalise_status, TERMINAL_CLEAN_STATUSES
            for rid,nid in expected:
                o=c.execute("SELECT helpfulness,used FROM outcome_log WHERE retrieval_log_id=? AND memory_id=?",(rid,nid)).fetchone()
                if o and normalise_status(o["helpfulness"], bool(o["used"])) in TERMINAL_CLEAN_STATUSES:
                    observed.add((rid,nid))
            missing=sorted(expected-observed)
            result={"final_result": "no_experience_used" if not rows else ("incomplete" if missing else "complete"), "retrieval_events":len(rows), "expected_outcomes":len(expected), "reported_outcomes":len(observed), "missing_pairs":[{"retrieval_id":r,"node_id":n,"retrieval_log_id":r,"memory_id":n} for r,n in missing], "count_anomaly":bool(missing), "duplicate_conflicts":[], "finalized_at":now, "scope":{"agent":agent,"host_id":host_id,"session_id":session_id}}
            previous=c.execute("SELECT payload FROM brain_session_audits WHERE agent=? AND host_id=? AND session_id=?",(agent,host_id,session_id)).fetchone()
            if previous:
                old=json.loads(previous["payload"])
                if all(old.get(k)==v for k,v in result.items() if k!="finalized_at"):
                    result=old
            c.execute("INSERT INTO brain_session_audits VALUES(?,?,?,?) ON CONFLICT(agent,host_id,session_id) DO UPDATE SET payload=excluded.payload",(agent,host_id,session_id,json.dumps(result)))
            return result

    # ------------------------------------------------------------------
    # Per-node feedback metrics for the UI panel
    # ------------------------------------------------------------------

    _STALE_DAYS_DEFAULT = 90

    def node_feedback_metrics(self, node_id: str, *, stale_days: int = _STALE_DAYS_DEFAULT) -> dict[str, object]:
        """Return outcome distribution + freshness signals for one node.

        Shape (stable for the UI panel — review requirement 3.2):

        * ``outcome_distribution`` — applied/failed/contradicted/not_used counts,
          the terminal denominator, and ``eligible`` (≥5 exposures).
        * ``last_retrieved_at`` — most recent ``last_used_at`` from the node row,
          plus ``last_outcome_at`` for the most recent outcome.
        * ``is_stale`` — True if the node has not been retrieved within
          ``stale_days`` (default 90).  Uses the node's ``last_used_at``
          when present; falls back to ``last_outcome_at`` when never
          retrieved but has recorded outcomes; otherwise ``None``.
        """
        from hermes.outcomes import (
            OutcomeObservation,
            TERMINAL_CLEAN_STATUSES,
            normalise_status,
        )

        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            node_row = connection.execute(
                "SELECT id, last_used_at, last_outcome_at FROM knowledge_nodes WHERE id = ?",
                (node_id,),
            ).fetchone()
            if node_row is None:
                return {
                    "node_id": node_id,
                    "found": False,
                    "outcome_distribution": {"applied": 0, "failed": 0, "contradicted": 0, "not_used": 0, "pending": 0, "exposures": 0, "eligible": 0},
                    "last_retrieved_at": None,
                    "last_outcome_at": None,
                    "is_stale": True,
                    "stale_days": stale_days,
                }
            outcome_rows = connection.execute(
                "SELECT retrieval_log_id, memory_id, helpfulness, used, created_at FROM outcome_log WHERE memory_id = ?",
                (node_id,),
            ).fetchall()

        observations = [
            OutcomeObservation(
                retrieval_log_id=str(o["retrieval_log_id"]),
                memory_id=str(o["memory_id"]),
                status=normalise_status(o["helpfulness"], used=bool(o["used"])),
                used=bool(o["used"]),
                exposure_key=f"{o['retrieval_log_id']}:{o['memory_id']}",
            )
            for o in outcome_rows
        ]

        hit_rates, _missing, _conflicts = _reduce_outcomes_safe(observations)
        node_rate = hit_rates.get(node_id)
        distribution = (
            node_rate.distribution()
            if node_rate is not None
            else {"applied": 0, "failed": 0, "contradicted": 0, "not_used": 0, "pending": 0, "exposures": 0, "eligible": 0}
        )

        last_retrieved_at = str(node_row["last_used_at"] or "") or None
        last_outcome_at = str(node_row["last_outcome_at"] or "") or None
        # Freshness anchor: prefer last retrieval; fall back to last outcome.
        anchor = last_retrieved_at or last_outcome_at
        is_stale = True
        if anchor:
            try:
                anchor_dt = datetime.fromisoformat(anchor)
                if anchor_dt.tzinfo is None:
                    anchor_dt = anchor_dt.replace(tzinfo=timezone.utc)
                is_stale = (now - anchor_dt).days >= stale_days
            except ValueError:
                is_stale = True

        return {
            "node_id": node_id,
            "found": True,
            "outcome_distribution": distribution,
            "last_retrieved_at": last_retrieved_at,
            "last_outcome_at": last_outcome_at,
            "is_stale": bool(is_stale),
            "stale_days": int(stale_days),
            "hit_rate": (node_rate.hit_rate if node_rate else 0.0),
        }

    # ------------------------------------------------------------------
    # Optional ranking (default disabled; opt-in only)
    # ------------------------------------------------------------------

    def rank_candidates(
        self,
        query: str,
        candidates: list[dict[str, object]],
        *,
        enabled: bool = False,
        limit: int = 5,
        reserve_for_new: int = 1,
        eligible_min_exposures: int = 5,
    ) -> list[dict[str, object]]:
        """Optional relevance-first + hit-rate rerank.

        Stage-1 contract: ``enabled`` defaults to ``False`` so the UI and
        the existing tests see no behavioural change.  When the caller
        opts in:

        1. Relevance first — keep the FTS ordering (caller-provided order).
        2. Apply hit-rate rerank **only within the eligible pool**
           (``exposures >= eligible_min_exposures``).
        3. Reserve ``reserve_for_new`` slots for the most-relevant node
           whose hit rate is below the eligibility threshold (the
           "待观察" queue from feedback.md §2.3).
        """
        from hermes.outcomes import (
            OutcomeObservation,
            TERMINAL_CLEAN_STATUSES,
            reduce_outcomes,
        )

        if not enabled or not candidates:
            return list(candidates[:limit])

        node_ids = [str(c.get("id") or "") for c in candidates if c.get("id")]
        if not node_ids:
            return list(candidates[:limit])

        placeholders = ",".join("?" * len(node_ids))
        with self._connect() as connection:
            outcome_rows = connection.execute(
                f"""SELECT retrieval_log_id, memory_id, helpfulness, used
                    FROM outcome_log WHERE memory_id IN ({placeholders})""",
                tuple(node_ids),
            ).fetchall()

        observations = [
            OutcomeObservation(
                retrieval_log_id=str(o["retrieval_log_id"]),
                memory_id=str(o["memory_id"]),
                status={"helpful": "applied", "harmful": "failed", "neutral": "not_used"}.get(
                    str(o["helpfulness"]).lower(), "pending"
                ),
                used=bool(o["used"]),
                exposure_key=f"{o['retrieval_log_id']}:{o['memory_id']}",
            )
            for o in outcome_rows
        ]
        hit_rates, _missing, _conflicts = reduce_outcomes(observations)

        # Bucket candidates by eligibility.
        eligible: list[dict[str, object]] = []
        newcomers: list[dict[str, object]] = []
        for c in candidates:
            nid = str(c.get("id") or "")
            rate = hit_rates.get(nid)
            if rate is not None and rate.eligible:
                eligible.append(c)
            else:
                newcomers.append(c)

        # Rerank eligible by hit_rate desc, then by original position.
        orig_index = {str(c.get("id") or ""): idx for idx, c in enumerate(candidates)}
        eligible.sort(
            key=lambda c: (
                -float(hit_rates[str(c.get("id") or "")].hit_rate),
                orig_index.get(str(c.get("id") or ""), 0),
            )
        )
        # Reserve slots for newcomers — pick the most-relevant newcomer
        # (i.e. earliest in the relevance order).
        reserve_count = max(0, min(reserve_for_new, len(newcomers)))
        reserved = newcomers[:reserve_count]
        eligible_pool = eligible[: max(0, limit - reserve_count)]
        return eligible_pool + reserved

    # ------------------------------------------------------------------
    # Knowledge stats + graph
    # ------------------------------------------------------------------

    def top_knowledge_nodes(self, limit: int = 10) -> list["KnowledgeNode"]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_nodes WHERE stage != 'deprecated' ORDER BY confidence DESC, retrieval_count DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [KnowledgeNode(**dict(r)) for r in rows]

    def knowledge_stats_full(self) -> dict:
        with self._connect() as connection:
            stages = {r["stage"]: r["cnt"] for r in connection.execute("SELECT stage, COUNT(*) as cnt FROM knowledge_nodes GROUP BY stage")}
            cats = {r["category"]: r["cnt"] for r in connection.execute("SELECT category, COUNT(*) as cnt FROM knowledge_nodes GROUP BY category")}
            total_retrievals = connection.execute("SELECT SUM(retrieval_count) FROM knowledge_nodes").fetchone()[0] or 0
            total_outcomes = connection.execute("SELECT SUM(outcome_count) FROM knowledge_nodes").fetchone()[0] or 0
            total_corrections = connection.execute("SELECT SUM(correction_count) FROM knowledge_nodes").fetchone()[0] or 0
            avg_conf = connection.execute("SELECT AVG(confidence) FROM knowledge_nodes WHERE stage != 'deprecated'").fetchone()[0] or 0
            ever_retrieved = connection.execute("SELECT COUNT(*) FROM knowledge_nodes WHERE retrieval_count > 0").fetchone()[0]
            ever_outcome = connection.execute("SELECT COUNT(*) FROM knowledge_nodes WHERE outcome_count > 0").fetchone()[0]
        return {
            "total": sum(stages.values()),
            "by_stage": stages,
            "categories": cats,
            "total_retrievals": total_retrievals,
            "total_outcomes": total_outcomes,
            "total_corrections": total_corrections,
            "avg_confidence": round(float(avg_conf), 2),
            "ever_retrieved": ever_retrieved,
            "ever_outcome": ever_outcome,
        }

    def knowledge_health_report(self) -> dict:
        """Full health report: pending, conflicts, quarantined, stale, dirty."""
        stats = self.knowledge_stats_full()
        with self._connect() as connection:
            pending = connection.execute("SELECT COUNT(*) FROM proposals WHERE state='pending'").fetchone()[0]
            no_evidence = connection.execute("SELECT COUNT(*) FROM knowledge_nodes WHERE (evidence='[]' OR evidence='' OR evidence IS NULL) AND stage != 'deprecated'").fetchone()[0]
            stale = connection.execute("SELECT COUNT(*) FROM knowledge_nodes WHERE last_used_at IS NULL AND stage IN ('canonized','verified','refined')").fetchone()[0]
            quarantined = connection.execute("SELECT COUNT(*) FROM knowledge_nodes WHERE stage='quarantined'").fetchone()[0]
            # Conflict signals: nodes with contradicts edges
            conflict_count = connection.execute(
                "SELECT COUNT(DISTINCT from_id) FROM memory_edges WHERE edge_type='contradicts'"
            ).fetchone()[0]
            # Dirty: chat_session category or empty summary
            dirty = connection.execute(
                "SELECT COUNT(*) FROM knowledge_nodes WHERE category='chat_session' OR summary='' OR summary IS NULL OR length(summary) < 10"
            ).fetchone()[0]
            # Top stale nodes (for surfacing)
            stale_nodes = connection.execute(
                "SELECT id, summary, last_used_at, retrieval_count FROM knowledge_nodes WHERE last_used_at IS NULL AND stage IN ('canonized','verified','refined') ORDER BY created_at ASC LIMIT 20"
            ).fetchall()
            # Top harmful (quarantined candidates)
            harmful = connection.execute(
                """SELECT kn.id, kn.summary, COUNT(ol.id) as harmful_count
                   FROM knowledge_nodes kn
                   JOIN outcome_log ol ON ol.memory_id = kn.id
                   WHERE ol.helpfulness = 'harmful'
                   GROUP BY kn.id HAVING harmful_count >= 2
                   ORDER BY harmful_count DESC LIMIT 10"""
            ).fetchall()
        status = "attention" if (pending or no_evidence or stale or quarantined or conflict_count or dirty) else "ok"
        return {
            **stats,
            "status": status,
            "stats": stats,
            "missing_metadata": 0,
            "pending_proposals": pending,
            "nodes_without_evidence": no_evidence,
            "stale_nodes": stale,
            "quarantined": quarantined,
            "conflict_count": conflict_count,
            "dirty_nodes": dirty,
            "stale_top": [{"id": r["id"], "summary": (r["summary"] or "")[:80], "last_used": r["last_used_at"]} for r in stale_nodes],
            "harmful_top": [{"id": r["id"], "summary": (r["summary"] or "")[:80], "count": r["harmful_count"]} for r in harmful],
        }

    def proposal_lifecycle_overview(self, limit: int = 40) -> dict:
        """Return lightweight read-only proposal lifecycle signals for the web UI."""
        with self._connect() as connection:
            stage_rows = connection.execute("SELECT stage, COUNT(*) AS total FROM knowledge_nodes GROUP BY stage").fetchall()
            operation_rows = connection.execute("SELECT operation, COUNT(*) AS total FROM knowledge_nodes GROUP BY operation ORDER BY total DESC").fetchall()
            active_rows = connection.execute(
                "SELECT id, summary, stage, operation, confidence, retrieval_count, outcome_count, parent_id, supersedes, merged_from, refined_at, last_used_at, created_at FROM knowledge_nodes WHERE stage != 'deprecated' ORDER BY (retrieval_count + outcome_count * 2) DESC, confidence DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            timeline_rows = connection.execute(
                "SELECT id, summary, stage, operation, confidence, retrieval_count, outcome_count, parent_id, supersedes, merged_from, refined_at, last_used_at, created_at FROM knowledge_nodes ORDER BY COALESCE(refined_at, verified_at, deprecated_at, created_at) DESC LIMIT ?",
                (limit,),
            ).fetchall()
            thought_rows = connection.execute(
                "SELECT tc.id, tc.node_id, tc.action, tc.decision, tc.confidence_in_decision, tc.created_at, kn.summary, kn.stage FROM thought_chains tc LEFT JOIN knowledge_nodes kn ON kn.id = tc.node_id ORDER BY tc.created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            decision_rows = connection.execute(
                "SELECT tc.id AS thought_id, tc.node_id, tc.action, tc.reasoning, tc.evidence_used, tc.decision, tc.confidence_in_decision, tc.created_at AS decision_at, kn.id, kn.summary, kn.stage, kn.operation, kn.confidence, kn.parent_id, kn.supersedes, kn.merged_from, kn.retrieval_count, kn.outcome_count, kn.created_at, kn.refined_at, kn.verified_at, kn.deprecated_at FROM thought_chains tc LEFT JOIN knowledge_nodes kn ON kn.id = tc.node_id WHERE tc.action IN ('dedup_check', 'merge', 'refine', 'contradiction_detect', 'canonize', 'outcome_recorded') ORDER BY tc.created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            retrieval_rows = connection.execute(
                "SELECT id, query, agent, host, node_ids, created_at, outcome_recorded_at FROM knowledge_retrieval_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            merge_count = connection.execute("SELECT COUNT(*) AS total FROM knowledge_nodes WHERE merged_from IS NOT NULL AND merged_from != '' AND merged_from != '[]'").fetchone()
            supersede_count = connection.execute("SELECT COUNT(*) AS total FROM knowledge_nodes WHERE supersedes IS NOT NULL AND supersedes != ''").fetchone()
        def _short_text(value, limit_chars=96):
            text = str(value or "").strip().replace("\\n", " ")
            return text[:limit_chars] + ("…" if len(text) > limit_chars else "")
        def _json_list(value):
            if not value: return []
            if isinstance(value, list): return [str(item) for item in value]
            try: return [str(item) for item in json.loads(str(value))]
            except: return []
        def _dict_row(row):
            d = dict(row)
            for k in ("summary", "observation", "why_it_matters", "suggested_memory"):
                if k in d: d[k] = _short_text(d.get(k, ""))
            return d
        return {
            "stages": {r["stage"]: r["total"] for r in stage_rows},
            "operations": {r["operation"]: r["total"] for r in operation_rows},
            "active": [_dict_row(r) for r in active_rows],
            "timeline": [_dict_row(r) for r in timeline_rows],
            "thought_chains": [_dict_row(r) for r in thought_rows],
            "decision_chains": [_dict_row(r) for r in decision_rows],
            "retrieval_events": [_dict_row(r) for r in retrieval_rows],
            "merge_count": merge_count["total"] if merge_count else 0,
            "supersede_count": supersede_count["total"] if supersede_count else 0,
            "proposal_sync": self.proposal_sync_status(),
            "embeddings": self.embedding_status(),
        }

    def get_knowledge_graph(self, limit: int = 200) -> dict:
        """Return nodes+edges for knowledge graph visualization (v3)."""
        with self._connect() as connection:
            edge_rows = connection.execute(
                "SELECT from_id, to_id, edge_type, evidence_id, created_at FROM memory_edges ORDER BY created_at DESC"
            ).fetchall()
            edge_ids = set()
            for row in edge_rows:
                edge_ids.add(row["from_id"])
                edge_ids.add(row["to_id"])
            edge_kn, edge_props = [], []
            if edge_ids:
                ph = ",".join(["?"] * len(edge_ids))
                edge_kn = connection.execute(
                    f"SELECT id, summary, content, category, domain, stage, confidence, retrieval_count, outcome_count, source, created_at, refined_at, last_used_at FROM knowledge_nodes WHERE id IN ({ph})",
                    tuple(edge_ids),
                ).fetchall()
                edge_props = connection.execute(
                    f"SELECT proposal_id, summary, observation, why_it_matters, suggested_memory, scope, evidence, category, project_key, state, risk_level, retrieval_count_30d, created_at, source_agent, source_host FROM proposals WHERE proposal_id IN ({ph})",
                    tuple(edge_ids),
                ).fetchall()
            remaining = limit - len(edge_kn) if edge_ids else limit
            extra_rows = []
            if remaining > 0 and edge_ids:
                extra_rows = connection.execute(
                    f"SELECT id, summary, content, category, domain, stage, confidence, retrieval_count, outcome_count, source, created_at, refined_at, last_used_at FROM knowledge_nodes WHERE stage != 'deprecated' AND id NOT IN ({ph}) ORDER BY retrieval_count DESC, confidence DESC LIMIT ?",
                    tuple(edge_ids) + (remaining,),
                ).fetchall()
            elif remaining > 0:
                extra_rows = connection.execute(
                    "SELECT id, summary, content, category, domain, stage, confidence, retrieval_count, outcome_count, source, created_at, refined_at, last_used_at FROM knowledge_nodes WHERE stage != 'deprecated' ORDER BY retrieval_count DESC, confidence DESC LIMIT ?",
                    (remaining,),
                ).fetchall()
        nodes = []
        seen = set()
        for row in list(edge_kn) + list(extra_rows):
            nid = row["id"]
            if nid in seen: continue
            seen.add(nid)
            is_dirty = (row["category"] or "") == "chat_session" or not (row["summary"] or "").strip() or len((row["summary"] or "").strip()) < 10
            nodes.append({"id": nid, "type": "knowledge", "summary": (row["summary"] or "")[:240], "content": (row["content"] or "")[:1200], "category": row["category"] or "fact", "domain": row["domain"] or "general", "stage": row["stage"] or "draft", "confidence": round(float(row["confidence"] or 0.3), 2), "retrieval_count": int(row["retrieval_count"] or 0), "outcome_count": int(row["outcome_count"] or 0), "source": (row["source"] or "")[:80], "created_at": row["created_at"] or "", "refined_at": row["refined_at"] or "", "last_used_at": row["last_used_at"] or "", "dirty": is_dirty})
        def _proposal_node(row) -> dict:
            state = row["state"] if row["state"] else ""
            return {
                "id": row["proposal_id"],
                "type": "proposal",
                "summary": (row["summary"] or "")[:240],
                "observation": (row["observation"] or "")[:800],
                "why_it_matters": (row["why_it_matters"] or "")[:500],
                "suggested_memory": (row["suggested_memory"] or "")[:800],
                "scope": (row["scope"] or "")[:200],
                "evidence": (row["evidence"] or "")[:1200],
                "category": row["category"] or "fact",
                "domain": row["project_key"] or "general",
                "stage": state or "pending",
                "confidence": 0.5,
                "retrieval_count": int(row["retrieval_count_30d"] or 0),
                "outcome_count": 0,
                "source": row["source_agent"] or "",
                "risk_level": row["risk_level"] or "",
                "created_at": row["created_at"] or "",
                "refined_at": "",
                "last_used_at": "",
            }

        for row in edge_props:
            pid = row["proposal_id"]
            state = row["state"] if row["state"] else ""
            if pid in seen: continue
            if state in ("rejected", "superseded"): continue
            seen.add(pid)
            nodes.append(_proposal_node(row))

        # Always surface pending proposals even if they have no edges yet,
        # so the review filter can show them with full decision fields.
        with self._connect() as connection:
            pending_rows = connection.execute(
                """
                SELECT proposal_id, summary, observation, why_it_matters, suggested_memory, scope, evidence,
                       category, project_key, state, risk_level, retrieval_count_30d, created_at, source_agent, source_host
                FROM proposals
                WHERE state = 'pending'
                ORDER BY created_at DESC
                LIMIT 100
                """
            ).fetchall()
        for row in pending_rows:
            pid = row["proposal_id"]
            if pid in seen:
                continue
            seen.add(pid)
            nodes.append(_proposal_node(row))

        edges = [{"from_id": r["from_id"], "to_id": r["to_id"], "edge_type": r["edge_type"], "evidence_id": r["evidence_id"] or "", "created_at": r["created_at"] or ""} for r in edge_rows]
        sc = {}
        for n in nodes: s = n["stage"]; sc[s] = sc.get(s, 0) + 1
        return {"nodes": nodes, "edges": edges, "stats": {"total_nodes": len(nodes), "total_edges": len(edges), "stage_counts": sc}}

    def list_proposals_ordered(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM proposals ORDER BY inserted_at DESC").fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Legacy migration
    # ------------------------------------------------------------------

    def migrate_proposals_to_knowledge_nodes(self) -> dict[str, int]:
        """Migrate existing proposals to knowledge_nodes table.

        Maps:
        - state 'approved_for_export' or 'approved_db_only' → stage 'canonized'
        - state 'pending' → stage 'draft'
        - state 'rejected' → skip
        - state 'superseded' → stage 'deprecated' with supersedes set
        - weight (0.5-5.0) → confidence (0.0-1.0) by dividing by 5.0

        Returns counts of migrated/skipped nodes.
        """
        migrated = 0
        skipped = 0
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as connection:
            proposals = connection.execute(
                "SELECT * FROM proposals ORDER BY inserted_at ASC"
            ).fetchall()

        for row in proposals:
            p = dict(row)
            state = str(p["state"] or "")
            # Skip rejected proposals
            if state == "rejected":
                skipped += 1
                continue

            # Check if already migrated (by proposal_id in id field)
            existing = self.get_knowledge_node(str(p["proposal_id"]))
            if existing is not None:
                skipped += 1
                continue

            # Map state → stage
            stage_map = {
                "approved_for_export": "canonized",
                "approved_db_only": "canonized",
                "pending": "draft",
                "superseded": "deprecated",
            }
            stage = stage_map.get(state, "draft")

            # Map weight → confidence
            old_weight = float(p.get("weight", 1.0))
            confidence = max(0.0, min(1.0, old_weight / 5.0))

            # Determine operation
            supersedes_id = p.get("supersedes")
            if supersedes_id:
                operation = "supersede"
            else:
                operation = "draft"

            # Map category (V1 categories → V2 categories)
            cat = str(p.get("category", "fact"))

            node = KnowledgeNode(
                id=str(p["proposal_id"]),
                parent_id=None,
                content=str(p.get("suggested_memory", "")),
                summary=str(p.get("summary", "")),
                category=cat,
                domain="general",
                stage=stage,
                operation=operation,
                confidence=round(confidence, 2),
                source=f"migration:{p['source_agent'] or 'unknown'}@{p['source_host'] or 'unknown'}",
                evidence=str(p.get("evidence", "[]")) if p.get("evidence") else "[]",
                supersedes=str(supersedes_id) if supersedes_id else None,
                merged_from="[]",
                contradicts="[]",
                verified_by="[]",
                created_at=str(p.get("inserted_at", now)),
                refined_at=str(p.get("inserted_at", now)) if stage in ("canonized", "verified") else None,
                verified_at=str(p.get("inserted_at", now)) if stage == "canonized" else None,
                deprecated_at=now if stage == "deprecated" else None,
                retrieval_count=int(p.get("retrieval_count_30d", 0) or 0),
                last_used_at=None,
                correction_count=0,
            )
            self.insert_knowledge_node(node)
            migrated += 1

        return {"migrated": migrated, "skipped": skipped}
