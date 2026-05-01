from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from hermes.proposals import load_front_matter
from hermes.repository import HermesRepository
from hermes.notifier import NotificationRouter


AUTO_APPROVE_MATRIX = {
    ("preference", "low"): "approved_db_only",
    ("fact", "low"): "approved_db_only",
    ("workflow_hint", "low"): "approved_db_only",
}


@dataclass(frozen=True)
class IngestOutcome:
    proposal_id: str
    route: str


class IngestionService:
    def __init__(
        self,
        *,
        repo: HermesRepository,
        sync_root: str | Path,
        auto_approve_low_risk: bool = True,
        notification_router: NotificationRouter | None = None,
    ) -> None:
        self.repo = repo
        self.sync_root = Path(sync_root)
        self.auto_approve_low_risk = auto_approve_low_risk
        self._router = notification_router

    def ingest_path(self, path: str | Path) -> IngestOutcome:
        candidate = Path(path)
        if candidate.name.startswith(".tmp-") or ".sync-conflict-" in candidate.name:
            raise ValueError("temporary/conflict files must not be ingested")

        try:
            front_matter, body = load_front_matter(candidate)
        except Exception as exc:  # noqa: BLE001
            rejected_path = self._write_rejected(candidate, str(exc))
            raise ValueError(f"invalid proposal: {rejected_path}") from exc

        proposal_id = str(front_matter["proposal_id"])
        if self.repo.has_proposal(proposal_id):
            stored = self.repo.get_proposal(proposal_id)
            return IngestOutcome(proposal_id=proposal_id, route=str(stored["state"]))

        sections = _parse_sections(body)
        semantic_hash = _compute_semantic_hash(body)
        duplicate_of = self.repo.find_by_semantic_hash(semantic_hash)
        route = self._route(front_matter["category"], front_matter["risk_level"])
        self.repo.insert_proposal(
            {
                "proposal_id": proposal_id,
                "source_agent": front_matter["source_agent"],
                "source_host": front_matter["source_host"],
                "created_at": front_matter["created_at"],
                "project_key": front_matter["project_key"],
                "category": front_matter["category"],
                "risk_level": front_matter["risk_level"],
                "summary": sections["Summary"],
                "observation": sections["Observation"],
                "why_it_matters": sections["Why it matters"],
                "suggested_memory": sections["Suggested durable memory"],
                "scope": sections["Scope"],
                "evidence": sections["Evidence"],
                "state": route,
                "semantic_hash": semantic_hash,
                "semantic_duplicate_of": duplicate_of,
                "supersedes": None,
                "inserted_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # -- best-effort notifications ----------------------------------------
        self._dispatch_ingest_notifications(
            route=route,
            duplicate_of=duplicate_of,
            proposal_id=proposal_id,
            category=front_matter["category"],
            project_key=front_matter["project_key"],
            summary=sections["Summary"],
            suggested_memory=sections["Suggested durable memory"],
        )

        return IngestOutcome(proposal_id=proposal_id, route=route)

    def _route(self, category: str, risk_level: str) -> str:
        if category == "rule":
            return "pending"
        if self.auto_approve_low_risk and AUTO_APPROVE_MATRIX.get((category, risk_level)) == "approved_db_only":
            return "approved_db_only"
        return "pending"

    def _dispatch_ingest_notifications(
        self,
        *,
        route: str,
        duplicate_of: str | None,
        proposal_id: str,
        category: str,
        project_key: str,
        summary: str,
        suggested_memory: str,
    ) -> None:
        """Fire best-effort notification(s) for the just-ingested proposal."""
        if self._router is None:
            return

        if duplicate_of is not None:
            self._router.dispatch("duplicate_detected", {
                "new_id": proposal_id,
                "original_id": duplicate_of,
                "suggested_memory": suggested_memory,
            })

        if route == "approved_db_only":
            self._router.dispatch("auto_approved", {
                "proposal_id": proposal_id,
                "category": category,
            })
        else:
            self._router.dispatch("pending_new", {
                "proposal_id": proposal_id,
                "category": category,
                "summary": summary,
                "project_key": project_key,
            })

    def _write_rejected(self, candidate: Path, reason: str) -> Path:
        target_dir = self.sync_root / "review" / "rejected"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"invalid-{candidate.stem}.md"
        target_path.write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")
        target_path.with_suffix(".reason").write_text(reason, encoding="utf-8")
        return target_path


def _parse_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_heading: str | None = None
    buffer: list[str] = []
    for line in body.splitlines():
        heading_match = re.match(r"^(#|##)\s+(.+)$", line)
        if heading_match:
            if current_heading is not None:
                sections[current_heading] = "\n".join(buffer).strip()
            current_heading = heading_match.group(2).strip()
            buffer = []
        else:
            buffer.append(line)
    if current_heading is not None:
        sections[current_heading] = "\n".join(buffer).strip()

    required = {"Summary", "Observation", "Why it matters", "Suggested durable memory", "Scope", "Evidence"}
    missing = required - sections.keys()
    if missing:
        raise ValueError(f"proposal body is missing sections: {sorted(missing)}")
    return sections


def _compute_semantic_hash(body: str) -> str:
    normalized = []
    for line in body.splitlines():
        if line.strip().lower().startswith("evidence_refs:"):
            continue
        normalized.append(line.strip().lower())
    collapsed = " ".join(part for part in normalized if part)
    collapsed = re.sub(r"\s+", " ", collapsed).strip()
    return sha256(collapsed.encode("utf-8")).hexdigest()

