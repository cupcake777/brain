from __future__ import annotations

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.repository import HermesRepository


def _client(tmp_path):
    config = HermesConfig(sync_root=tmp_path, db_path=tmp_path / "brain.sqlite3")
    repo = HermesRepository(config.db_path)
    repo.insert_proposal(
        {
            "proposal_id": "proposal-editable",
            "source_agent": "xiaohe",
            "source_host": "local",
            "created_at": "2026-10-09T00:00:00+00:00",
            "project_key": "global",
            "category": "workflow_hint",
            "risk_level": "low",
            "domain": "infrastructure",
            "summary": "Old summary",
            "observation": "Old observation",
            "why_it_matters": "Old impact",
            "suggested_memory": "Old memory",
            "scope": "global",
            "evidence": "source: https://example.com\nexcerpt: old evidence",
            "state": "pending",
            "semantic_hash": "0" * 64,
        }
    )
    return TestClient(create_app(repo=repo, sync_root=tmp_path, config=config)), repo


def _valid_payload() -> dict[str, object]:
    return {
        "project_key": "global",
        "category": "workflow_hint",
        "risk_level": "medium",
        "domain": "infrastructure",
        "summary": "New structured summary",
        "observation": "A concrete observation with enough detail.",
        "why_it_matters": "This changes how later agents should operate.",
        "suggested_memory": "Use this durable, declarative memory entry.",
        "scope": "global",
        "evidence": [{
            "source_type": "url",
            "source_uri": "https://example.com/report",
            "quoted_excerpt": "concrete evidence",
        }],
    }


def test_edit_proposal_updates_only_editable_fields(tmp_path) -> None:
    client, repo = _client(tmp_path)

    response = client.put("/api/review/proposal-editable/edit", json=_valid_payload())

    assert response.status_code == 200
    updated = repo.get_proposal("proposal-editable")
    assert updated["summary"] == "New structured summary"
    assert updated["risk_level"] == "medium"
    assert updated["state"] == "pending"
    assert updated["source_agent"] == "xiaohe"
    assert len(str(updated["semantic_hash"])) == 64


def test_edit_proposal_rejects_missing_required_section(tmp_path) -> None:
    client, _repo = _client(tmp_path)
    payload = _valid_payload()
    payload["evidence"] = ""

    response = client.put("/api/review/proposal-editable/edit", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == "evidence is required"


def test_edit_proposal_rejects_unstructured_evidence(tmp_path) -> None:
    client, _repo = _client(tmp_path)
    payload = _valid_payload()
    payload["evidence"] = "source: https://example.com/report\nexcerpt: concrete evidence"

    response = client.put("/api/review/proposal-editable/edit", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == "evidence must be a non-empty list"


def test_edit_proposal_requires_complete_evidence_objects(tmp_path) -> None:
    client, _repo = _client(tmp_path)
    payload = _valid_payload()
    payload["evidence"] = [{"source_type": "url", "source_uri": "https://example.com/report"}]

    response = client.put("/api/review/proposal-editable/edit", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == "evidence[0] requires quoted_excerpt"


def test_edit_proposal_rejects_invalid_taxonomy_and_sensitive_content(tmp_path) -> None:
    client, _repo = _client(tmp_path)
    invalid = _valid_payload()
    invalid["category"] = "essay"
    assert client.put("/api/review/proposal-editable/edit", json=invalid).status_code == 422

    sensitive = _valid_payload()
    sensitive["evidence"] = [{
        "source_type": "test",
        "source_uri": "test://sensitive-content",
        "quoted_excerpt": "server observed at 203.0.113.9",
    }]
    response = client.put("/api/review/proposal-editable/edit", json=sensitive)
    assert response.status_code == 422
    assert "203.0.113.9" not in response.text


def test_edit_proposal_rejects_terminal_state(tmp_path) -> None:
    client, repo = _client(tmp_path)
    repo.transition_state("proposal-editable", "rejected")

    response = client.put("/api/review/proposal-editable/edit", json=_valid_payload())

    assert response.status_code == 409
