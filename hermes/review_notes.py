"""Human-readable, attributed reviews. Recommendations never approve knowledge."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

_FIELDS = {
    "proposal": ("proposal_id", "summary", "observation", "why_it_matters", "suggested_memory", "scope", "evidence", "category", "risk_level", "domain", "project_key"),
    "knowledge": ("id", "summary", "content", "evidence", "category", "domain", "use_when", "avoid_when"),
}
DISPOSITIONS = {
    "retain": "建议保留", "scope": "限定环境后保留", "verify": "需要补证",
    "merge": "建议合并", "archive": "建议归档", "conflict": "有冲突，需核对",
}


class ReviewNotes:
    def __init__(self, repo):
        self.repo = repo
        with repo._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS editorial_reviews (
                id TEXT PRIMARY KEY, entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL, content_digest TEXT NOT NULL,
                reviewer TEXT NOT NULL, session_id TEXT NOT NULL,
                title_zh TEXT NOT NULL, summary_zh TEXT NOT NULL,
                disposition TEXT NOT NULL, reasoning TEXT NOT NULL,
                next_step TEXT NOT NULL, related_id TEXT NOT NULL DEFAULT '',
                evidence_check TEXT NOT NULL DEFAULT 'submitted_text_only',
                reviewed_at TEXT NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS editorial_reviews_entity ON editorial_reviews(entity_type, entity_id, reviewed_at DESC)")

    def digest(self, kind: str, item: dict) -> str:
        with self.repo._connect() as conn:
            return self._digest(kind, item, conn)

    def _digest(self, kind: str, item: dict, conn) -> str:
        fields = _FIELDS[kind]
        payload = {field: item.get(field, "") for field in fields}
        entity_id = str(item.get("proposal_id") if kind == "proposal" else item.get("id"))
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='brain_environment_scopes'").fetchone()
        if exists:
            scope = conn.execute("SELECT * FROM brain_environment_scopes WHERE entity_type=? AND entity_id=?", (kind, entity_id)).fetchone()
            payload["environment_scope"] = dict(scope) if scope else None
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()

    def all(self, kind: str) -> dict[str, dict]:
        with self.repo._connect() as conn:
            rows = conn.execute("SELECT * FROM editorial_reviews WHERE entity_type=? ORDER BY reviewed_at,id", (kind,)).fetchall()
        return {row["entity_id"]: dict(row) for row in rows}

    def attach(self, kind: str, items: list[dict]) -> list[dict]:
        notes = self.all(kind)
        result = []
        for item in items:
            item = dict(item)
            key = str(item.get("proposal_id") if kind == "proposal" else item.get("id"))
            note = notes.get(key)
            item["editorial_review"] = note if note and note["content_digest"] == self.digest(kind, item) else None
            item["review_outdated"] = bool(note and not item["editorial_review"])
            result.append(item)
        return result

    def record(self, kind: str, item: dict, *, reviewer: str, session_id: str,
               title_zh: str, summary_zh: str, disposition: str, reasoning: str,
               next_step: str, related_id: str = "", expected_digest: str) -> str:
        if kind not in _FIELDS or disposition not in DISPOSITIONS:
            raise ValueError("invalid entity type or recommendation")
        values = (reviewer, session_id, title_zh, summary_zh, reasoning, next_step)
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError("review identity and substantive review fields are required")
        entity_id = str(item.get("proposal_id") if kind == "proposal" else item.get("id"))
        record_id = str(uuid4())
        with self.repo._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            table, key = ("proposals", "proposal_id") if kind == "proposal" else ("knowledge_nodes", "id")
            current = conn.execute(f"SELECT * FROM {table} WHERE {key}=?", (entity_id,)).fetchone()
            if current is None:
                raise ValueError("review target no longer exists")
            if self._digest(kind, item, conn) != expected_digest or self._digest(kind, dict(current), conn) != expected_digest:
                raise ValueError("content changed since review")
            conn.execute("""INSERT INTO editorial_reviews (id,entity_type,entity_id,content_digest,reviewer,session_id,title_zh,summary_zh,disposition,reasoning,next_step,related_id,evidence_check,reviewed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                record_id, kind, entity_id, expected_digest, reviewer, session_id,
                title_zh, summary_zh, disposition, reasoning, next_step, related_id,
                "submitted_text_only", datetime.now(timezone.utc).isoformat(),
            ))
        return record_id
