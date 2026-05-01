"""Tests for the four production-level additions: auth, notifier, templates, eviction."""

from __future__ import annotations

from pathlib import Path

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
        evidence="Test evidence.",
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

        # Protected routes require auth
        assert client.get("/api/review/pending").status_code == 401
        assert client.get("/review").status_code == 401

    def test_auth_token_allows_with_bearer(self, tmp_path: Path) -> None:
        _, repo, writer, ingest, _, client = _make_stack(tmp_path, auth_token="secret123")
        proposal_path = _write_proposal(writer)
        ingest.ingest_path(proposal_path)

        headers = {"Authorization": "Bearer secret123"}
        assert client.get("/api/review/pending", headers=headers).status_code == 200
        assert client.get("/review", headers=headers).status_code == 200

    def test_wrong_token_rejected(self, tmp_path: Path) -> None:
        _, repo, writer, ingest, _, client = _make_stack(tmp_path, auth_token="secret123")
        headers = {"Authorization": "Bearer wrong"}
        assert client.get("/api/review/pending", headers=headers).status_code == 401

    def test_exports_public_even_with_auth(self, tmp_path: Path) -> None:
        _, repo, writer, ingest, compiler, client = _make_stack(tmp_path, auth_token="secret123")
        proposal_path = _write_proposal(writer, suggested_memory="Export me.")
        ingest.ingest_path(proposal_path)
        pid = repo.list_proposals_by_state("pending")[0]["proposal_id"]
        repo.transition_state(pid, "approved_for_export")
        compiler.build_project_export("brain")

        # Export files are public (no auth needed)
        resp = client.get("/exports/projects/brain.md")
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

    def test_queue_with_state_filter(self, tmp_path: Path) -> None:
        _, _, writer, ingest, _, client = _make_stack(tmp_path)
        proposal_path = _write_proposal(writer)
        ingest.ingest_path(proposal_path)

        resp = client.get("/review?state=all")
        assert resp.status_code == 200


# -- eviction tests -----------------------------------------------------------

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
