#!/usr/bin/env python3
"""Read-only pending-proposal audit and rollback-plan generator."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hermes.evidence import validate_evidence


_VALID_SCOPES = {"global", "project"}


def _classification(row: sqlite3.Row) -> tuple[str, list[str], str]:
    reasons: list[str] = []
    try:
        quality, _entries = validate_evidence(str(row["evidence"] or ""))
    except ValueError:
        return "invalid_evidence", ["evidence_missing_or_invalid"], "none"

    if row["semantic_duplicate_of"] or row["supersedes"]:
        reasons.append("duplicate_or_supersession_marker")
        return "duplicate_or_superseded", reasons, quality

    risk = str(row["risk_level"] or "").strip().lower()
    if risk != "low":
        reasons.append(f"risk_level:{risk or 'missing'}")
        return "requires_human_review", reasons, quality

    scope = str(row["scope"] or "").strip().lower()
    project_key = str(row["project_key"] or "").strip()
    if scope not in _VALID_SCOPES:
        reasons.append(f"invalid_scope:{scope or 'missing'}")
        return "requires_human_review", reasons, quality
    if scope == "project" or (project_key and project_key != "global"):
        reasons.append(f"project_key:{project_key or 'missing'}")
        return "project_specific", reasons, quality

    return "valid_reusable_global", reasons, quality


def audit_pending(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path)
    uri = f"file:{path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT proposal_id, source_agent, source_host, created_at,
                      inserted_at, project_key, category, risk_level, domain,
                      summary, scope, evidence, semantic_duplicate_of, supersedes
                 FROM proposals
                WHERE state = 'pending'
                ORDER BY inserted_at ASC, proposal_id ASC"""
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        classification, reasons, evidence_quality = _classification(row)
        source_agent = str(row["source_agent"] or "")
        source_host = str(row["source_host"] or "")
        attribution = (
            "unverified"
            if source_agent in {"", "bare-markdown"} or source_host in {"", "auto-ingest"}
            else "declared"
        )
        items.append(
            {
                "proposal_id": row["proposal_id"],
                "classification": classification,
                "reasons": reasons,
                "summary": row["summary"],
                "category": row["category"],
                "risk_level": row["risk_level"],
                "domain": row["domain"],
                "scope": row["scope"],
                "project_key": row["project_key"],
                "source_agent": source_agent,
                "source_host": source_host,
                "attribution": attribution,
                "evidence_quality": evidence_quality,
                "created_at": row["created_at"],
                "inserted_at": row["inserted_at"],
            }
        )

    counts = Counter(item["classification"] for item in items)
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(path.resolve()),
        "mode": "read_only",
        "total_pending": len(items),
        "classifications": dict(sorted(counts.items())),
        "items": items,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Brain Pending Proposal Audit",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Database: `{report['database']}`",
        f"- Mode: `{report['mode']}`",
        f"- Pending: **{report['total_pending']}**",
        "",
        "## Classification counts",
        "",
    ]
    for name, count in report["classifications"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(["", "## Items", ""])
    for item in report["items"]:
        tags = [item["classification"], f"evidence:{item['evidence_quality']}"]
        if item["attribution"] == "unverified":
            tags.append("attribution_unverified")
        lines.append(f"### {item['proposal_id']}")
        lines.append(f"- Classification: `{item['classification']}`")
        lines.append(f"- Summary: {item['summary']}")
        lines.append(f"- Tags: {', '.join(f'`{tag}`' for tag in tags)}")
        lines.append(
            f"- Source: `{item['source_agent'] or 'missing'}` / "
            f"`{item['source_host'] or 'missing'}`"
        )
        lines.append(
            f"- Scope: `{item['scope']}`; project: `{item['project_key']}`; "
            f"risk: `{item['risk_level']}`"
        )
        if item["reasons"]:
            lines.append(f"- Reasons: {', '.join(item['reasons'])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_reports(
    report: dict[str, Any], output_dir: str | Path, *, stamp: str | None = None
) -> tuple[Path, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    label = stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = target / f"pending-audit-{label}.json"
    md_path = target / f"pending-audit-{label}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    md_path.write_text(_markdown(report))
    return json_path, md_path


def write_action_plan(report: dict[str, Any], path: str | Path) -> Path:
    """Write a non-executing, reversible review plan; never mutate the DB."""
    actions = []
    for item in report["items"]:
        classification = item["classification"]
        action = {
            "proposal_id": item["proposal_id"],
            "classification": classification,
            "recommended_action": {
                "valid_reusable_global": "human_review_then_approve",
                "requires_human_review": "human_review",
                "project_specific": "route_to_project_review",
                "invalid_evidence": "reject_or_request_resubmission",
                "duplicate_or_superseded": "confirm_duplicate_then_reject",
            }[classification],
            "apply": False,
            "rollback": {"restore_state": "pending"},
        }
        actions.append(action)
    payload = {
        "schema": 1,
        "generated_at": report["generated_at"],
        "database": report["database"],
        "mode": "plan_only_no_database_writes",
        "actions": actions,
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database to open read-only")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--action-plan", help="Optional plan-only JSON output")
    args = parser.parse_args()

    report = audit_pending(args.db)
    json_path, md_path = write_reports(report, args.output_dir)
    result: dict[str, Any] = {
        "total_pending": report["total_pending"],
        "classifications": report["classifications"],
        "json_report": str(json_path),
        "markdown_report": str(md_path),
    }
    if args.action_plan:
        result["action_plan"] = str(write_action_plan(report, args.action_plan))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
