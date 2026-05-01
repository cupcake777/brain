from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
import uuid

import yaml


REQUIRED_FRONT_MATTER = {
    "proposal_id",
    "source_agent",
    "source_host",
    "created_at",
    "project_key",
    "category",
    "risk_level",
    "status",
}


@dataclass(frozen=True)
class ProposalBody:
    summary: str
    observation: str
    why_it_matters: str
    suggested_memory: str
    scope: str
    evidence: str


class ProposalWriter:
    def __init__(self, inbox_dir: str | Path) -> None:
        self.inbox_dir = Path(inbox_dir)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        *,
        source_agent: str,
        source_host: str,
        project_key: str,
        category: str,
        risk_level: str,
        summary: str,
        observation: str,
        why_it_matters: str,
        suggested_memory: str,
        scope: str,
        evidence: str,
    ) -> Path:
        proposal_id = str(uuid.uuid4())
        tmp_path = self.inbox_dir / f".tmp-{proposal_id}.md"
        final_path = self.inbox_dir / f"{proposal_id}.md"
        front_matter = {
            "proposal_id": proposal_id,
            "source_agent": source_agent,
            "source_host": source_host,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "project_key": project_key,
            "category": category,
            "risk_level": risk_level,
            "status": "submitted",
        }
        body = ProposalBody(
            summary=summary,
            observation=observation,
            why_it_matters=why_it_matters,
            suggested_memory=suggested_memory,
            scope=scope,
            evidence=evidence,
        )
        payload = _format_proposal(front_matter, body)
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.rename(final_path)
        return final_path


def load_front_matter(path: str | Path) -> tuple[dict[str, str], str]:
    text = Path(path).read_text(encoding="utf-8")
    if text.startswith("---\n"):
        _, raw_front_matter, body = text.split("---\n", 2)
        data = yaml.safe_load(raw_front_matter) or {}
        missing = REQUIRED_FRONT_MATTER - set(data)
        if missing:
            raise ValueError(f"proposal is missing required fields: {sorted(missing)}")
        return data, body.strip()

    # --- Bare Markdown fallback: auto-generate front matter ---
    # Codex and other agents sometimes write proposals as plain Markdown
    # with headings but no YAML front matter. Rather than rejecting them,
    # we extract structure from the headings and apply sensible defaults.
    import re
    sections: dict[str, str] = {}
    current_heading: str | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        heading_match = re.match(r"^(#+)\s+(.+)$", line)
        if heading_match:
            if current_heading is not None:
                sections[current_heading] = "\n".join(buffer).strip()
            current_heading = heading_match.group(2).strip()
            buffer = []
        else:
            buffer.append(line)
    if current_heading is not None:
        sections[current_heading] = "\n".join(buffer).strip()

    # Try to map common heading names to canonical section names
    heading_map = {
        "summary": "Summary",
        "observation": "Observation",
        "context": "Observation",
        "why_it_matters": "Why it matters",
        "why": "Why it matters",
        "rationale": "Why it matters",
        "suggested_memory": "Suggested durable memory",
        "suggested durable memory": "Suggested durable memory",
        "memory": "Suggested durable memory",
        "scope": "Scope",
        "evidence": "Evidence",
        "rule": "Summary",
        "error_to_avoid": "Observation",
        "error to avoid": "Observation",
        "error to fix mapping": "Observation",
        "trigger": "Evidence",
        "trigger examples": "Evidence",
    }
    mapped: dict[str, str] = {}
    for key, value in sections.items():
        canonical = heading_map.get(key.lower().strip(), None)
        if canonical:
            mapped[canonical] = value
        elif not mapped.get("Summary"):
            # First unrecognised heading with substantial content becomes summary
            mapped["Summary"] = value

    # Determine risk level and category from content heuristics
    content_lower = text.lower()
    if any(kw in content_lower for kw in ["must not", "never", "prohibit", "forbid", "禁止"]):
        risk = "high"
        category = "rule"
    elif any(kw in content_lower for kw in ["always", "should", "prefer", "avoid"]):
        risk = "medium"
        category = "rule"
    else:
        risk = "low"
        category = "workflow_hint"

    # Use the first heading or filename as summary fallback
    summary = mapped.get("Summary", sections.get("Rule", list(sections.values())[0] if sections else Path(path).stem))
    observation = mapped.get("Observation", "")
    why = mapped.get("Why it matters", "")
    mem = mapped.get("Suggested durable memory", f"{summary}")
    scope = mapped.get("Scope", "global")
    evidence = mapped.get("Evidence", "")

    # Reconstruct body in canonical format
    canonical_body = (
        f"# Summary\n{summary}\n\n"
        f"## Observation\n{observation}\n\n"
        f"## Why it matters\n{why}\n\n"
        f"## Suggested durable memory\n{mem}\n\n"
        f"## Scope\n{scope}\n\n"
        f"## Evidence\n{evidence}"
    )

    data = {
        "proposal_id": str(uuid.uuid4()),
        "source_agent": "bare-markdown",
        "source_host": "auto-ingest",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_key": "global",
        "category": category,
        "risk_level": risk,
        "status": "submitted",
    }
    return data, canonical_body


def _format_proposal(front_matter: dict[str, str], body: ProposalBody) -> str:
    yaml_block = yaml.safe_dump(front_matter, sort_keys=False).strip()
    return (
        f"---\n{yaml_block}\n---\n\n"
        f"# Summary\n{body.summary}\n\n"
        f"## Observation\n{body.observation}\n\n"
        f"## Why it matters\n{body.why_it_matters}\n\n"
        f"## Suggested durable memory\n{body.suggested_memory}\n\n"
        f"## Scope\n{body.scope}\n\n"
        f"## Evidence\n{body.evidence}\n"
    )

