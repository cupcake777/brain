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


def sync_proposal_to_brain_context(
    proposal: dict,
    proposal_id: str,
    *,
    logger: logging.Logger | None = None,
) -> bool:
    """Sync a proposal's suggested_memory to ~/.hermes/brain-context.md.

    Module-level so both HermesRuntime and app.py API endpoints can share
    the same implementation without duplication.
    """
    try:
        suggested = str(proposal.get("suggested_memory", "")).strip()
        if not suggested:
            return False

        category = str(proposal.get("category", "fact"))
        summary = str(proposal.get("summary", ""))[:120]
        pid = proposal_id[:12]

        context_file = Path.home() / ".hermes" / "brain-context.md"
        context_file.parent.mkdir(parents=True, exist_ok=True)

        existing = ""
        if context_file.exists():
            existing = context_file.read_text(encoding="utf-8")

        if pid in existing or summary[:60] in existing:
            return False

        entry = f"\n### [{category}] {summary[:100]}\n{suggested}\n<!-- proposal:{pid} -->\n"

        # Keep only top 50 entries
        entries = existing.split("<!-- proposal:")
        if len(entries) > 50:
            header = entries[0] if not entries[0].startswith("<!--") else ""
            entries = entries[-49:]
            existing = header + "<!-- proposal:" + "<!-- proposal:".join(entries)

        context_file.write_text(existing + entry, encoding="utf-8")
        if logger is not None:
            logger.info("brain-context.md: wrote %s (%s)", pid, category)
        else:
            print(f"[brain.sync] wrote {pid} ({category}) to brain-context.md", flush=True)
        return True
    except Exception as exc:
        print(f"[brain.sync] FAILED: {exc}", flush=True)
        return False


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

    def _sync_to_brain_context(self, proposal_id: str) -> bool:
        """Sync a proposal's suggested_memory to ~/.hermes/brain-context.md."""
        try:
            proposal = self.repo.get_proposal(proposal_id)
        except KeyError:
            return False
        return sync_proposal_to_brain_context(
            proposal, proposal_id, logger=logging.getLogger(__name__),
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
                # Sync approved knowledge to agent context immediately
                self._sync_to_brain_context(outcome.proposal_id)
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

        # Always rebuild KNOWLEDGE.md from canonized knowledge nodes
        self.exporter.build_knowledge_export()

        # Export brain-context.md so HPC agents can pull it via HTTP
        self.exporter.export_brain_context()

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

    def run_retrospect_cycle(self) -> dict:
        """Run knowledge maintenance: dedup stale nodes, auto-promote stages, recompute confidence."""
        from hermes.integrate import retrospect
        result = retrospect(self.repo)
        logging.info("retrospect: %s", result)
        return result

    def run_knowledge_pipeline(self, *, backfill_embeddings: bool = True) -> dict:
        """Materialize approved proposals and persist any missing vectors."""
        from hermes.embedding import provider_config
        from hermes.pipeline import sync_approved_proposals

        result: dict[str, object] = {
            "proposals": sync_approved_proposals(self.repo),
            "embeddings": {"skipped": True, "reason": "provider disabled"},
        }
        if backfill_embeddings and provider_config()["enabled"]:
            result["embeddings"] = self.repo.backfill_embeddings(entity_type="all", batch_size=32)
        logging.info("knowledge pipeline: %s", result)
        return result

    def run_remote_dedup(self) -> dict:
        """Run embedding-based dedup on HF Space (16GB RAM) and apply results.

        Offloads fastembed computation to HuggingFace Space since VPS (2GB RAM) OOMs.
        Uploads current DB, runs dedup, downloads updated DB with deprecated nodes.
        """
        import os
        from hermes.remote_dedup import remote_dedup

        db_path = str(self.config.db_path)
        logging.info("remote_dedup: starting via HF Space ...")

        result = remote_dedup(
            db_path=db_path,
            merge_threshold=0.85,
            review_threshold=0.55,
            apply=True,
            timeout=300,
        )

        if result.error:
            logging.error("remote_dedup: failed: %s", result.error)
            return {"remote_dedup": "error", "error": result.error}

        logging.info("remote_dedup: deprecated %d nodes, log=%s",
                      result.deprecated_count, result.log[-200:] if result.log else "(empty)")

        # Rebuild exports after DB changes
        if result.deprecated_count > 0:
            self.rebuild_exports()

        return {
            "remote_dedup": "ok",
            "deprecated_count": result.deprecated_count,
        }

    def watch(self, *, max_cycles: int | None = None, sleep_fn=sleep) -> None:
        cycle = 0
        REMOTE_DEDUP_INTERVAL = 100  # every ~50 minutes at 30s intervals
        while True:
            self.run_scan_cycle()
            self.run_knowledge_pipeline()
            self.rebuild_exports()
            # Run local retrospect every 10 cycles (~5 minutes)
            # auto-promotes draft→refined→canonized, finds merge candidates
            if cycle % 10 == 0:
                self.run_retrospect_cycle()
            # Run remote (embedding) dedup less frequently — heavy operation
            # uploads DB to HF Space, runs fastembed, downloads result
            if cycle > 0 and cycle % REMOTE_DEDUP_INTERVAL == 0:
                try:
                    self.run_remote_dedup()
                except Exception as exc:
                    logging.warning("remote_dedup skipped (non-fatal): %s", exc)
            cycle += 1
            if max_cycles is not None and cycle >= max_cycles:
                return
            sleep_fn(self.config.poll_interval_seconds)
