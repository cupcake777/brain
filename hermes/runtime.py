from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from time import sleep

from hermes.config import HermesConfig
from hermes.eviction import EvictionService, EvictionResult
from hermes.exporter import ExportCompiler
from hermes.ingest import IngestionService
from hermes.notifier import NotificationRouter, TelegramNotifier
from hermes.repository import HermesRepository
from hermes.status import StatusPublisher


@dataclass(frozen=True)
class ScanCycleResult:
    ingested_count: int
    processed_files: list[str]
    skipped_files: list[str]
    failed_files: list[str]


@dataclass(frozen=True)
class RebuildResult:
    global_updated: bool
    projects_updated: list[str]


class HermesRuntime:
    def __init__(self, *, config: HermesConfig, repo: HermesRepository | None = None) -> None:
        self.config = config
        self.config.ensure_directories()
        self.repo = repo or HermesRepository(config.db_path)

        # -- notification wiring ------------------------------------------------
        notifier: TelegramNotifier | None = None
        if config.telegram_bot_token and config.telegram_chat_id:
            notifier = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)
        self.notifier = NotificationRouter(notifier)

        self.ingestion = IngestionService(
            repo=self.repo,
            sync_root=self.config.sync_root,
            auto_approve_low_risk=self.config.auto_approve_low_risk,
            notification_router=self.notifier,
        )
        self.exporter = ExportCompiler(repo=self.repo, sync_root=self.config.sync_root)
        self.status = StatusPublisher(repo=self.repo, sync_root=self.config.sync_root)
        self.eviction = EvictionService(
            repo=self.repo,
            sync_root=self.config.sync_root,
            stale_tolerance_hours=self.config.stale_export_tolerance_hours,
            stale_hard_limit_days=self.config.stale_export_hard_limit_days,
        )

    def run_scan_cycle(self) -> ScanCycleResult:
        processed: list[str] = []
        skipped: list[str] = []
        failed: list[str] = []
        ingested_count = 0
        for candidate in sorted(self.config.proposals_dir.glob("*.md")):
            name = candidate.name
            if name.startswith(".tmp-") or ".sync-conflict-" in name:
                skipped.append(name)
                continue
            try:
                outcome = self.ingestion.ingest_path(candidate)
                processed.append(name)
                # Remove file from inbox after successful ingestion (already in DB)
                try:
                    candidate.unlink()
                except OSError:
                    pass
                if outcome.route == "pending":
                    ingested_count += 1  # count new pending proposals
                else:
                    ingested_count += 1  # count auto-approved as well
            except Exception as exc:  # noqa: BLE001
                failed.append(name)
                logging.warning("skipping invalid proposal %s: %s", name, exc)
                # Remove the file from inbox since ingest_path has already
                # moved it to review/rejected/ — leaving it causes repeated errors
                if candidate.exists():
                    try:
                        candidate.unlink()
                    except OSError:
                        pass
        for hidden in sorted(self.config.proposals_dir.glob(".*.md")):
            name = hidden.name
            if name.startswith(".tmp-"):
                skipped.append(name)
        skipped = sorted(set(skipped))
        self.status.publish()
        return ScanCycleResult(ingested_count=ingested_count, processed_files=processed, skipped_files=skipped, failed_files=failed)

    def rebuild_exports(self) -> RebuildResult:
        global_records = self.repo.list_exportable(None)
        global_updated = False
        if global_records:
            self.exporter.build_global_export()
            self.exporter.build_claude_md_export()
            global_updated = True

        project_keys = self.repo.list_exportable_project_keys()
        for project_key in project_keys:
            self.exporter.build_project_export(project_key)
        self.status.publish()
        return RebuildResult(global_updated=global_updated, projects_updated=project_keys)

    def run_eviction_cycle(self) -> EvictionResult:
        # 1. Detect stale exports
        stale = self.eviction.detect_stale_exports()

        # 2. Evict hard-stale ones, flag soft-stale for rebuild
        result = self.eviction.evict_stale_exports()

        # 3. Check budget pressure and demote if needed
        self.eviction.check_budget_pressure(self.exporter.budgets)

        # 4. Rebuild affected exports
        if result.evicted_count > 0 or result.flagged_for_rebuild_count > 0:
            self.rebuild_exports()

        # 5. Publish status
        self.status.publish()

        return result

    def watch(self, *, max_cycles: int | None = None, sleep_fn=sleep) -> None:
        cycle = 0
        while True:
            self.run_scan_cycle()
            self.rebuild_exports()
            cycle += 1
            if max_cycles is not None and cycle >= max_cycles:
                return
            sleep_fn(self.config.poll_interval_seconds)
