from __future__ import annotations

import json
import uuid
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
                    correction_count INTEGER NOT NULL DEFAULT 0
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
                CREATE INDEX IF NOT EXISTS idx_tc_action ON thought_chains(action);
                """
            )

            # -- Migration: add weight column if missing (pre-existing DBs) --
            try:
                connection.execute("ALTER TABLE proposals ADD COLUMN weight REAL NOT NULL DEFAULT 1.0")
            except Exception:
                pass  # Column already exists

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
        "project_key", "category", "risk_level", "summary", "observation",
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
        }
        payload = {k: v for k, v in row.items() if k in self._KN_COLUMNS}
        columns = ", ".join(payload)
        placeholders = ", ".join("?" for _ in payload)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO knowledge_nodes ({columns}) VALUES ({placeholders})",
                tuple(payload.values()),
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
            state = str(p.get("state", ""))
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
                source=f"migration:{p.get('source_agent', 'unknown')}@{p.get('source_host', 'unknown')}",
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
