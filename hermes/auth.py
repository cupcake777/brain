"""Authentication, CSRF, DB-fail-closed, and TLS configuration for Hermes."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from hermes.config import HermesConfig

# ---------------------------------------------------------------------------
# Bearer-token security scheme (reusable dependency)
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


async def require_bearer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    config: HermesConfig,  # injected via app.state or manually
) -> None:
    """FastAPI dependency that enforces bearer-token auth.

    Raise 401 if ``config.auth_token`` is set and the request carries no
    matching ``Authorization: Bearer *** header.  If ``auth_token`` is
    ``None`` the dependency is a no-op (auth disabled).
    """
    if config.auth_token is None:
        return  # auth disabled – pass-through

    if credentials is None or credentials.credentials != config.auth_token:
        raise HTTPException(status_code=401, detail="unauthorized")


# ---------------------------------------------------------------------------
# TokenAuthMiddleware  – blanket bearer protection on every route
# ---------------------------------------------------------------------------

# Paths that never require authentication.
# Paths that never require authentication.
# Note: /exports/projects/ and /exports/global/ are public for file downloads,
# but /exports/ (the list page) requires auth.
_PUBLIC_PREFIXES = ("/health", "/exports/projects/", "/exports/global/", "/login", "/favicon")
_PUBLIC_EXACT = frozenset({"/health", "/login", "/logout"})


def _is_public(path: str) -> bool:
    if path in _PUBLIC_EXACT:
        return True
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that enforces authentication on non-public routes.

    Supports two modes:
    * Bearer token auth (auth_token set): validates ``Authorization: Bearer ***
    * Username/password only (auth_token None but auth_enabled True): only accepts session cookies
    * Disabled (auth_token None, auth_enabled False): all requests pass through

    Public routes: ``/health``, ``/exports/*``, ``/login``, ``/logout``.
    """

    def __init__(self, app: ASGIApp, *, auth_token: str | None = None, auth_enabled: bool = False, session_cookie_value: str | None = None) -> None:
        super().__init__(app)
        self._auth_token = auth_token
        self._auth_enabled = auth_enabled or auth_token is not None
        self._session_cookie_value = session_cookie_value

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Auth disabled → pass-through
        if not self._auth_enabled:
            return await call_next(request)

        # Public routes skip auth
        if _is_public(request.url.path):
            return await call_next(request)

        # Validate Bearer token (if configured)
        if self._auth_token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                if token == self._auth_token:
                    return await call_next(request)

            # Check cookie for token-based auth
            cookie_val = request.cookies.get("hermes_auth")
            if cookie_val:
                expected = hashlib.sha256(self._auth_token.encode()).hexdigest()
                if cookie_val == expected:
                    return await call_next(request)

        # Check session cookie (set by /login form for username/password mode)
        if self._session_cookie_value:
            cookie_val = request.cookies.get("hermes_auth")
            if cookie_val == self._session_cookie_value:
                return await call_next(request)

        # For browser HTML requests, redirect to login instead of returning JSON
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="/login", status_code=303)

        return Response(
            content='{"detail":"unauthorized"}',
            status_code=401,
            media_type="application/json",
        )


# ---------------------------------------------------------------------------
# CSRFMiddleware  – Origin/Referer check for mutating requests
# ---------------------------------------------------------------------------

_MUTATING_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})


class CSRFMiddleware(BaseHTTPMiddleware):
    """Lightweight CSRF protection for state-changing requests.

    A mutating request (POST/PUT/DELETE/PATCH) is allowed through when **any**
    of the following is true:

    1. A valid ``Authorization: Bearer *** header is present (API
       clients are inherently CSRF-safe because scripts cannot read the
       token from another origin).
    2. An ``X-CSRF-Token`` header matches ``csrf_secret``.
    3. The ``Origin`` or ``Referer`` header matches the request's ``Host``
       (standard same-origin check).

    If ``csrf_secret`` is ``None`` **and** ``auth_token`` is ``None``, CSRF
    protection is disabled entirely.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        auth_token: str | None = None,
        csrf_secret: str | None = None,
    ) -> None:
        super().__init__(app)
        self._auth_token = auth_token
        self._csrf_secret = csrf_secret

    def _csrf_enabled(self) -> bool:
        return self._auth_token is not None or self._csrf_secret is not None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self._csrf_enabled():
            return await call_next(request)

        if request.method not in _MUTATING_METHODS:
            return await call_next(request)

        # Login form POST is always allowed (no auth yet)
        if request.url.path in ("/login",):
            return await call_next(request)

        # 1) Valid bearer token → pass (API client, not browser form)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer ") and self._auth_token is not None:
            if auth_header[7:] == self._auth_token:
                return await call_next(request)

        # 2) X-CSRF-Token header matches secret
        csrf_header = request.headers.get("x-csrf-token", "")
        if self._csrf_secret is not None and csrf_header == self._csrf_secret:
            return await call_next(request)

        # 3) Origin / Referer same-origin check
        host = request.headers.get("host", "")
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")

        if host:
            for header_value in (origin, referer):
                if not header_value:
                    continue
                parsed = urlparse(header_value)
                # Compare scheme+host+port (netloc) against Host header
                # Host header may or may not include port; be lenient
                header_host = parsed.hostname or ""
                header_port = parsed.port
                host_parts = host.split(":")
                host_name = host_parts[0]
                host_port = int(host_parts[1]) if len(host_parts) > 1 else None

                if header_host == host_name:
                    # If both specify a port, they must match; otherwise OK
                    if header_port is not None and host_port is not None:
                        if header_port == host_port:
                            return await call_next(request)
                    else:
                        return await call_next(request)

        return Response(
            content='{"detail":"csrf check failed"}',
            status_code=403,
            media_type="application/json",
        )


# ---------------------------------------------------------------------------
# DBFailClosedMiddleware  – fail-closed on sqlite3 errors
# ---------------------------------------------------------------------------


class DBFailClosedMiddleware(BaseHTTPMiddleware):
    """Catches ``sqlite3.OperationalError`` bubbling out of route handlers and
    returns ``503 {"detail": "database unavailable"}``.

    Fail-closed: when the DB is unreachable no writes are accepted and all
    reads surface a clear 503 rather than a 500 or a stale partial response.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except sqlite3.OperationalError:
            return Response(
                content='{"detail":"database unavailable"}',
                status_code=503,
                media_type="application/json",
            )


# ---------------------------------------------------------------------------
# TLSConfig  – frozen dataclass for TLS termination settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TLSConfig:
    """Configuration for HTTPS / TLS termination.

    ``enabled`` is ``True`` only when **both** ``cert_path`` and ``key_path``
    are set **and** the referenced files exist on disk.
    """

    cert_path: str | None = None
    key_path: str | None = None

    @property
    def enabled(self) -> bool:
        if self.cert_path is None or self.key_path is None:
            return False
        return Path(self.cert_path).is_file() and Path(self.key_path).is_file()