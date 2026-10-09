from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from hermes.repository import HermesRepository


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_pending_proposals.py"


def _load():
    spec = importlib.util.spec_from_file_location("audit_pending", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _proposal(proposal_id: str, **overrides):
    row = {
        "proposal_id": proposal_id,
        "source_agent": "codex",
        "source_host": "hpc",
        "created_at": "2026-09-25T00:00:00+00:00",
        "project_key": "global",
        "category": "workflow_hint",
        "risk_level": "low",
        "domain": "tech",
        "summary": "Use a reusable verified workflow",
        "observation": "The workflow was verified on a real failure.",
        "why_it_matters": "The failure is likely to recur.",
        "suggested_memory": "Apply the verified workflow when the trigger recurs.",
        "scope": "global",
        "evidence": '[{"source_type":"test","source_uri":"test://pending","quoted_excerpt":"verified evidence"}]',
        "state": "pending",
        "semantic_hash": f"hash-{proposal_id}",
        "semantic_duplicate_of": None,
        "supersedes": None,
        "weight": 1.0,
        "inserted_at": "2026-09-25T00:00:00+00:00",
    }
    row.update(overrides)
    return row


def test_pending_audit_classifies_without_mutating_database(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    repo.insert_proposal(_proposal("valid-low"))
    repo.insert_proposal(_proposal("high-risk", risk_level="high"))
    repo.insert_proposal(_proposal("project-only", project_key="apa", scope="project"))
    repo.insert_proposal(_proposal("bad-evidence", evidence="generic prose"))
    repo.insert_proposal(_proposal("duplicate", semantic_duplicate_of="valid-low"))
    before = repo.counts_by_state()

    report = _load().audit_pending(tmp_path / "brain.sqlite3")

    assert repo.counts_by_state() == before
    assert report["total_pending"] == 5
    by_id = {item["proposal_id"]: item for item in report["items"]}
    assert by_id["valid-low"]["classification"] == "valid_reusable_global"
    assert by_id["high-risk"]["classification"] == "requires_human_review"
    assert by_id["project-only"]["classification"] == "project_specific"
    assert by_id["bad-evidence"]["classification"] == "invalid_evidence"
    assert by_id["duplicate"]["classification"] == "duplicate_or_superseded"
    assert all("suggested_memory" not in item for item in report["items"])


def test_pending_audit_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "brain.sqlite3")
    repo.insert_proposal(_proposal("valid-low", source_agent="bare-markdown", source_host="auto-ingest"))
    module = _load()
    report = module.audit_pending(tmp_path / "brain.sqlite3")

    json_path, md_path = module.write_reports(report, tmp_path / "reports", stamp="20260925T000000Z")

    assert json.loads(json_path.read_text())["total_pending"] == 1
    text = md_path.read_text()
    assert "valid_reusable_global" in text
    assert "attribution_unverified" in text
    assert "Use a reusable verified workflow" in text


def test_pending_audit_action_plan_is_non_executing_and_reversible(tmp_path: Path) -> None:
    db_path = tmp_path / "brain.sqlite3"
    repo = HermesRepository(db_path)
    repo.insert_proposal(_proposal("valid-low"))
    before = repo.get_proposal("valid-low")
    module = _load()
    report = module.audit_pending(db_path)

    plan_path = module.write_action_plan(report, tmp_path / "action-plan.json")

    plan = json.loads(plan_path.read_text())
    assert plan["mode"] == "plan_only_no_database_writes"
    assert plan["actions"] == [
        {
            "proposal_id": "valid-low",
            "classification": "valid_reusable_global",
            "recommended_action": "human_review_then_approve",
            "apply": False,
            "rollback": {"restore_state": "pending"},
        }
    ]
    assert repo.get_proposal("valid-low") == before


def test_pending_audit_cli_runs_from_project_root(tmp_path: Path) -> None:
    db_path = tmp_path / "brain.sqlite3"
    repo = HermesRepository(db_path)
    repo.insert_proposal(_proposal("valid-low"))
    output_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--db",
            str(db_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=SCRIPT.parents[1],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["total_pending"] == 1
