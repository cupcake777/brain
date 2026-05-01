from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HermesConfig:
    sync_root: Path
    db_path: Path
    auto_approve_low_risk: bool = True
    poll_interval_seconds: int = 30
    stale_export_tolerance_hours: int = 72
    stale_export_hard_limit_days: int = 14
    auth_token: str | None = None
    auth_username: str | None = None
    auth_password: str | None = None
    csrf_secret: str | None = None
    tls_cert: str | None = None
    tls_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sync_root", Path(self.sync_root))
        object.__setattr__(self, "db_path", Path(self.db_path))

    @property
    def proposals_dir(self) -> Path:
        return self.sync_root / "inbox" / "proposals"

    @property
    def pending_dir(self) -> Path:
        return self.sync_root / "review" / "pending"

    @property
    def approved_dir(self) -> Path:
        return self.sync_root / "review" / "approved"

    @property
    def rejected_dir(self) -> Path:
        return self.sync_root / "review" / "rejected"

    @property
    def state_dir(self) -> Path:
        return self.sync_root / "state"

    @property
    def global_exports_dir(self) -> Path:
        return self.sync_root / "exports" / "global"

    @property
    def project_exports_dir(self) -> Path:
        return self.sync_root / "exports" / "projects"

    def ensure_directories(self) -> None:
        for directory in (
            self.proposals_dir,
            self.pending_dir,
            self.approved_dir,
            self.rejected_dir,
            self.state_dir,
            self.global_exports_dir,
            self.project_exports_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

