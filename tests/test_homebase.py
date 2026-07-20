from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.cassette import _agent_rows, _project_rows, _safe_review_href, cassette_page
from hermes.config import HermesConfig
from hermes.ingest import IngestionService
from hermes.proposals import ProposalWriter
from hermes.repository import HermesRepository


def _client(tmp_path: Path, *, auth: bool = False) -> tuple[HermesRepository, TestClient, Any]:
    sync_root = tmp_path / "sync"
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    config = HermesConfig(
        sync_root=sync_root,
        db_path=tmp_path / "hermes.sqlite3",
        auth_token="test-token" if auth else None,
        auth_username="owner" if auth else None,
        auth_password="test-password" if auth else None,
    )
    app = create_app(repo=repo, sync_root=sync_root, config=config)
    return repo, TestClient(app), app


def _add_pending_proposal(repo: HermesRepository, sync_root: Path) -> str:
    writer = ProposalWriter(sync_root / "inbox" / "proposals")
    proposal_path = writer.write(
        source_agent="homebase-test",
        source_host="test-host",
        project_key="brain",
        category="warning",
        risk_level="high",
        summary="Homebase live proposal requires a decision.",
        observation="A real pending proposal must appear on the home page.",
        why_it_matters="Static prototype data would hide the actual Brain queue.",
        suggested_memory="Render live Brain proposal counts and summaries on Homebase.",
        scope="project",
        evidence='[{"source_type":"test","source_uri":"test://homebase","quoted_excerpt":"Homebase must render real repository data."}]',
    )
    return IngestionService(repo=repo, sync_root=sync_root).ingest_path(proposal_path).proposal_id


def test_root_renders_homebase_with_live_brain_and_signal_data(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    board_path = tmp_path / "self/knowledge/daily-learnings/linuxdo-board.json"
    board_path.parent.mkdir(parents=True)
    board_path.write_text(
        '{"updated_at":"2026-07-19T07:30:00Z","items":[{"title":"Live signal from the Brain board","url":"https://example.test/live"},{"title":"Untrusted signal","url":"javascript:alert(1)"}]}',
        encoding="utf-8",
    )

    repo, client, _ = _client(tmp_path)
    proposal_id = _add_pending_proposal(repo, tmp_path / "sync")

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "<title>Homebase · Brain</title>" in html
    assert 'class="homebase-sidebar"' in html
    assert 'id="home-system-pulse"' in html
    assert 'id="home-attention"' in html
    assert 'id="home-servers"' in html
    assert 'id="home-agents"' in html
    assert 'id="home-projects"' in html
    assert 'id="home-signals"' in html
    assert "System Pulse" in html
    assert "Needs your attention" in html
    assert "Homebase live proposal requires a decision." in html
    assert proposal_id in html
    assert "Live signal from the Brain board" in html
    assert 'href="javascript:alert(1)"' not in html
    assert 'href="/linuxdo"' in html
    assert "INDEPENDENT PROTOTYPE" not in html
    assert "MOCK DATA" not in html


def test_cassette_design_route_is_isolated_and_uses_live_data(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    board_path = tmp_path / "self/knowledge/daily-learnings/linuxdo-board.json"
    board_path.parent.mkdir(parents=True)
    board_path.write_text(
        '{"updated_at":"2026-07-20T12:40:00Z","items":[{"title":"Signal received by the cassette deck","url":"https://example.test/cassette"}]}',
        encoding="utf-8",
    )
    repo, client, _ = _client(tmp_path)
    proposal_id = _add_pending_proposal(repo, tmp_path / "sync")

    home = client.get("/")
    candidate = client.get("/design/cassette")

    assert home.status_code == 200
    assert 'class="homebase-sidebar"' in home.text
    assert "cassette-workbench" not in home.text
    assert candidate.status_code == 200
    html = candidate.text
    assert "<title>Command Deck · Brain</title>" in html
    assert 'class="cassette-workbench"' in html
    assert 'id="deck-brief"' in html
    assert 'id="deck-next"' in html
    assert 'id="deck-fleet"' in html
    assert 'id="deck-agents"' in html
    assert 'id="deck-projects"' in html
    assert 'id="deck-signals"' in html
    assert html.index('id="deck-brief"') < html.index('id="deck-fleet"')
    assert html.index('id="deck-fleet"') < html.index('id="deck-projects"')
    assert "Homebase live proposal requires a decision." in html
    assert proposal_id in html
    assert "Signal received by the cassette deck" in html
    assert "/api/vps/fleet" in html
    assert "/api/dashboard/health" in html
    assert "System Pulse" not in html
    assert "pulse-score" not in html
    assert "metric-ring" not in html
    assert "overview-grid" not in html
    assert "homebase-sidebar" not in html
    assert "MOCK DATA" not in html


def test_cassette_review_href_encodes_untrusted_path_segments() -> None:
    assert _safe_review_href('abc/../../x\" onmouseover=\"alert(1)') == (
        "/review/abc%2F..%2F..%2Fx%22%20onmouseover%3D%22alert%281%29"
    )
    assert _safe_review_href("") == "/proposals"


def test_cassette_activity_rows_use_latest_timestamp() -> None:
    proposals = [
        {
            "project_key": "brain",
            "source_agent": "hermes",
            "state": "approved",
            "created_at": "2026-07-01T00:00:00Z",
        },
        {
            "project_key": "brain",
            "source_agent": "hermes",
            "state": "pending",
            "created_at": "2026-07-20T00:00:00Z",
        },
    ]

    projects = _project_rows(proposals)
    agents = _agent_rows(proposals)

    assert "latest 2026-07-20" in projects
    assert "Last Brain submission 2026-07-20" in agents
    assert "latest 2026-07-01" not in projects
    assert "Last Brain submission 2026-07-01" not in agents


def test_cassette_brief_tracks_pending_list_when_count_lags() -> None:
    html = cassette_page(
        node_counts={},
        proposal_counts={"pending": 0},
        knowledge_health={},
        lifecycle_overview={},
        pending_proposals=[
            {
                "proposal_id": "pending-one",
                "summary": "A queued decision",
                "risk_level": "low",
            }
        ],
        all_proposals=[],
        linuxdo_board={},
    )

    assert "1 item need a look." in html
    assert "Review decision" in html
    assert "Nothing asks for you right now." not in html


def test_cassette_maintenance_meta_includes_quarantine() -> None:
    html = cassette_page(
        node_counts={},
        proposal_counts={"pending": 0},
        knowledge_health={"quarantined": 2},
        lifecycle_overview={},
        pending_proposals=[],
        all_proposals=[],
        linuxdo_board={},
    )

    assert "2 items need a look." in html
    assert "2 quarantined" in html


def test_homebase_preserves_auth_and_existing_business_routes(tmp_path: Path) -> None:
    _, client, app = _client(tmp_path, auth=True)

    unauthenticated = client.get("/", follow_redirects=False)
    assert unauthenticated.status_code == 303
    assert unauthenticated.headers["location"] == "/login"

    candidate_unauthenticated = client.get("/design/cassette", follow_redirects=False)
    assert candidate_unauthenticated.status_code == 303
    assert candidate_unauthenticated.headers["location"] == "/login"

    login = client.post(
        "/login",
        data={"username": "owner", "password": "test-password"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert login.headers["location"] == "/"
    assert client.get("/").status_code == 200
    assert client.get("/design/cassette").status_code == 200

    route_paths = {route.path for route in app.routes}
    assert {
        "/overview",
        "/design/cassette",
        "/proposals",
        "/knowledge",
        "/control",
        "/fleet",
        "/hub",
        "/linuxdo",
        "/gallery",
        "/settings",
        "/profile",
        "/api/review/pending",
        "/api/knowledge/list",
        "/api/dashboard/health",
        "/api/dashboard/resources",
        "/api/vps/fleet",
    } <= route_paths
