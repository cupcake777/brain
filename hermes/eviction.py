from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from hermes.repository import HermesRepository


@dataclass(frozen=True)
class StaleExport:
    scope_type: str
    project_key: str
    file_name: str
    age_hours: float
    severity: str  # "soft" or "hard"


@dataclass(frozen=True)
class EvictionResult:
    evicted_count: int
    flagged_for_rebuild_count: int
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BudgetPressure:
    scope: str
    current_bytes: int
    soft_cap: int
    hard_cap: int
    over_soft: bool
    over_hard: bool


class EvictionService:
    def __init__(
        self,
        *,
        repo: HermesRepository,
        sync_root: str | Path,
        stale_tolerance_hours: int = 72,
        stale_hard_limit_days: int = 14,
    ) -> None:
        self.repo = repo
        self.sync_root = Path(sync_root)
        self.stale_tolerance_hours = stale_tolerance_hours
        self.stale_hard_limit_days = stale_hard_limit_days

    # -- stale export detection ------------------------------------------------

    def detect_stale_exports(self) -> list[StaleExport]:
        now = datetime.now(timezone.utc)
        soft_limit_hours = float(self.stale_tolerance_hours)
        hard_limit_hours = float(self.stale_hard_limit_days * 24)
        stale: list[StaleExport] = []

        for record in self.repo.list_export_records():
            rebuilt_at = datetime.fromisoformat(record.rebuilt_at)
            age_hours = (now - rebuilt_at).total_seconds() / 3600.0

            if age_hours >= hard_limit_hours:
                stale.append(StaleExport(
                    scope_type=record.scope_type,
                    project_key=record.project_key,
                    file_name=record.file_name,
                    age_hours=age_hours,
                    severity="hard",
                ))
            elif age_hours >= soft_limit_hours:
                stale.append(StaleExport(
                    scope_type=record.scope_type,
                    project_key=record.project_key,
                    file_name=record.file_name,
                    age_hours=age_hours,
                    severity="soft",
                ))

        return stale

    # -- export eviction -------------------------------------------------------

    def evict_stale_exports(self) -> EvictionResult:
        stale = self.detect_stale_exports()
        evicted_count = 0
        flagged_for_rebuild_count = 0
        errors: list[str] = []

        for item in stale:
            try:
                if item.severity == "hard":
                    file_path = self._resolve_export_path(
                        item.scope_type, item.project_key, item.file_name,
                    )
                    if file_path.exists():
                        file_path.unlink()
                    self.repo.delete_export(
                        item.scope_type, item.project_key, item.file_name,
                    )
                    evicted_count += 1
                else:
                    flagged_for_rebuild_count += 1
            except Exception as exc:
                errors.append(
                    f"{item.scope_type}/{item.project_key}/{item.file_name}: {exc}"
                )

        return EvictionResult(
            evicted_count=evicted_count,
            flagged_for_rebuild_count=flagged_for_rebuild_count,
            errors=errors,
        )

    # -- proposal demotion -----------------------------------------------------

    def demote_low_priority(
        self,
        project_key: str | None,
        current_bytes: int,
        soft_cap: int,
    ) -> list[str]:
        if current_bytes <= soft_cap:
            return []

        candidates = self.repo.list_proposals_ordered_for_demotion(project_key)
        if not candidates:
            return []

        # Estimate per-proposal byte contribution using suggested_memory field
        # plus the markdown list prefix "- " and newline.
        contributions: list[tuple[str, int]] = []
        for proposal in candidates:
            mem = str(proposal.get("suggested_memory", ""))
            approx_bytes = len(("- " + mem + "\n").encode("utf-8"))
            contributions.append((str(proposal["proposal_id"]), approx_bytes))

        # Demote candidates (already ordered by retrieval_count_30d ASC,
        # inserted_at ASC) until the estimated remaining size is under soft_cap.
        bytes_to_shed = current_bytes - soft_cap
        demoted_ids: list[str] = []
        shed_so_far = 0

        for proposal_id, approx_bytes in contributions:
            if shed_so_far >= bytes_to_shed:
                break
            self.repo.transition_state(proposal_id, "approved_db_only")
            demoted_ids.append(proposal_id)
            shed_so_far += approx_bytes

        return demoted_ids

    # -- soft cap enforcement --------------------------------------------------

    def check_budget_pressure(
        self,
        budgets: "ExportBudgets",  # noqa: F821 – avoid circular import at module level
    ) -> list[BudgetPressure]:
        from hermes.exporter import ExportBudgets  # deferred to avoid circular import

        pressures: list[BudgetPressure] = []
        records = self.repo.list_export_records()

        # Index records by (scope_type, project_key) for quick lookup
        size_map: dict[tuple[str, str], int] = {}
        for rec in records:
            size_map[(rec.scope_type, rec.project_key)] = rec.size_bytes

        # -- global scope -------------------------------------------------------
        global_bytes = size_map.get(("global", "global"), 0)
        global_pressure = BudgetPressure(
            scope="global",
            current_bytes=global_bytes,
            soft_cap=budgets.global_soft_cap,
            hard_cap=budgets.global_hard_cap,
            over_soft=global_bytes > budgets.global_soft_cap,
            over_hard=global_bytes > budgets.global_hard_cap,
        )
        pressures.append(global_pressure)

        if global_pressure.over_soft and not global_pressure.over_hard:
            self.demote_low_priority(
                project_key=None,
                current_bytes=global_bytes,
                soft_cap=budgets.global_soft_cap,
            )

        # -- per-project scopes -------------------------------------------------
        project_keys = self.repo.list_exportable_project_keys()
        for pk in project_keys:
            proj_bytes = size_map.get(("project", pk), 0)
            proj_pressure = BudgetPressure(
                scope=f"project:{pk}",
                current_bytes=proj_bytes,
                soft_cap=budgets.project_soft_cap,
                hard_cap=budgets.project_hard_cap,
                over_soft=proj_bytes > budgets.project_soft_cap,
                over_hard=proj_bytes > budgets.project_hard_cap,
            )
            pressures.append(proj_pressure)

            if proj_pressure.over_soft and not proj_pressure.over_hard:
                self.demote_low_priority(
                    project_key=pk,
                    current_bytes=proj_bytes,
                    soft_cap=budgets.project_soft_cap,
                )

        return pressures

    # -- helpers ---------------------------------------------------------------

    def _resolve_export_path(
        self, scope_type: str, project_key: str, file_name: str,
    ) -> Path:
        if scope_type == "global":
            return self.sync_root / "exports" / "global" / file_name
        return self.sync_root / "exports" / "projects" / file_name
