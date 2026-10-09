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
from hermes.scoped_auth import ScopedPrincipalRegistry

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

# Only liveness and login assets are public. Knowledge, exports, dashboard data,
# and packaged agent assets may contain private material and require auth.
_PUBLIC_PREFIXES = ("/favicon",)
_PUBLIC_EXACT = frozenset({"/health", "/login"})
_PAGE_EXTENSIONS = ("", ".html", ".htm")


def _is_public(path: str) -> bool:
    if path in _PUBLIC_EXACT:
        return True
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


def _is_page_request(request: Request) -> bool:
    """Return True for browser-style page requests that should go to /login."""
    path = request.url.path
    if request.method != "GET" or path.startswith("/api/"):
        return False
    suffix = Path(path).suffix
    if suffix and suffix not in _PAGE_EXTENSIONS:
        return False
    accept = request.headers.get("accept", "")
    return not accept or "text/html" in accept or "*/*" in accept


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that enforces authentication on non-public routes.

    Supports two modes:
    * Bearer token auth (auth_token set): validates ``Authorization: Bearer ***
    * Username/password only (auth_token None but auth_enabled True): only accepts session cookies
    * Disabled (auth_token None, auth_enabled False): all requests pass through

    Public routes are limited to liveness checks, login, and favicon assets.
    """

    def __init__(self, app: ASGIApp, *, auth_token: str | None = None, auth_enabled: bool = False, session_cookie_value: str | None = None, scoped_registry: ScopedPrincipalRegistry | None = None) -> None:
        super().__init__(app)
        self._auth_token = auth_token
        self._auth_enabled = auth_enabled or auth_token is not None
        self._session_cookie_value = session_cookie_value
        self._scoped_registry = scoped_registry

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Auth disabled → pass-through
        if not self._auth_enabled:
            return await call_next(request)

        # Public routes skip auth
        if _is_public(request.url.path):
            return await call_next(request)

        if self._scoped_registry is not None and self._scoped_registry.authorize_http(request):
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

        # For browser/page requests, redirect to login instead of returning JSON.
        # curl and some monitors use Accept: */*, so classify non-API GET pages
        # by path as well; API endpoints must keep fail-closed 401 JSON.
        if _is_page_request(request):
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
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _canonical_origin(value: str, *, allow_path: bool) -> tuple[str, str, int] | None:
    """Return a strict ``(scheme, host, port)`` tuple for an HTTP(S) URL."""
    try:
        parsed = urlparse(value)
        scheme = parsed.scheme.lower()
        if scheme not in _DEFAULT_PORTS or not parsed.netloc:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        if not allow_path and (parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            return None
        host = (parsed.hostname or "").rstrip(".").casefold()
        if not host:
            return None
        port = parsed.port or _DEFAULT_PORTS[scheme]
    except (TypeError, ValueError):
        return None
    return scheme, host, port


def _request_origin(request: Request) -> tuple[str, str, int] | None:
    host = request.headers.get("host", "")
    if not host:
        return None
    # TLS terminates at nginx/Cloudflare in production.  The application is
    # intentionally bound to loopback, so the proxy-provided scheme is the
    # authoritative external origin; direct local tests fall back to the URL.
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    scheme = forwarded_proto or request.url.scheme
    return _canonical_origin(f"{scheme}://{host}", allow_path=False)


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
        scoped_registry: ScopedPrincipalRegistry | None = None,
    ) -> None:
        super().__init__(app)
        self._auth_token = auth_token
        self._csrf_secret = csrf_secret
        self._scoped_registry = scoped_registry

    def _csrf_enabled(self) -> bool:
        return self._auth_token is not None or self._csrf_secret is not None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self._csrf_enabled():
            return await call_next(request)

        if request.method not in _MUTATING_METHODS:
            return await call_next(request)

        if self._scoped_registry is not None and self._scoped_registry.authorize_http(request):
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

        # 3) Strict Origin / Referer same-origin check. Prefer Origin when it
        # is present: a conflicting Referer must never rescue a bad Origin.
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")
        expected = _request_origin(request)
        supplied = origin or referer
        if expected is not None and supplied:
            actual = _canonical_origin(supplied, allow_path=not bool(origin))
            if actual == expected:
                return await call_next(request)
        # Some privacy-oriented browsers and proxy paths omit Origin/Referer.
        # When the trusted TLS terminator explicitly marks the request HTTPS,
        # accept only a header-less browser form; conflicting origins above
        # remain rejected.
        if not supplied and request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower() == "https":
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