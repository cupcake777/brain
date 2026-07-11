from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import logging
import re

from hermes.proposals import load_front_matter
from hermes.evidence import validate_evidence, extract_observations
from hermes.repository import HermesRepository
from hermes.notifier import NotificationRouter


ROUTE_MATRIX = {
    ("preference", "low"): "approved_db_only",
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
        from hermes.weight import compute_weight
        weight = compute_weight(
            category=front_matter["category"],
            risk_level=front_matter["risk_level"],
        )
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
                "weight": weight,
                "inserted_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # V3: Extract observations from evidence and insert into DB
        evidence_entries = []
        try:
            from hermes.evidence import parse_evidence_section, extract_observations
            evidence_entries = parse_evidence_section(sections.get("Evidence", ""))
            observations = extract_observations(evidence_entries, proposal_id)
            if observations:
                self.repo.insert_observations(observations)
        except Exception:
            pass  # Non-fatal: proposal is already stored

        # V3: Create memory edges for supersedes/contradicts
        supersedes = front_matter.get("supersedes", "")
        contradicts = front_matter.get("contradicts", "")
        if supersedes:
            try:
                self.repo.insert_memory_edge(proposal_id, supersedes, "supersedes")
            except Exception:
                pass
        if contradicts:
            try:
                self.repo.insert_memory_edge(proposal_id, contradicts, "contradicts")
            except Exception:
                pass
        if duplicate_of:
            try:
                self.repo.insert_memory_edge(proposal_id, duplicate_of, "duplicates")
            except Exception:
                pass

        self._dispatch_ingest_notifications(
            route=route,
            duplicate_of=duplicate_of,
            proposal_id=proposal_id,
            category=front_matter["category"],
            project_key=front_matter["project_key"],
            summary=sections["Summary"],
            suggested_memory=sections["Suggested durable memory"],
        )

        if route in {"approved_db_only", "approved_for_export"}:
            self._integrate_proposal(
                category=front_matter["category"],
                project_key=front_matter["project_key"],
                suggested_memory=sections["Suggested durable memory"],
                observation=sections["Observation"],
                source=f"proposal:{proposal_id[:12]}",
            )

        return IngestOutcome(proposal_id=proposal_id, route=route)

    def _integrate_proposal(
        self,
        *,
        category: str,
        project_key: str,
        suggested_memory: str,
        observation: str,
        source: str,
    ) -> None:
        """Integrate already-approved proposals into knowledge nodes."""
        try:
            from hermes.integrate import integrate as _integrate
            content = f"{suggested_memory}"
            if observation:
                content += f"\n\nObservation: {observation}"
            known_domains = {"devops", "network", "security", "study", "general"}
            if project_key and project_key in known_domains:
                domain = project_key
            elif project_key and project_key.strip():
                domain = project_key.strip().lower()
            else:
                domain = "general"
            cat_map = {"workflow_hint": "workflow_hint"}
            cat = cat_map.get(category, category if category in ("rule", "preference", "fact") else "fact")
            _integrate(
                content=content,
                source=source,
                category=cat,
                domain=domain,
                repo=self.repo,
            )
        except Exception as exc:  # noqa: BLE001
            logging.warning("Knowledge Node integration failed for %s: %s", source, exc)

    def _route(self, category: str, risk_level: str) -> str:
        return ROUTE_MATRIX.get((category, risk_level), "pending")

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

        event = {
            "pending": "pending_new",
            "approved_db_only": "approved_db_only",
            "approved_for_export": "auto_approved",
        }.get(route)
        if event is not None:
            self._router.dispatch(event, {
                "proposal_id": proposal_id,
                "category": category,
                "project_key": project_key,
                "summary": summary,
            })

    def _write_rejected(self, candidate: Path, reason: str) -> Path:
        target_dir = self.sync_root / "review" / "rejected"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"invalid-{candidate.stem}.md"
        target_path.write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")
        target_path.with_suffix(".reason").write_text(reason, encoding="utf-8")
        return target_path

_UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_MIN_CONTENT_LENGTH = 10  # characters — below this, content is likely garbage


def _is_garbage_content(text: str) -> bool:
    """Return True if the text looks like garbage (bare UUID, empty, too short)."""
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) < _MIN_CONTENT_LENGTH:
        return True
    if _UUID_PATTERN.match(stripped):
        return True
    return False


def _validate_sections(sections: dict[str, str]) -> None:
    """Validate proposal section content — reject proposals with garbage content."""
    summary = sections.get("Summary", "")
    observation = sections.get("Observation", "")
    why = sections.get("Why it matters", "")
    memory = sections.get("Suggested durable memory", "")

    if _is_garbage_content(summary):
        raise ValueError(
            f"proposal Summary is empty, too short, or just a UUID: {summary!r}"
        )

    # At least one of Observation/Why it matters/Suggested memory must have real content
    meaningful = [
        s for s in (observation, why, memory)
        if not _is_garbage_content(s)
    ]
    if not meaningful:
        raise ValueError(
            "proposal has no meaningful content in Observation, Why it matters, "
            "or Suggested durable memory sections"
        )

    # V3: Validate evidence section
    evidence_text = sections.get("Evidence", "")
    evidence_quality, _evidence_entries = validate_evidence(evidence_text)
    # Store quality in sections for downstream use
    sections["_evidence_quality"] = evidence_quality


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
    _validate_sections(sections)
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

