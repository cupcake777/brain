from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.exporter import ExportCompiler
from hermes.ingest import IngestionService
from hermes.proposals import ProposalWriter
from hermes.repository import HermesRepository


def test_review_endpoints_expose_pending_and_allow_approval(tmp_path) -> None:
    sync_root = tmp_path / "sync"
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    writer = ProposalWriter(sync_root / "inbox" / "proposals")
    ingest = IngestionService(repo=repo, sync_root=sync_root)
    compiler = ExportCompiler(repo=repo, sync_root=sync_root)
    app = create_app(repo=repo, sync_root=sync_root, exporter=compiler)
    client = TestClient(app)

    proposal_path = writer.write(
        source_agent="codex",
        source_host="macbook",
        project_key="brain",
        category="rule",
        risk_level="high",
        summary="Review UI should expose pending proposals.",
        observation="Pending proposals need web review.",
        why_it_matters="Without it, approval is bottlenecked.",
        suggested_memory="Provide approve/reject/export actions in the web UI.",
        scope="project",
        evidence="Manual design review.",
    )
    proposal_id = ingest.ingest_path(proposal_path).proposal_id

    pending = client.get("/api/review/pending")
    assert pending.status_code == 200
    assert pending.json()["items"][0]["proposal_id"] == proposal_id

    detail = client.get(f"/api/review/{proposal_id}")
    assert detail.status_code == 200
    assert detail.json()["proposal_id"] == proposal_id

    approve = client.post(f"/api/review/{proposal_id}/approve-for-export")
    assert approve.status_code == 200
    assert approve.json()["state"] == "approved_for_export"

    export_response = client.get("/exports/projects/brain.md")
    assert export_response.status_code == 200
    assert "Provide approve/reject/export actions in the web UI." in export_response.text


def test_review_html_pages_render_queue_and_detail(tmp_path) -> None:
    sync_root = tmp_path / "sync"
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    writer = ProposalWriter(sync_root / "inbox" / "proposals")
    ingest = IngestionService(repo=repo, sync_root=sync_root)
    app = create_app(repo=repo, sync_root=sync_root)
    client = TestClient(app)

    proposal_path = writer.write(
        source_agent="claude",
        source_host="vps",
        project_key="brain",
        category="rule",
        risk_level="high",
        summary="HTML review queue should show pending proposals.",
        observation="People need a quick browser review path.",
        why_it_matters="Review should not require raw DB access.",
        suggested_memory="Provide a browser queue and detail view for pending proposals.",
        scope="global",
        evidence="Design requirement.",
    )
    proposal_id = ingest.ingest_path(proposal_path).proposal_id

    queue = client.get("/review")
    assert queue.status_code == 200
    assert proposal_id in queue.text
    assert "Pending proposals" in queue.text

    detail = client.get(f"/review/{proposal_id}")
    assert detail.status_code == 200
    assert "Provide a browser queue and detail view for pending proposals." in detail.text
