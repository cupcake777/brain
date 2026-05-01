from pathlib import Path

from hermes.config import HermesConfig
from hermes.proposals import ProposalWriter
from hermes.repository import HermesRepository
from hermes.runtime import HermesRuntime


def _write(writer: ProposalWriter, *, category: str, risk_level: str, project_key: str, scope: str = "project") -> Path:
    return writer.write(
        source_agent="codex",
        source_host="macbook",
        project_key=project_key,
        category=category,
        risk_level=risk_level,
        summary="Runtime should ingest inbox files.",
        observation="Watcher scans the shared inbox.",
        why_it_matters="The service must process synced proposals automatically.",
        suggested_memory="Run a polling watcher that ingests new proposals and refreshes status.",
        scope=scope,
        evidence="Runtime integration test.",
    )


def test_runtime_scan_ingests_new_files_and_publishes_status(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)
    runtime = HermesRuntime(config=config, repo=repo)
    writer = ProposalWriter(config.proposals_dir)

    proposal_path = _write(writer, category="rule", risk_level="high", project_key="brain")

    result = runtime.run_scan_cycle()
    status_path = config.state_dir / "status.md"

    assert result.ingested_count == 1
    assert proposal_path.name in result.processed_files
    assert repo.get_proposal(proposal_path.stem)["state"] == "pending"
    assert status_path.exists()
    assert "Pending proposals: 1" in status_path.read_text(encoding="utf-8")


def test_runtime_ignores_temp_and_syncthing_conflict_files(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)
    runtime = HermesRuntime(config=config, repo=repo)
    proposals_dir = config.proposals_dir
    proposals_dir.mkdir(parents=True, exist_ok=True)
    (proposals_dir / ".tmp-123.md").write_text("partial", encoding="utf-8")
    (proposals_dir / "abc.sync-conflict-20260417-1.md").write_text("conflict", encoding="utf-8")

    result = runtime.run_scan_cycle()

    assert result.ingested_count == 0
    assert result.skipped_files == [".tmp-123.md", "abc.sync-conflict-20260417-1.md"]


def test_runtime_rebuilds_global_and_project_exports_from_approved_records(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)
    runtime = HermesRuntime(config=config, repo=repo)
    writer = ProposalWriter(config.proposals_dir)

    project = _write(writer, category="rule", risk_level="high", project_key="brain")
    global_item = _write(writer, category="rule", risk_level="high", project_key="global", scope="global")

    runtime.run_scan_cycle()
    repo.transition_state(project.stem, "approved_for_export")
    repo.transition_state(global_item.stem, "approved_for_export")

    result = runtime.rebuild_exports()

    assert result.global_updated is True
    assert result.projects_updated == ["brain"]
    assert (config.global_exports_dir / "global.md").exists()
    assert (config.project_exports_dir / "brain.md").exists()


def test_runtime_watch_runs_multiple_cycles_with_injected_sleep(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "hermes.sqlite3", poll_interval_seconds=1)
    repo = HermesRepository(config.db_path)
    runtime = HermesRuntime(config=config, repo=repo)
    calls: list[int] = []

    runtime.watch(max_cycles=3, sleep_fn=lambda seconds: calls.append(seconds))

    assert calls == [1, 1]
