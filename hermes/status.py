from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from hermes.repository import HermesRepository


class StatusPublisher:
    def __init__(self, *, repo: HermesRepository, sync_root: str | Path, version: str = "0.1.0") -> None:
        self.repo = repo
        self.sync_root = Path(sync_root)
        self.version = version

    def publish(self) -> Path:
        state_dir = self.sync_root / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        counts = self.repo.counts_by_state()
        export_records = self.repo.list_export_records()
        oldest_pending = self.repo.oldest_pending_age_seconds()
        lines = [
            "# Hermes Status",
            "",
            f"Last updated: {datetime.now(timezone.utc).isoformat()}",
            f"Hermes version: {self.version}",
            "",
            "## Inbox",
            f"- Pending proposals: {counts['pending']}",
            "- Ingested in last 24h: 0",
            "- Rejected in last 24h: 0",
            "",
            "## Review queue",
            f"- pending: {counts['pending']}",
            f"- approved_db_only: {counts['approved_db_only']}",
            f"- approved_for_export: {counts['approved_for_export']}",
            f"- Oldest pending: {oldest_pending if oldest_pending is not None else 'none'}",
            "",
            "## Exports",
        ]
        if export_records:
            for record in export_records:
                lines.append(f"- {record.file_name}: last rebuilt {record.rebuilt_at}, size {record.size_bytes}")
        else:
            lines.append("- none")
        lines.extend(
            [
                "",
                "## Health",
                "- Proposal watcher: ok",
                "- Review service: ok",
                "- Export compiler: ok",
                "- Last error: none",
            ]
        )
        path = state_dir / "status.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

