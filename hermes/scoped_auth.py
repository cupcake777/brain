"""Server-owned scoped token registry for Brain multi-agent access."""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi import Request

from hermes.event_store import Principal


class ScopedAuthError(RuntimeError):
    pass


class ScopedPrincipalRegistry:
    """Resolve bearer tokens to bounded actor/workspace/project principals.

    Registry files store SHA-256 token digests only. The request may select a
    project through ``X-Brain-Project`` only when that project is explicitly
    listed or the trusted registry grants ``*``. The header selects scope; it
    never grants scope.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = RLock()
        self._file_signature: tuple[int, int, int] | None = None
        self._records: tuple[dict[str, Any], ...] = ()

    @staticmethod
    def token_digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _load(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            try:
                stat = self.path.stat()
            except OSError as exc:
                raise ScopedAuthError("scoped principal registry unavailable") from exc
            signature = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
            if signature == self._file_signature:
                return self._records
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ScopedAuthError("invalid scoped principal registry") from exc
            if not isinstance(payload, dict) or payload.get("version") != 1:
                raise ScopedAuthError("unsupported scoped principal registry")
            rows = payload.get("tokens")
            if not isinstance(rows, list):
                raise ScopedAuthError("scoped principal registry tokens must be a list")
            records: list[dict[str, Any]] = []
            seen: set[str] = set()
            for raw in rows:
                if not isinstance(raw, dict):
                    raise ScopedAuthError("invalid scoped principal record")
                digest = raw.get("token_sha256")
                actor = raw.get("actor")
                workspace = raw.get("workspace")
                projects = raw.get("projects")
                permissions = raw.get("permissions")
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or not isinstance(actor, str)
                    or not actor
                    or not isinstance(workspace, str)
                    or not workspace
                    or not isinstance(projects, list)
                    or not projects
                    or not all(isinstance(x, str) and x for x in projects)
                    or not isinstance(permissions, list)
                    or not all(isinstance(x, str) and x for x in permissions)
                ):
                    raise ScopedAuthError("invalid scoped principal fields")
                if digest in seen:
                    raise ScopedAuthError("duplicate scoped token digest")
                seen.add(digest)
                records.append(
                    {
                        "name": str(raw.get("name") or actor),
                        "token_sha256": digest.lower(),
                        "actor": actor,
                        "workspace": workspace,
                        "projects": tuple(projects),
                        "permissions": frozenset(permissions),
                        "default_project": str(raw.get("default_project") or projects[0]),
                    }
                )
            self._records = tuple(records)
            self._file_signature = signature
            return self._records

    @staticmethod
    def _bearer(request: Request) -> str | None:
        value = request.headers.get("authorization", "")
        if not value.startswith("Bearer "):
            return None
        token = value[7:].strip()
        return token or None

    def record_for_request(self, request: Request) -> dict[str, Any] | None:
        token = self._bearer(request)
        if token is None:
            return None
        digest = self.token_digest(token)
        try:
            rows = self._load()
        except ScopedAuthError:
            return None
        for row in rows:
            if hmac.compare_digest(row["token_sha256"], digest):
                return row
        return None

    def authenticate(self, request: Request, *, permission: str) -> Principal | None:
        row = self.record_for_request(request)
        if row is None or permission not in row["permissions"]:
            return None
        selected = request.headers.get("x-brain-project", "").strip()
        project = selected or row["default_project"]
        projects = row["projects"]
        if project not in projects and "*" not in projects:
            return None
        return Principal(actor=row["actor"], workspace=row["workspace"], project=project)

    def authorize_http(self, request: Request) -> bool:
        """Allow outer auth middleware to pass only explicitly permitted calls."""
        row = self.record_for_request(request)
        if row is None:
            return False
        path = request.url.path
        method = request.method.upper()
        permission: str | None = None
        if path.startswith("/api/v2/brain/events"):
            permission = "events:write" if method in {"POST", "PUT", "PATCH", "DELETE"} else "events:read"
        elif path.startswith("/api/v2/brain/proposals"):
            permission = "proposals:write" if method in {"POST", "PUT", "PATCH", "DELETE"} else "proposals:read"
        elif path == "/api/v1/brain/outcome":
            permission = "outcomes:write"
        elif path == "/api/v1/brain/propose":
            permission = "proposals:write"
        elif path == "/api/v1/brain/finalize":
            permission = "outcomes:write"
        elif path == "/api/v1/brain/sources/retrieve":
            permission = "sources:read"
        return permission is not None and permission in row["permissions"]
