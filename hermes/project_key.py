from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
import re
from urllib.parse import urlparse

import yaml


PROJECT_ROOT_SENTINELS = (".git", "pyproject.toml", "package.json", "Cargo.toml")


@dataclass(frozen=True)
class ProjectKeyResult:
    project_key: str
    source: str
    warning: str | None = None


def resolve_project_key(cwd: str | Path) -> ProjectKeyResult:
    path = Path(cwd).resolve()

    explicit = _resolve_from_hermes_project(path)
    if explicit is not None:
        return explicit

    remote_hash = _resolve_from_git_remote(path)
    if remote_hash is not None:
        return remote_hash

    fallback = _resolve_from_project_root_name(path)
    if fallback is not None:
        return fallback

    return ProjectKeyResult(project_key="global", source="global")


def _resolve_from_hermes_project(path: Path) -> ProjectKeyResult | None:
    for candidate in (path, *path.parents):
        marker = candidate / ".hermes-project"
        if marker.exists():
            data = yaml.safe_load(marker.read_text(encoding="utf-8")) or {}
            project_key = str(data["project_key"]).strip()
            return ProjectKeyResult(project_key=project_key, source="hermes-project")
    return None


def _resolve_from_git_remote(path: Path) -> ProjectKeyResult | None:
    for candidate in (path, *path.parents):
        git_dir = candidate / ".git"
        if git_dir.is_dir():
            config = git_dir / "config"
            if not config.exists():
                return None
            text = config.read_text(encoding="utf-8")
            match = re.search(r"url\s*=\s*(.+)", text)
            if not match:
                return None
            normalized = _normalize_remote_url(match.group(1).strip())
            project_key = sha1(normalized.encode("utf-8")).hexdigest()[:12]
            return ProjectKeyResult(project_key=project_key, source="git-remote")
    return None


def _resolve_from_project_root_name(path: Path) -> ProjectKeyResult | None:
    for candidate in (path, *path.parents):
        if any((candidate / sentinel).exists() for sentinel in PROJECT_ROOT_SENTINELS):
            return ProjectKeyResult(
                project_key=candidate.name,
                source="cwd-fallback",
                warning="cwd-derived fallback keys are not portable across machines.",
            )
    return None


def _normalize_remote_url(url: str) -> str:
    if "://" in url:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path
    else:
        host, path = url.split(":", 1)
        host = host.split("@")[-1].lower()
        path = f"/{path}"
    if path.endswith(".git"):
        path = path[:-4]
    return f"{host}{path}".strip("/")

