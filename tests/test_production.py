"""Tests for the four production-level additions: auth, notifier, templates, eviction."""

from __future__ import annotations

from pathlib import Path

import pytest
import hermes.templates as legacy_templates
from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.auth import CSRFMiddleware, DBFailClosedMiddleware, TLSConfig, TokenAuthMiddleware
from hermes.config import HermesConfig
from hermes.eviction import EvictionService
from hermes.exporter import ExportCompiler
from hermes.ingest import IngestionService
from hermes.notifier import NotificationRouter, TelegramNotifier
from hermes.proposals import ProposalWriter
from hermes.repository import HermesRepository
from hermes.templates import _page


# -- helpers -----------------------------------------------------------------

def _write_proposal(
    writer: ProposalWriter,
    *,
    source_agent: str = "test",
    source_host: str = "testhost",
    project_key: str = "brain",
    category: str = "rule",
    risk_level: str = "high",
    suggested_memory: str = "Test memory rule.",
    scope: str = "project",
) -> Path:
    return writer.write(
        source_agent=source_agent,
        source_host=source_host,
        project_key=project_key,
        category=category,
        risk_level=risk_level,
        summary=suggested_memory,
        observation="Observed behavior.",
        why_it_matters="Because it matters.",
        suggested_memory=suggested_memory,
        scope=scope,
        evidence='[{"source_type":"test","source_uri":"tests/test_production.py","quoted_excerpt":"Test proposal evidence for production route coverage."}]',
    )


def _make_stack(tmp_path: Path, *, auth_token: str | None = None):
    sync_root = tmp_path / "sync"
    config = HermesConfig(
        sync_root=sync_root,
        db_path=tmp_path / "hermes.sqlite3",
        auth_token=auth_token,
    )
    config.ensure_directories()
    repo = HermesRepository(config.db_path)
    writer = ProposalWriter(config.proposals_dir)
    ingest = IngestionService(repo=repo, sync_root=sync_root)
    compiler = ExportCompiler(repo=repo, sync_root=sync_root)
    app = create_app(repo=repo, sync_root=sync_root, config=config, exporter=compiler)
    client = TestClient(app)
    return config, repo, writer, ingest, compiler, client


# -- auth tests ---------------------------------------------------------------

class TestTokenAuth:
    def test_sensitive_public_route_near_misses_are_not_public(self, tmp_path: Path) -> None:
        *_, client = _make_stack(tmp_path, auth_token="secret123")
        for path in (
            "/api/dashboard/health",
            "/api/v1/brain/health",
            "/api/dashboard/data",
            "/api/dashboard/resources",
            "/api/v1/brain/retrieve",
            "/api/knowledge/record-query",
            "/exports/projects/report.txt",
            "/api/dashboard/data/anything",
        ):
            assert client.get(path).status_code == 401

    @pytest.mark.parametrize("path", ["/api/v1/brain/retrieve", "/api/knowledge/record-query"])
    def test_cookie_authenticated_retrieval_writes_reject_cross_site_posts(
        self, tmp_path: Path, path: str
    ) -> None:
        *_, client = _make_stack(tmp_path, auth_token="secret123")
        login = client.post(
            "/login",
            data={"username": "owner", "password": "secret123"},
            headers={"Origin": "http://testserver"},
        )
        assert login.status_code == 200

        response = client.post(
            path,
            json={"query": "provider config logs", "agent": "browser", "host": "test"},
            headers={"Origin": "https://evil.test"},
        )
        assert response.status_code == 403

    def test_get_logout_does_not_clear_session_and_post_logout_does(self, tmp_path: Path) -> None:
        *_, client = _make_stack(tmp_path, auth_token="secret123")
        login = client.post("/login", data={"username": "owner", "password": "secret123"}, headers={"Origin": "http://testserver"}, follow_redirects=False)
        assert login.status_code == 303
        cookie = client.cookies.get("hermes_auth")
        get_response = client.get("/logout", follow_redirects=False)
        assert get_response.status_code == 405
        assert client.cookies.get("hermes_auth") == cookie
        post_response = client.post("/logout", headers={"Origin": "http://testserver"}, follow_redirects=False)
        assert post_response.status_code == 303
        assert "hermes_auth" in post_response.headers.get("set-cookie", "")

    def test_cookie_auth_without_csrf_secret_remains_same_origin_only(self, tmp_path: Path) -> None:
        config, *_rest, client = _make_stack(tmp_path, auth_token="secret123")
        assert config.csrf_secret is None
        assert client.post("/login", data={"username": "owner", "password": "secret123"}, headers={"Origin": "http://evil.test"}).status_code == 403

    def test_record_query_rejects_invalid_limit_as_bad_request(self, tmp_path: Path) -> None:
        *_, client = _make_stack(tmp_path, auth_token="secret123")
        response = client.post(
            "/api/knowledge/record-query",
            headers={"Authorization": "Bearer secret123"},
            json={"query": "provider logs", "limit": "not-an-integer"},
        )
        assert response.status_code == 400

    def test_legacy_templates_do_not_advertise_missing_render_api(self) -> None:
        source = Path(legacy_templates.__file__).read_text(encoding="utf-8")
        assert "/api/render" not in source
        assert "fetch(RENDER_API" not in source
    def test_no_auth_token_allows_all(self, tmp_path: Path) -> None:
        _, repo, writer, ingest, _, client = _make_stack(tmp_path)
        proposal_path = _write_proposal(writer, category="preference", risk_level="low")
        ingest.ingest_path(proposal_path)

        # All routes accessible without auth
        assert client.get("/health").status_code == 200
        assert client.get("/api/review/pending").status_code == 200
        assert client.get("/review").status_code == 200

    def test_auth_token_blocks_unauthenticated(self, tmp_path: Path) -> None:
        _, repo, writer, ingest, _, client = _make_stack(tmp_path, auth_token="secret123")
        proposal_path = _write_proposal(writer)
        ingest.ingest_path(proposal_path)

        # Public routes still accessible
        assert client.get("/health").status_code == 200

        # Protected API routes require auth and keep JSON 401.
        assert client.get("/api/review/pending").status_code == 401

        # Protected page routes redirect unauthenticated browsers/tools to login.
        page_resp = client.get("/review", follow_redirects=False)
        assert page_resp.status_code == 303
        assert page_resp.headers["location"] == "/login"

    def test_auth_token_allows_with_bearer(self, tmp_path: Path) -> None:
        _, repo, writer, ingest, _, client = _make_stack(tmp_path, auth_token="secret123")
        proposal_path = _write_proposal(writer)
        ingest.ingest_path(proposal_path)

        headers = {"Authorization": "Bearer secret123"}
        assert client.get("/api/review/pending", headers=headers).status_code == 200
        assert client.get("/review", headers=headers).status_code == 200

    def test_html_responses_are_not_cached(self, tmp_path: Path) -> None:
        _, _, _, _, _, client = _make_stack(tmp_path, auth_token="secret123")

        resp = client.get("/login")
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
        assert resp.headers["pragma"] == "no-cache"
        assert resp.headers["expires"] == "0"

    def test_wrong_token_rejected(self, tmp_path: Path) -> None:
        _, repo, writer, ingest, _, client = _make_stack(tmp_path, auth_token="secret123")
        headers = {"Authorization": "Bearer wrong"}
        assert client.get("/api/review/pending", headers=headers).status_code == 401

    def test_login_requires_same_origin_and_sets_secure_cookie_on_https(
        self, tmp_path: Path
    ) -> None:
        *_, default_client = _make_stack(tmp_path, auth_token="secret123")

        assert default_client.post(
            "/login", data={"username": "owner", "password": "secret123"}
        ).status_code == 403

        secure_client = TestClient(default_client.app, base_url="https://testserver")
        response = secure_client.post(
            "/login",
            data={"username": "owner", "password": "secret123"},
            headers={"Origin": "https://testserver"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "secure" in cookie
        assert "samesite=lax" in cookie
        assert "path=/" in cookie

    @pytest.mark.parametrize(
        "headers",
        (
            {"Origin": "https://testserver"},
            {"Origin": "http://testserver:81"},
            {"Origin": "http://testserver:bad"},
            {"Origin": "null"},
            {"Origin": "http://evil.test", "Referer": "http://testserver/settings"},
        ),
    )
    def test_cookie_write_rejects_non_matching_origin(
        self, tmp_path: Path, headers: dict[str, str]
    ) -> None:
        *_, client = _make_stack(tmp_path, auth_token="secret123")
        login = client.post(
            "/login",
            data={"username": "owner", "password": "secret123"},
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        assert login.status_code == 303

        response = client.post(
            "/api/settings/profile",
            data={"display_name": "owner", "avatar_url": "", "theme": "light", "lang": "zh"},
            headers=headers,
        )
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "headers",
        (
            {"Origin": "http://testserver"},
            {"Origin": "http://testserver:80"},
            {"Referer": "http://testserver/settings?tab=profile"},
        ),
    )
    def test_cookie_write_accepts_exact_same_origin(
        self, tmp_path: Path, headers: dict[str, str]
    ) -> None:
        *_, client = _make_stack(tmp_path, auth_token="secret123")
        login = client.post(
            "/login",
            data={"username": "owner", "password": "secret123"},
            headers={"Origin": "http://testserver"},
            follow_redirects=False,
        )
        assert login.status_code == 303

        response = client.post(
            "/api/settings/profile",
            data={"display_name": "owner", "avatar_url": "", "theme": "light", "lang": "zh"},
            headers=headers,
        )
        assert response.status_code == 200

    def test_exports_require_auth(self, tmp_path: Path) -> None:
        _, repo, writer, ingest, compiler, client = _make_stack(tmp_path, auth_token="secret123")
        proposal_path = _write_proposal(writer, suggested_memory="Export me.")
        ingest.ingest_path(proposal_path)
        pid = repo.list_proposals_by_state("pending")[0]["proposal_id"]
        repo.transition_state(pid, "approved_for_export")
        compiler.build_project_export("brain")

        assert client.get("/exports/projects/brain.md").status_code == 401
        resp = client.get(
            "/exports/projects/brain.md",
            headers={"Authorization": "Bearer secret123"},
        )
        assert resp.status_code == 200
        assert "Export me." in resp.text


class TestTLSConfig:
    def test_enabled_when_both_files_exist(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.pem"
        key = tmp_path / "key.pem"
        cert.write_text("cert", encoding="utf-8")
        key.write_text("key", encoding="utf-8")
        tls = TLSConfig(cert_path=str(cert), key_path=str(key))
        assert tls.enabled is True

    def test_disabled_when_missing(self) -> None:
        tls = TLSConfig(cert_path="/nonexistent", key_path="/nonexistent")
        assert tls.enabled is False

    def test_disabled_when_none(self) -> None:
        assert TLSConfig().enabled is False


# -- notifier tests -----------------------------------------------------------

class TestTelegramNotifier:
    def test_enabled_when_configured(self) -> None:
        notifier = TelegramNotifier("123:abc", "999")
        assert notifier.enabled is True

    def test_disabled_when_missing(self) -> None:
        assert TelegramNotifier("", "999").enabled is False
        assert TelegramNotifier("123", "").enabled is False

    def test_send_returns_false_when_disabled(self) -> None:
        import asyncio
        notifier = TelegramNotifier("", "999")
        result = asyncio.run(notifier.send("test"))
        assert result is False


class TestNotificationRouter:
    def test_dispatch_is_noop_without_notifier(self) -> None:
        router = NotificationRouter(None)
        # Should not raise
        router.dispatch("pending_new", {"proposal_id": "x"})

    def test_dispatch_is_noop_with_disabled_notifier(self) -> None:
        router = NotificationRouter(TelegramNotifier("", ""))
        # Should not raise
        router.dispatch("pending_new", {"proposal_id": "x"})


# -- templates / HTML tests ---------------------------------------------------

class TestMobileReviewUI:
    def test_queue_page_has_viewport_and_dark_theme(self, tmp_path: Path) -> None:
        _, _, writer, ingest, _, client = _make_stack(tmp_path)
        proposal_path = _write_proposal(writer)
        ingest.ingest_path(proposal_path)

        resp = client.get("/review")
        assert resp.status_code == 200
        html = resp.text
        assert "viewport" in html
        assert "dark" in html.lower() or "#282a36" in html  # dracula bg

    def test_queue_page_has_filter_tabs(self, tmp_path: Path) -> None:
        _, _, writer, ingest, _, client = _make_stack(tmp_path)
        proposal_path = _write_proposal(writer)
        ingest.ingest_path(proposal_path)

        resp = client.get("/review")
        html = resp.text
        assert "Pending" in html
        assert "Approved" in html or "approved" in html.lower()

    def test_detail_page_has_action_buttons(self, tmp_path: Path) -> None:
        _, repo, writer, ingest, _, client = _make_stack(tmp_path)
        proposal_path = _write_proposal(writer)
        pid = ingest.ingest_path(proposal_path).proposal_id

        resp = client.get(f"/review/{pid}")
        html = resp.text
        assert "approve-db-only" in html or "Approve" in html
        assert "approve-for-export" in html or "Export" in html
        assert "reject" in html.lower()

    def test_approved_page(self, tmp_path: Path) -> None:
        _, repo, writer, ingest, _, client = _make_stack(tmp_path)
        proposal_path = _write_proposal(writer, category="preference", risk_level="low")
        ingest.ingest_path(proposal_path)

        resp = client.get("/review/approved")
        assert resp.status_code == 200

    def test_rejected_page(self, tmp_path: Path) -> None:
        _, repo, writer, ingest, _, client = _make_stack(tmp_path)
        resp = client.get("/review/rejected")
        assert resp.status_code == 200

    def test_dashboard_page(self, tmp_path: Path) -> None:
        _, _, writer, ingest, _, client = _make_stack(tmp_path)
        proposal_path = _write_proposal(writer)
        ingest.ingest_path(proposal_path)

        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "pending" in resp.text.lower()

    def test_queue_with_state_filter(self, tmp_path: Path) -> None:
        _, _, writer, ingest, _, client = _make_stack(tmp_path)
        proposal_path = _write_proposal(writer)
        ingest.ingest_path(proposal_path)

        resp = client.get("/review?state=all")
        assert resp.status_code == 200


class TestAvatarSecurity:
    def test_profile_rejects_unsafe_avatar_schemes(self, tmp_path: Path) -> None:
        _, _, _, _, _, client = _make_stack(tmp_path)
        for value in (
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "http://example.test/avatar.png",
            "//example.test/avatar.png",
            "/\\evil.example/avatar.png",
            "/safe\nunsafe.png",
        ):
            response = client.post(
                "/api/settings/profile",
                data={"display_name": "test", "avatar_url": value, "theme": "light", "lang": "zh"},
            )
            assert response.status_code == 422

    def test_profile_accepts_https_and_local_avatar_paths(self, tmp_path: Path) -> None:
        _, _, _, _, _, client = _make_stack(tmp_path)
        for value in ("https://example.test/avatar.png", "/static/avatar.png"):
            response = client.post(
                "/api/settings/profile",
                data={"display_name": "test", "avatar_url": value, "theme": "light", "lang": "zh"},
            )
            assert response.status_code == 200
            assert response.json()["profile"]["avatar_url"] == value

    def test_page_uses_dom_api_for_stored_avatar(self) -> None:
        html = _page("test", "<main>test</main>")
        assert "renderStoredAvatar" in html
        assert "sa.replaceChildren(img)" in html
        assert "sa.innerHTML='<img src" not in html
        assert "onerror=" not in html


# -- eviction tests -----------------------------------------------------------

class TestGalleryScriptUploadSecurity:
    @staticmethod
    def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
        plotting_dir = tmp_path / "plotting"
        monkeypatch.setenv("BRAIN_PLOTTING_DIR", str(plotting_dir))
        *_, client = _make_stack(tmp_path)
        return client, plotting_dir

    @pytest.mark.parametrize(
        "filename",
        ("../../outside.py", "/tmp/outside.py", "..\\..\\outside.py", "nested/script.py"),
    )
    def test_rejects_filename_with_directories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str
    ) -> None:
        client, plotting_dir = self._client(tmp_path, monkeypatch)
        response = client.post(
            "/api/gallery/upload_script",
            data={"chart_name": "test", "description": "test"},
            files={"file": (filename, b"print('safe')", "text/x-python")},
        )
        assert response.status_code == 422
        assert not (tmp_path / "outside.py").exists()
        assert list((plotting_dir / "templates").glob("*")) == []

    def test_uses_generated_name_inside_template_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, plotting_dir = self._client(tmp_path, monkeypatch)
        response = client.post(
            "/api/gallery/upload_script",
            data={"chart_name": "test", "description": "test"},
            files={"file": ("safe.py", b"print('safe')", "text/x-python")},
        )
        assert response.status_code == 200
        stored_name = response.json()["filename"]
        assert stored_name != "safe.py"
        assert stored_name.endswith(".py")
        stored = (plotting_dir / "templates" / stored_name).resolve()
        assert stored.parent == (plotting_dir / "templates").resolve()
        assert stored.read_bytes() == b"print('safe')"

    def test_rejects_oversized_upload_without_partial_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, plotting_dir = self._client(tmp_path, monkeypatch)
        response = client.post(
            "/api/gallery/upload_script",
            data={"chart_name": "test", "description": "test"},
            files={"file": ("large.py", b"x" * (2 * 1024 * 1024 + 1), "text/x-python")},
        )
        assert response.status_code == 413
        assert list((plotting_dir / "templates").glob("*")) == []

    def test_rejects_zip_upload(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        client, plotting_dir = self._client(tmp_path, monkeypatch)
        response = client.post(
            "/api/gallery/upload_script",
            data={"chart_name": "test", "description": "test"},
            files={"file": ("archive.zip", b"PK\x03\x04unsafe", "application/zip")},
        )
        assert response.status_code == 422
        assert list((plotting_dir / "templates").glob("*")) == []


class TestGallerySubmissionSurface:
    def test_poster_submission_routes_are_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plotting_dir = tmp_path / "plotting"
        monkeypatch.setenv("BRAIN_PLOTTING_DIR", str(plotting_dir))
        *_, client = _make_stack(tmp_path)

        route_paths = [getattr(route, "path", None) for route in getattr(client.app, "routes", ())]
        assert "/api/gallery/submit_figure" not in route_paths
        assert "/gallery/submitted" not in route_paths
        assert not (plotting_dir / "submitted_figures").exists()

    def test_interactive_gallery_iframe_has_no_same_origin_capability(self) -> None:
        from hermes.templates import gallery_page

        html = gallery_page()
        assert 'id="iframe-chart"' in html
        assert 'sandbox="allow-scripts"' in html
        assert "allow-same-origin" not in html

    def test_gallery_static_serves_only_catalog_allowlisted_assets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plotting_dir = tmp_path / "plotting"
        templates_dir = plotting_dir / "templates"
        submitted_dir = plotting_dir / "submitted_figures"
        templates_dir.mkdir(parents=True)
        submitted_dir.mkdir()
        (plotting_dir / "catalog.yaml").write_text(
            "charts:\n"
            "  - name: safe_chart\n"
            "    title: Safe\n"
            "    demo: demos/safe.png\n"
            "    template: templates/safe_chart.py\n",
            encoding="utf-8",
        )
        (plotting_dir / "demos").mkdir()
        (plotting_dir / "demos" / "safe.png").write_bytes(b"safe-image")
        (plotting_dir / "interactive").mkdir()
        (plotting_dir / "interactive" / "safe.html").write_text(
            "<script>window.parent.document.body.dataset.pwned='yes'</script>",
            encoding="utf-8",
        )
        (templates_dir / "safe_chart.py").write_text("print('safe')", encoding="utf-8")
        (templates_dir / "unlisted.py").write_text("print('private')", encoding="utf-8")
        (plotting_dir / "secret.txt").write_text("secret", encoding="utf-8")
        (submitted_dir / "old-poster.png").write_bytes(b"private")
        monkeypatch.setenv("BRAIN_PLOTTING_DIR", str(plotting_dir))
        *_, client = _make_stack(tmp_path)

        assert client.get("/gallery/static/demos/safe.png").content == b"safe-image"
        assert client.get("/gallery/static/templates/safe_chart.py").status_code == 200
        assert client.get("/gallery/static/templates/unlisted.py").status_code == 404
        assert client.get("/api/gallery/template/unlisted.py").json()["ok"] is False
        assert client.get("/gallery/static/secret.txt").status_code == 404
        assert client.get("/gallery/static/submitted_figures/old-poster.png").status_code == 404
        assert client.get("/gallery/static/%2e%2e/secret.txt").status_code == 404

    def test_gallery_interactive_html_can_be_framed_only_by_same_origin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plotting_dir = tmp_path / "plotting"
        interactive_dir = plotting_dir / "interactive"
        interactive_dir.mkdir(parents=True)
        (plotting_dir / "catalog.yaml").write_text(
            "charts:\n"
            "  - name: safe_chart\n"
            "    interactive: interactive/safe.html\n",
            encoding="utf-8",
        )
        (interactive_dir / "safe.html").write_text("<p>interactive</p>", encoding="utf-8")
        monkeypatch.setenv("BRAIN_PLOTTING_DIR", str(plotting_dir))
        *_, client = _make_stack(tmp_path)

        response = client.get("/gallery/static/interactive/safe.html")
        assert response.status_code == 200
        assert "frame-ancestors 'self'" in response.headers["content-security-policy"]
        assert "frame-ancestors 'none'" not in response.headers["content-security-policy"]

    def test_gallery_catalog_paths_cannot_escape_or_follow_outside_symlinks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plotting_dir = tmp_path / "plotting"
        templates_dir = plotting_dir / "templates"
        demos_dir = plotting_dir / "demos"
        templates_dir.mkdir(parents=True)
        demos_dir.mkdir()
        outside = tmp_path / "outside.py"
        outside.write_text("secret", encoding="utf-8")
        (templates_dir / "linked.py").symlink_to(outside)
        (plotting_dir / "catalog.yaml").write_text(
            "charts:\n"
            "  - name: linked\n"
            "    template: templates/linked.py\n"
            "    demo: ../outside.py\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("BRAIN_PLOTTING_DIR", str(plotting_dir))
        *_, client = _make_stack(tmp_path)

        assert client.get("/gallery/static/templates/linked.py").status_code == 404
        detail = client.get("/api/gallery/catalog/linked").json()["chart"]
        assert detail["has_template"] is False
        assert detail["has_demo"] is False
        assert detail["sources"] == {}
        assert detail["demo"] is None

    def test_generic_gallery_uploader_is_retired(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plotting_dir = tmp_path / "plotting"
        monkeypatch.setenv("BRAIN_PLOTTING_DIR", str(plotting_dir))
        *_, client = _make_stack(tmp_path)
        response = client.post("/api/gallery/submit", data={"chart_name": "test"})
        assert response.status_code == 410
        assert not plotting_dir.exists()


class TestEvictionService:
    def test_detect_stale_exports_empty(self, tmp_path: Path) -> None:
        sync_root = tmp_path / "sync"
        repo = HermesRepository(tmp_path / "hermes.sqlite3")
        eviction = EvictionService(
            repo=repo,
            sync_root=sync_root,
            stale_tolerance_hours=72,
            stale_hard_limit_days=14,
        )
        stale = eviction.detect_stale_exports()
        assert stale == []

    def test_evict_stale_exports_empty(self, tmp_path: Path) -> None:
        sync_root = tmp_path / "sync"
        repo = HermesRepository(tmp_path / "hermes.sqlite3")
        eviction = EvictionService(
            repo=repo,
            sync_root=sync_root,
            stale_tolerance_hours=72,
            stale_hard_limit_days=14,
        )
        result = eviction.evict_stale_exports()
        assert result.evicted_count == 0

    def test_check_budget_pressure_under_cap(self, tmp_path: Path) -> None:
        sync_root = tmp_path / "sync"
        repo = HermesRepository(tmp_path / "hermes.sqlite3")
        compiler = ExportCompiler(repo=repo, sync_root=sync_root)
        eviction = EvictionService(
            repo=repo,
            sync_root=sync_root,
            stale_tolerance_hours=72,
            stale_hard_limit_days=14,
        )
        pressures = eviction.check_budget_pressure(compiler.budgets)
        # No exports yet, so all pressures should show 0 current_bytes
        for p in pressures:
            assert not p.over_hard

    def test_repository_delete_export(self, tmp_path: Path) -> None:
        repo = HermesRepository(tmp_path / "hermes.sqlite3")
        repo.record_export(
            scope_type="project",
            project_key="brain",
            file_name="brain.md",
            size_bytes=100,
        )
        assert len(repo.list_export_records()) == 1
        repo.delete_export("project", "brain", "brain.md")
        assert len(repo.list_export_records()) == 0

    def test_repository_demotion_candidates(self, tmp_path: Path) -> None:
        repo = HermesRepository(tmp_path / "hermes.sqlite3")
        writer = ProposalWriter(tmp_path / "sync" / "inbox" / "proposals")
        ingest = IngestionService(repo=repo, sync_root=tmp_path / "sync")

        p1 = _write_proposal(writer, suggested_memory="First rule")
        p2 = _write_proposal(writer, suggested_memory="Second rule")
        id1 = ingest.ingest_path(p1).proposal_id
        id2 = ingest.ingest_path(p2).proposal_id
        repo.transition_state(id1, "approved_for_export")
        repo.transition_state(id2, "approved_for_export")

        candidates = repo.list_proposals_ordered_for_demotion("brain")
        assert len(candidates) == 2
        assert candidates[0]["proposal_id"] == id1  # oldest first


# -- integration: runtime eviction cycle --------------------------------------

class TestRuntimeEvictionCycle:
    def test_eviction_cycle_on_empty_db(self, tmp_path: Path) -> None:
        from hermes.runtime import HermesRuntime
        config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
        config.ensure_directories()
        runtime = HermesRuntime(config=config)
        result = runtime.run_eviction_cycle()
        assert result.evicted_count == 0
