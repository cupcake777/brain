from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
import uuid

import yaml

from hermes.sensitive import SensitiveContentError, default_gate


def _scan_payload_for_sensitive(payload: dict[str, object], *, field: str = "proposal") -> None:
    """Run the centralized SensitiveContentGate over a proposal payload.

    Wired into both ProposalWriter.write and the ingestion path so that a
    bearer token, API key, email, or IP address is rejected **before** any
    file is opened or DB row is inserted.  The gate is intentionally the
    SAME singleton used by HTTP request bodies so the contract matches
    ``brain-api-review-privacy.md`` ("centralized enforcement, fail-closed").
    """
    try:
        default_gate().check(payload, field=field)
    except SensitiveContentError:
        # Re-raise verbatim — the gate's message is already redacted and
        # we MUST NOT echo the payload or the matched substring.
        raise


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
        domain: str = "",
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
            "domain": domain,
            "status": "submitted",
        }
        if not front_matter["domain"]:
            from hermes.lane import assign_lane, lane_text
            front_matter["domain"] = assign_lane(
                hinted=domain,
                project_key=project_key,
                text=lane_text(summary, observation, suggested_memory),
            )
        body = ProposalBody(
            summary=summary,
            observation=observation,
            why_it_matters=why_it_matters,
            suggested_memory=suggested_memory,
            scope=scope,
            evidence=evidence,
        )
        payload = _format_proposal(front_matter, body)
        # Sensitive-content gate: reject the whole payload before any
        # file is created.  See hermes.sensitive + brain-api-review-privacy.md.
        _scan_payload_for_sensitive({"document": payload}, field="proposal")
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.rename(final_path)
        return final_path


def load_front_matter(path: str | Path) -> tuple[dict[str, str], str]:
    text = Path(path).read_text(encoding="utf-8")
    yaml_overlay: dict[str, str] = {}
    bare_fallback = False

    if text.startswith("---\n"):
        try:
            _, raw_front_matter, body = text.split("---\n", 2)
        except ValueError:
            # Malformed YAML delimiter — treat as bare markdown
            bare_fallback = True
            body = text
        else:
            yaml_overlay = yaml.safe_load(raw_front_matter) or {}
            if not isinstance(yaml_overlay, dict):
                yaml_overlay = {}
            missing = REQUIRED_FRONT_MATTER - set(yaml_overlay)
            if missing:
                # YAML frontmatter exists but incomplete — merge with bare markdown fallback
                # instead of rejecting.  Codex often writes minimal YAML (e.g. only type: + scope:)
                # and we auto-fill the rest from heading content.
                bare_fallback = True
                body = body.strip()
            else:
                return yaml_overlay, body.strip()
    else:
        bare_fallback = True
        body = text

    if not bare_fallback:
        return yaml_overlay, body.strip()

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
        "proposal_id": yaml_overlay.get("proposal_id", str(uuid.uuid4())),
        "source_agent": yaml_overlay.get("source_agent", yaml_overlay.get("type", "bare-markdown")),
        "source_host": yaml_overlay.get("source_host", "auto-ingest"),
        "created_at": yaml_overlay.get("created_at", datetime.now(timezone.utc).isoformat()),
        "project_key": yaml_overlay.get("project_key", "global"),
        "category": yaml_overlay.get("category", category),
        "risk_level": yaml_overlay.get("risk_level", risk),
        "status": yaml_overlay.get("status", "submitted"),
    }
    from hermes.lane import assign_lane, lane_text
    data["domain"] = assign_lane(
        hinted=yaml_overlay.get("domain", ""),
        project_key=data["project_key"],
        text=lane_text(summary, observation, why, mem),
    )
    # Preserve any extra YAML fields for downstream use
    for k, v in yaml_overlay.items():
        if k not in data:
            data[k] = str(v)
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

