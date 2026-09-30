from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.repository import HermesRepository
from hermes.runtime import HermesRuntime


PROPOSAL_ID = "11111111-1111-4111-8111-111111111111"


def _stack(tmp_path: Path) -> tuple[TestClient, HermesRepository, HermesConfig]:
    sync_root = tmp_path / "sync"
    config = HermesConfig(sync_root=sync_root, db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)
    return TestClient(create_app(repo=repo, sync_root=sync_root, config=config)), repo, config


def _proposal(*, evidence: str, proposal_id: str = PROPOSAL_ID) -> str:
    return f"""---
proposal_id: {proposal_id}
source_agent: codex
source_host: hpc-login
created_at: 2026-09-25T00:00:00+00:00
project_key: global
category: workflow_hint
risk_level: low
status: submitted
---

# Summary
Validate proposal evidence before reporting success.

## Observation
A transport-level HTTP success can still contain an invalid proposal.

## Why it matters
Agents otherwise report learning that never entered the durable database.

## Suggested durable memory
Treat a proposal as received only after structured validation succeeds.

## Scope
global

## Evidence
{evidence}
"""


def test_legacy_submit_rejects_invalid_evidence_without_leaving_inbox_file(tmp_path: Path) -> None:
    client, _repo, config = _stack(tmp_path)

    response = client.post(
        "/api/proposals/submit",
        json={
            "content": _proposal(evidence="generic prose without a session id, path, or URL"),
            "filename": "invalid.md",
        },
    )

    assert response.status_code == 422
    assert response.json()["status"] == "rejected"
    assert "no valid evidence entries" in response.json()["reason"]
    assert not (config.proposals_dir / "invalid.md").exists()


def test_legacy_submit_returns_202_only_after_structured_validation(tmp_path: Path) -> None:
    client, _repo, config = _stack(tmp_path)

    response = client.post(
        "/api/proposals/submit",
        json={
            "content": _proposal(
                evidence='[{"source_type":"file","source_uri":"/tmp/evidence.log","quoted_excerpt":"Exact non-secret runtime evidence."}]'
            ),
            "filename": "valid.md",
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "validated"
    assert response.json()["proposal_id"] == PROPOSAL_ID
    assert (config.proposals_dir / "valid.md").exists()


def test_legacy_submit_returns_409_for_existing_proposal(tmp_path: Path) -> None:
    client, repo, config = _stack(tmp_path)
    payload = {
        "content": _proposal(
            evidence='[{"source_type":"file","source_uri":"/tmp/evidence.log","quoted_excerpt":"Exact non-secret runtime evidence."}]'
        ),
        "filename": "valid.md",
    }
    first = client.post("/api/proposals/submit", json=payload)
    assert first.status_code == 202
    scan = HermesRuntime(config=config, repo=repo).run_scan_cycle()
    assert scan.ingested_count == 1

    duplicate = client.post("/api/proposals/submit", json=payload)

    assert duplicate.status_code == 409
    assert duplicate.json()["status"] == "duplicate"
    assert duplicate.json()["proposal_id"] == PROPOSAL_ID
    assert not (config.proposals_dir / "valid.md").exists()
