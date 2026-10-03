from html.parser import HTMLParser
from pathlib import Path
from typing import Any
import inspect

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.homebase import home_page
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


def test_root_renders_engram_home_with_only_knowledge_and_gallery_modules(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    board_path = tmp_path / "self/knowledge/daily-learnings/linuxdo-board.json"
    board_path.parent.mkdir(parents=True)
    board_path.write_text(
        '{"updated_at":"2026-07-19T07:30:00Z","items":[{"title":"Infrastructure signal that must not leak into Home","url":"https://example.test/live"}]}',
        encoding="utf-8",
    )

    repo, client, _ = _client(tmp_path)
    proposal_id = _add_pending_proposal(repo, tmp_path / "sync")

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "<title>Engram · Brain</title>" in html
    assert 'class="engram-home"' in html
    assert 'id="engram-ledger"' in html
    assert 'id="engram-knowledge"' in html
    assert 'id="engram-gallery"' in html
    assert 'href="/knowledge"' in html
    assert 'href="/gallery"' in html
    assert 'href="/opening/"' in html
    assert "Homebase live proposal requires a decision." in html
    assert proposal_id in html

    forbidden = (
        "homebase-sidebar",
        "home-system-pulse",
        "home-servers",
        "home-agents",
        "home-projects",
        "home-signals",
        "System Pulse",
        "Infrastructure signal that must not leak into Home",
        'href="/fleet"',
        'href="/hub"',
        'href="/linuxdo"',
        'href="/control"',
        "/api/vps/fleet",
        "/api/dashboard/health",
        "/api/render",
    )
    assert not [marker for marker in forbidden if marker in html]
    assert "INDEPENDENT PROTOTYPE" not in html
    assert "MOCK DATA" not in html


def test_root_does_not_collect_infrastructure_or_linuxdo_data(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    board_path = tmp_path / "self/knowledge/daily-learnings/linuxdo-board.json"
    board_path.parent.mkdir(parents=True)
    board_path.write_text("not valid json", encoding="utf-8")

    import hermes.app as app_module

    def _forbidden_collection(*args, **kwargs):
        raise AssertionError("Home must not collect infrastructure data")

    for name in (
        "_collect_dashboard_data",
        "_collect_do_security",
        "_collect_proxy_ssh",
        "_collect_sub2api_stats",
    ):
        if hasattr(app_module, name):
            monkeypatch.setattr(app_module, name, _forbidden_collection)

    _, client, app = _client(tmp_path)
    render_home = next(route.endpoint for route in app.routes if route.path == "/")
    closure_names = render_home.__code__.co_freevars
    closure_values = [cell.cell_contents for cell in render_home.__closure__ or ()]
    workbench_renderer = closure_values[closure_names.index("_render_workbench_page")]

    assert "_collect_dashboard_data" not in workbench_renderer.__code__.co_freevars

    response = client.get("/")

    assert response.status_code == 200
    assert 'class="engram-home"' in response.text


def test_home_api_excludes_retired_infrastructure_inputs() -> None:
    parameters = inspect.signature(home_page).parameters
    assert not {
        "do_status",
        "proxy_status",
        "proxy_traffic",
        "sub2api",
        "linuxdo_board",
    } & parameters.keys()


def test_home_prioritizes_modules_and_exposes_keyboard_navigation() -> None:
    rendered = home_page(
        node_counts={"draft": 1, "refined": 1, "verified": 1, "canonized": 1, "deprecated": 0},
        chart_count=2,
        health_summary={},
        recent_nodes=[],
        proposal_counts={"pending": 1},
        pending_proposals=[{"proposal_id": "p-1", "summary": "Review me"}],
    )

    assert 'class="skip-link" href="#main-content"' in rendered
    assert '<main class="engram-main" id="main-content"' in rendered
    assert 'href="/" aria-current="page"' in rendered
    assert rendered.index('id="engram-knowledge"') < rendered.index('id="decision-title"')
    assert rendered.index('id="engram-gallery"') < rendered.index('id="decision-title"')
    assert "a:focus-visible" in rendered
    assert "@media(max-width:760px)" in rendered
    mobile_css = rendered.split("@media(max-width:760px)", 1)[1].split("</style>", 1)[0]
    assert ".engram-nav a{min-height:44px" in mobile_css
    assert ".engram-nav .utility{display:none}" not in mobile_css
    assert ".module-card:focus-visible{outline:3px solid var(--oxide)" in rendered
    assert "@media(max-width:380px)" in rendered
    narrow_css = rendered.split("@media(max-width:380px)", 1)[1].split("</style>", 1)[0]
    assert ".engram-topbar{flex-wrap:wrap" in narrow_css
    assert ".engram-nav{width:100%" in narrow_css
    assert ".engram-nav a{flex:1" in narrow_css
    assert ".ledger-row,.recent-row{min-width:0" in narrow_css
    assert "overflow-wrap:anywhere" in narrow_css


def test_home_renders_empty_unicode_long_and_malicious_inputs_safely() -> None:
    empty = home_page(node_counts={}, chart_count=0, health_summary={})
    assert "No decisions waiting" in empty
    assert "No knowledge entries yet" in empty
    assert "<strong>0</strong> records" in empty
    # Home now includes one fixed theme controller; user data must never alter it.
    assert empty.count("<script>") == 1
    theme_script = empty.split("<script>", 1)[1].split("</script>", 1)[0]
    assert "localStorage.getItem('hermes_theme')" in theme_script
    assert "document.getElementById('home-theme-toggle')" in theme_script

    malicious = '</style><script>alert(1)</script><img src=x onerror=alert(2)>'
    rendered = home_page(
        node_counts={"verified": 1},
        chart_count=1,
        health_summary={},
        recent_nodes=[{
            "id": '../../节点/α\" onclick=\"alert(3)',
            "summary": "人脑 APA 🧠 " + malicious + "A" * 300,
            "stage": 'verified\" onmouseover=\"alert(4)',
            "category": '<svg onload=alert(5)>',
            "created_at": "2026-09-29",
        }],
        proposal_counts={"pending": 1},
        pending_proposals=[{
            "proposal_id": '../提案/β\" onclick=\"alert(6)',
            "summary": "复核证据 " + malicious + "B" * 300,
            "risk_level": '\" autofocus onfocus=alert(7) x=\"',
        }],
    )

    assert "人脑 APA 🧠" in rendered
    assert "复核证据" in rendered
    assert malicious not in rendered
    assert "<img src=x" not in rendered
    assert "<svg onload" not in rendered
    assert "/knowledge/..%2F..%2F%E8%8A%82%E7%82%B9%2F%CE%B1%22%20onclick%3D%22alert%283%29" in rendered
    assert "/review/..%2F%E6%8F%90%E6%A1%88%2F%CE%B2%22%20onclick%3D%22alert%286%29" in rendered
    assert "A" * 141 not in rendered
    assert "B" * 181 not in rendered
    assert rendered.count("<script>") == 1
    assert rendered.split("<script>", 1)[1].split("</script>", 1)[0] == theme_script
    assert all(marker not in rendered for marker in ("javascript:", "fetch(", "innerHTML"))

    class _EventAttributeParser(HTMLParser):
        event_attributes: list[tuple[str, str | None]]

        def __init__(self) -> None:
            super().__init__()
            self.event_attributes = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            self.event_attributes.extend((name, value) for name, value in attrs if name.lower().startswith("on"))

    parser = _EventAttributeParser()
    parser.feed(rendered)
    assert parser.event_attributes == []


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
    assert 'class="engram-home"' in home.text
    assert 'id="engram-knowledge"' in home.text
    assert 'id="engram-gallery"' in home.text
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
        headers={"Origin": "http://testserver"},
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


def test_opening_mount_preserves_both_v30_runs_and_has_a_non_blocking_exit(tmp_path: Path) -> None:
    _, client, app = _client(tmp_path)

    page = client.get("/opening/")
    script = client.get("/opening/app.js")
    styles = client.get("/opening/styles.css")

    assert page.status_code == 200
    assert script.status_code == 200
    assert styles.status_code == 200
    assert 'data-scene="sunset"' in page.text
    assert 'data-scene="blade"' in page.text
    assert 'href="/" class="opening-exit"' in page.text
    assert "fonts.googleapis.com" not in page.text
    assert 'selectedScene === "blade" ? "spinner" : "cruiser"' in script.text
    assert "if (!reduced) startBootPreview(selectedScene);" in script.text
    assert "opening-load-error" in page.text
    assert "/opening" in {route.path for route in app.routes}
    assert "default-src 'self'" in page.headers["content-security-policy"]
    assert "frame-ancestors 'self'" in page.headers["content-security-policy"]


def test_opening_accessibility_contract_covers_motion_dialog_status_and_touch_controls(tmp_path: Path) -> None:
    _, client, _ = _client(tmp_path)

    page = client.get("/opening/")
    script = client.get("/opening/app.js")

    assert 'role="status"' in page.text
    assert 'aria-live="polite"' in page.text
    assert 'role="radiogroup"' in page.text
    assert page.text.count('role="radio"') == 2
    assert page.text.count('aria-label=') >= 5
    assert 'role="dialog"' in page.text
    assert 'aria-modal="true"' in page.text
    assert 'aria-labelledby="pauseTitle"' in page.text
    assert 'id="pauseTitle"' in page.text
    assert 'pauseOverlay?.setAttribute("aria-hidden", paused ? "false" : "true")' in script.text
    assert 'resumeBtn?.focus()' in script.text
    assert "function trapPauseFocus" in script.text
    assert 'pauseOverlay?.addEventListener("keydown", trapPauseFocus)' in script.text
    assert 'motionEnabled = true' in script.text
    assert 'ENABLE MOTION & START' in script.text
    assert 'id="openingError"' in page.text
    assert 'role="alert"' in page.text
    assert 'openingError.hidden = false' in script.text


def test_opening_csp_allows_only_the_runtime_style_attributes_it_uses(tmp_path: Path) -> None:
    _, client, _ = _client(tmp_path)

    response = client.get("/opening/")
    csp = response.headers["content-security-policy"]

    assert "style-src 'self'" in csp
    assert "style-src-attr 'unsafe-inline'" in csp
    assert "script-src 'self'" in csp
    assert "'wasm-unsafe-eval'" in csp
    assert "worker-src 'self' blob:" in csp
    assert "connect-src 'self' blob:" in csp
    assert "img-src 'self' data: blob:" in csp


def test_opening_requires_auth_when_brain_auth_is_enabled(tmp_path: Path) -> None:
    _, client, _ = _client(tmp_path, auth=True)

    response = client.get("/opening/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    assert client.get("/opening/app.js", follow_redirects=False).status_code in (303, 401)
