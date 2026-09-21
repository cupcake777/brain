"""Additive v2 storage layer for events, proposals, documents, jobs, and outbox.

This module is the persistent foundation of the v2 Brain protocol.  It is
intentionally narrow: an :class:`EventStore` instance owns a single SQLite
file and exposes the bounded operations the rest of the application needs.

Design invariants (Task 3 of the backend convergence plan):

* **Additive migration** — the v2 schema is layered on top of the v1
  fixture.  Re-running migration is a no-op; original v1 tables and rows
  are preserved untouched.
* **Immutable rows** — every persisted row carries a monotonically
  increasing ``version`` and a content digest.  There is no UPDATE on the
  fact tables; corrections create new revisions and the current pointer
  advances to the latest version.
* **Canonical digests** — content identity is determined by a stable
  digest of the canonicalised payload.  Same payload → idempotent ack;
  same ``(id, version)`` with different payload → ``409 ConflictError``.
* **Privacy before write** — the storage layer rejects payloads that
  carry secret-like content (labelled credentials, API key signatures,
  bearer tokens, etc.) **before** any row is inserted.  No body, no
  matched substring, no detector text is ever echoed back to the caller.
* **No URL fetching** — source documents are resolved only against the
  local registry.  The store never opens a network socket.
* **Body-size limit** — payloads above :data:`MAX_BODY_BYTES` are
  rejected with :class:`BodyTooLargeError` before the sensitive scan
  even runs (DoS hardening).
* **Principal scoping** — every read and write is bound to the
  authenticated principal recorded by :class:`StaticPrincipalAdapter`
  (or compatible adapter).  Cross-workspace / cross-project access is
  rejected fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import UUID


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


#: Maximum serialised payload size accepted by the storage layer.  Bodies
#: larger than this are rejected with :class:`BodyTooLargeError` **before**
#: any sensitive-content scan, so a giant payload cannot amplify CPU cost.
MAX_BODY_BYTES = 65_536


#: Current schema version produced by :meth:`EventStore.schema_version`.
SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EventStoreError(Exception):
    """Base class for every storage-layer failure."""


class ConflictError(EventStoreError):
    """Raised on a CAS / version mismatch (HTTP 409 semantic)."""


class NotFoundError(EventStoreError):
    """Raised when a requested identity does not exist in the store."""


class ReferenceUnavailableError(EventStoreError):
    """Raised when a ``source_ref`` points to a non-registered document."""


class UnauthorizedError(EventStoreError):
    """Raised when the principal cannot act on the requested scope."""


class BodyTooLargeError(EventStoreError):
    """Raised when a serialised payload exceeds :data:`MAX_BODY_BYTES`."""


class SensitiveRejectedError(EventStoreError):
    """Raised when the storage-layer privacy gate rejects a payload.

    The matched substring is **never** included in the message or
    attributes — see ``brain-api-review-privacy.md``.
    """

    def __init__(self, detector: str = "sensitive_content_detected", field: str = "") -> None:
        self.detector = detector
        self.field = field
        super().__init__(
            f"sensitive_content_detected ({detector} @ {field or '<root>'})"
        )


# ---------------------------------------------------------------------------
# Principal adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Principal:
    """Authenticated identity bound server-side to every read and write."""

    actor: str
    workspace: str
    project: str

    def __post_init__(self) -> None:
        if not self.actor:
            raise ValueError("principal.actor must not be empty")
        if not self.workspace:
            raise ValueError("principal.workspace must not be empty")
        if not self.project:
            raise ValueError("principal.project must not be empty")


class StaticPrincipalAdapter:
    """Principal adapter that returns a fixed identity for testing / CLI use.

    The real HTTP API passes a request-bound adapter that resolves the
    authenticated principal from a session cookie or bearer token.  This
    adapter returns the same :class:`Principal` for every request — it
    exists so the storage layer can be exercised without an HTTP frame.
    """

    def __init__(self, *, actor: str, workspace: str, project: str) -> None:
        self._principal = Principal(actor=actor, workspace=workspace, project=project)

    @property
    def principal(self) -> Principal:
        return self._principal

    def authenticate(self, request_context: Any) -> Principal | None:
        """Return the bound principal.  Returns ``None`` to fail-closed
        when no mapping is configured (e.g. production uses an adapter
        that returns ``None`` for unauthenticated requests)."""
        return self._principal


class _DenyAllAdapter:
    """Adapter used in tests to force an unauthorised path."""

    def authenticate(self, request_context: Any) -> Principal | None:
        return None


# ---------------------------------------------------------------------------
# Storage-layer privacy gate
# ---------------------------------------------------------------------------


# Bounded regexes for the storage-layer labelled-secret detector.  These
# are intentionally stricter than the network-facing ``SensitiveContentGate``
# so that a payload which merely *names* a labelled credential (e.g.
# ``api_key=«redacted:sk-…»``) is rejected before write.
_LABELED_SECRET = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd)\s*[:=]\s*\S{4,}"
)
_PROVIDER_KEY_SIGNATURE = re.compile(
    r"\bsk-[A-Za-z0-9_\-]{16,200}\b"
    r"|\bsk-ant-[A-Za-z0-9_\-]{16,200}\b"
    r"|\bgsk_[A-Za-z0-9]{16,200}\b"
    r"|\bghp_[A-Za-z0-9]{16,200}\b"
    r"|\bgithub_pat_[A-Za-z0-9_]{16,200}\b"
    r"|\bAIza[0-9A-Za-z_\-]{16,200}\b"
    r"|\bAKIA[0-9A-Z]{12,32}\b"
    r"|\bhf_[A-Za-z0-9]{16,200}\b"
    r"|\bxox[abprs]-[A-Za-z0-9\-]{10,200}\b"
)
_BEARER_TOKEN = re.compile(
    r"\bbearer\s+[A-Za-z0-9._\-]{8,4096}\b", flags=re.IGNORECASE
)


def _walk_strings(payload: Any) -> Iterable[tuple[Any, str]]:
    """Yield ``(value, field_path)`` pairs for every string in *payload*."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            child = f".{key}" if isinstance(key, str) else f"[{key!r}]"
            yield from _walk_strings_field(value, key, child)
    else:
        yield from _walk_strings_field(payload, None, "")


def _walk_strings_field(value: Any, key: Any, suffix: str) -> Iterable[tuple[Any, str]]:
    field = f".{key}" if isinstance(key, str) else (f"[{key!r}]" if key is not None else "")
    if isinstance(value, dict):
        for sub_key, sub_value in value.items():
            yield from _walk_strings_field(sub_value, sub_key, field)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings_field(item, index, f"{field}[{index}]")
    elif isinstance(value, str):
        yield value, field.lstrip(".")


def _storage_privacy_scan(payload: Any) -> tuple[str, str] | None:
    """Walk *payload* and return ``(detector, field)`` for the first hit.

    Returns ``None`` when the payload is clean.  Never returns the matched
    substring, the surrounding context, or the payload itself.
    """
    for text, field in _walk_strings(payload):
        if not text:
            continue
        if _LABELED_SECRET.search(text):
            return "labeled_secret", field or "<root>"
        if _PROVIDER_KEY_SIGNATURE.search(text):
            return "provider_key_signature", field or "<root>"
        if _BEARER_TOKEN.search(text):
            return "bearer_token", field or "<root>"
    return None


# ---------------------------------------------------------------------------
# Canonical digest helper
# ---------------------------------------------------------------------------


_DIGEST_FIELDS: tuple[str, ...] = (
    "project_id",
    "agent_id",
    "occurred_at",
    "target_id",
    "action",
    "result",
    "lesson",
    "draft",
    "source_refs",
    "origin",
    "classification",
)


def _digest_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("digest requires timezone-aware datetime")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _digest_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_digest_value(v) for v in value]
    return value


def canonical_proposal_digest(payload: Mapping[str, Any]) -> str:
    """Return the SHA-256 hex digest of the canonicalised proposal payload.

    The ``id`` and ``version`` fields are excluded so two revisions of
    the *same* proposal have a comparable digest across versions.
    """
    canonical: dict[str, Any] = {}
    for field in _DIGEST_FIELDS:
        if field in payload:
            canonical[field] = _digest_value(payload[field])
    body = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("timezone-aware datetime required")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"unsupported value for JSON: {value!r}")


def _serialise(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    )


def _deserialise(raw: str | None) -> Any:
    if raw is None:
        return None
    return json.loads(raw)


def _coerce_uuid(value: Any) -> uuid.UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _coerce_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        # Accept ISO 8601 with or without trailing 'Z'.
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    raise TypeError(f"unsupported datetime value: {value!r}")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# EventStore
# ---------------------------------------------------------------------------


_EVENT_COLUMNS: tuple[str, ...] = (
    "id",
    "version",
    "project_id",
    "agent_id",
    "occurred_at",
    "action",
    "result",
    "origin",
    "classification",
    "payload_digest",
    "principal_actor",
    "principal_workspace",
    "principal_project",
    "received_at",
    "source_refs",
)


class EventStore:
    """Additive SQLite storage for v2 events / proposals / documents.

    The store is safe to instantiate on a file that already contains v1
    data — the v2 migration only creates new tables and inserts the
    schema-version marker row.  Original tables and rows are untouched.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        principal: Any | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # The principal adapter is captured at construction time so that
        # every call on this instance is bound to the same identity.  A
        # ``None`` adapter fails-closed (see ``_resolve_principal``).
        self._principal_adapter = principal
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    # -- migration -----------------------------------------------------------

    def _migrate(self) -> None:
        """Apply the additive v2 migration.

        The migration is wrapped in ``CREATE TABLE IF NOT EXISTS`` so
        re-running it on an already-migrated file is a no-op.  Original
        v1 tables are never inspected or dropped.
        """
        cur = self._conn.cursor()
        # Schema-version marker — additive; never conflicts with v1.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        cur.execute(
            "INSERT OR IGNORE INTO schema_meta(key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS source_events (
                id TEXT NOT NULL,
                version INTEGER NOT NULL,
                project_id TEXT,
                agent_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                client_digest TEXT NOT NULL DEFAULT '',
                action TEXT,
                result TEXT,
                origin TEXT NOT NULL,
                classification TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL,
                received_at TEXT NOT NULL,
                source_refs TEXT NOT NULL,
                PRIMARY KEY (id, version)
            )
            """
        )
        event_columns = {
            row[1] for row in cur.execute("PRAGMA table_info(source_events)")
        }
        if "client_digest" not in event_columns:
            cur.execute(
                "ALTER TABLE source_events ADD COLUMN client_digest TEXT NOT NULL DEFAULT ''"
            )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS source_documents (
                id TEXT NOT NULL,
                version INTEGER NOT NULL,
                url TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                bytes_digest TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL,
                PRIMARY KEY (id, version)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS proposal_revisions (
                id TEXT NOT NULL,
                version INTEGER NOT NULL,
                project_id TEXT,
                agent_id TEXT NOT NULL,
                occurred_at TEXT,
                action TEXT,
                result TEXT,
                lesson TEXT,
                draft INTEGER NOT NULL,
                source_refs TEXT NOT NULL,
                workflow_state TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL,
                received_at TEXT NOT NULL,
                PRIMARY KEY (id, version)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS proposal_current (
                id TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                digest TEXT NOT NULL,
                workflow_state TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS check_runs (
                id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                proposal_version INTEGER NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS durable_jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                state TEXT NOT NULL,
                enqueued_at TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS outbox_events (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                reference_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def schema_version(self) -> int:
        """Return the schema version stored in ``schema_meta``."""
        cur = self._conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        )
        row = cur.fetchone()
        if row is None:
            return 0
        try:
            return int(row["value"])
        except (TypeError, ValueError):
            return 0

    # -- principal resolution ------------------------------------------------

    def _resolve_principal(self) -> Principal:
        adapter = self._principal_adapter
        if adapter is None:
            raise UnauthorizedError("no principal adapter configured")
        # Adapter contract: returns a Principal-like object or None.
        principal = adapter.authenticate(None)
        if principal is None:
            raise UnauthorizedError("authentication failed")
        if not isinstance(principal, Principal):
            # Allow duck-typed adapters that expose the three attributes.
            try:
                principal = Principal(
                    actor=getattr(principal, "actor"),
                    workspace=getattr(principal, "workspace"),
                    project=getattr(principal, "project"),
                )
            except Exception as exc:  # noqa: BLE001
                raise UnauthorizedError("invalid principal") from exc
        return principal

    def _enforce_scope(self, principal: Principal, *, project_id: str | None) -> None:
        if project_id is None:
            return
        if project_id != principal.project:
            raise UnauthorizedError("cross-project access rejected")

    # -- body-size + privacy gate -------------------------------------------

    def _enforce_body_limit(self, payload: Mapping[str, Any]) -> None:
        size = len(_serialise(dict(payload)).encode("utf-8"))
        if size > MAX_BODY_BYTES:
            raise BodyTooLargeError(
                f"payload exceeds MAX_BODY_BYTES ({size} > {MAX_BODY_BYTES})"
            )

    def _enforce_privacy(self, payload: Mapping[str, Any]) -> None:
        hit = _storage_privacy_scan(dict(payload))
        if hit is not None:
            detector, field = hit
            raise SensitiveRejectedError(detector=detector, field=field)

    # -- events --------------------------------------------------------------

    def record_event(
        self,
        *,
        id: Any,
        project_id: str | None = None,
        agent_id: str,
        occurred_at: datetime,
        action: str | None = None,
        result: str | None = None,
        source_refs: Iterable[Mapping[str, Any]] | None = None,
        origin: str = "hook",
        classification: str = "production",
        expected_version: int | None = None,
        client_digest: str | None = None,
    ) -> dict[str, Any]:
        principal = self._resolve_principal()
        self._enforce_scope(principal, project_id=project_id)

        source_refs_list = list(source_refs or [])
        ref_payload = [
            {"type": str(ref.get("type")), "id": str(ref.get("id"))}
            for ref in source_refs_list
        ]
        payload_for_scan = {
            "action": action,
            "result": result,
            "source_refs": ref_payload,
        }
        self._enforce_body_limit(payload_for_scan)
        self._enforce_privacy(payload_for_scan)
        if client_digest is not None and (
            not isinstance(client_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", client_digest)
        ):
            raise ValueError("client_digest must be lowercase sha256 hex")

        self._resolve_source_refs(ref_payload, principal=principal)

        # The keyword ``id`` may collide with a positional argument the
        # caller forwarded via ``**kwargs``; resolve it from locals last.
        event_uuid = _coerce_uuid(id)
        event_id = str(event_uuid)
        payload_digest = canonical_proposal_digest(
            {
                "project_id": project_id,
                "agent_id": agent_id,
                "occurred_at": _coerce_dt(occurred_at),
                "action": action,
                "result": result,
                "origin": origin,
                "classification": classification,
            }
        )

        with self._conn:  # transactional
            cur = self._conn.cursor()
            existing = cur.execute(
                "SELECT version, payload_digest, client_digest FROM source_events WHERE id = ?",
                (event_id,),
            ).fetchall()
            if existing:
                versions = sorted(row["version"] for row in existing)
                latest = versions[-1]
                if expected_version is not None and expected_version != latest:
                    raise ConflictError(
                        f"expected_version={expected_version} but current is {latest}"
                    )
                for row in existing:
                    if row["payload_digest"] == payload_digest and (
                        client_digest is None or row["client_digest"] == client_digest
                    ):
                        return {
                            "status": "duplicate",
                            "id": event_id,
                            "version": row["version"],
                            "digest": payload_digest,
                            "received_at": _now_utc().isoformat(),
                        }
                new_version = latest + 1
            else:
                if expected_version not in (None, 1):
                    raise ConflictError(
                        f"expected_version={expected_version} but event is new"
                    )
                new_version = 1

            received_at = _now_utc().isoformat()
            cur.execute(
                """
                INSERT OR REPLACE INTO source_events(
                    id, version, project_id, agent_id, occurred_at, client_digest,
                    action, result, origin, classification,
                    payload_digest, principal_actor, principal_workspace,
                    principal_project, received_at, source_refs
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    new_version,
                    project_id,
                    agent_id,
                    _coerce_dt(occurred_at).isoformat(),
                    client_digest or "",
                    action,
                    result,
                    origin,
                    classification,
                    payload_digest,
                    principal.actor,
                    principal.workspace,
                    principal.project,
                    received_at,
                    _serialise(ref_payload),
                ),
            )
            return {
                "status": "recorded",
                "id": event_id,
                "version": new_version,
                "digest": payload_digest,
                "received_at": received_at,
            }

    def list_events(self) -> list[dict[str, Any]]:
        principal = self._resolve_principal()
        cur = self._conn.execute(
            """
            SELECT id, version, project_id, agent_id, occurred_at, client_digest, action,
                   result, origin, classification, payload_digest,
                   principal_actor, principal_workspace, principal_project,
                   received_at, source_refs
            FROM source_events
            WHERE principal_workspace = ? AND principal_project = ?
            ORDER BY received_at ASC, id ASC, version ASC
            """,
            (principal.workspace, principal.project),
        )
        return [self._row_to_event(row) for row in cur.fetchall()]

    def get_event(self, event_id: str, *, version: int = 1) -> dict[str, Any]:
        principal = self._resolve_principal()
        cur = self._conn.execute(
            """
            SELECT id, version, project_id, agent_id, occurred_at, client_digest, action,
                   result, origin, classification, payload_digest,
                   principal_actor, principal_workspace, principal_project,
                   received_at, source_refs
            FROM source_events
            WHERE id = ? AND version = ?
              AND principal_workspace = ? AND principal_project = ?
            """,
            (event_id, version, principal.workspace, principal.project),
        )
        row = cur.fetchone()
        if row is None:
            raise NotFoundError(f"event {event_id}@{version} not found")
        return self._row_to_event(row)

    def _row_to_event(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "version": row["version"],
            "project_id": row["project_id"],
            "agent_id": row["agent_id"],
            "occurred_at": row["occurred_at"],
            "client_digest": row["client_digest"],
            "action": row["action"],
            "result": row["result"],
            "origin": row["origin"],
            "classification": row["classification"],
            "payload_digest": row["payload_digest"],
            "principal_actor": row["principal_actor"],
            "principal_workspace": row["principal_workspace"],
            "principal_project": row["principal_project"],
            "received_at": row["received_at"],
            "source_refs": _deserialise(row["source_refs"]) or [],
        }

    # -- documents -----------------------------------------------------------

    def register_source_document(
        self,
        *,
        doc_id: Any,
        url: str,
        version: int,
        excerpt: str = "",
        bytes_digest: str = "",
    ) -> dict[str, Any]:
        principal = self._resolve_principal()
        doc_uuid = _coerce_uuid(doc_id)
        self._enforce_body_limit({"excerpt": excerpt, "url": url, "bytes_digest": bytes_digest})
        self._enforce_privacy({"excerpt": excerpt, "url": url})
        with self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            existing = self._conn.execute(
                "SELECT * FROM source_documents WHERE id=? AND version=?", (str(doc_uuid), version)
            ).fetchone()
            if existing is not None:
                if (existing["principal_workspace"], existing["principal_project"]) != (principal.workspace, principal.project):
                    raise UnauthorizedError("document scope mismatch")
                if (existing["url"], existing["excerpt"], existing["bytes_digest"]) != (url, excerpt, bytes_digest):
                    raise ConflictError("immutable document revision conflict")
                return {"status": "registered"}
            self._conn.execute(
                """
                INSERT INTO source_documents(
                    id, version, url, excerpt, bytes_digest, registered_at,
                    principal_actor, principal_workspace, principal_project
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(doc_uuid),
                    version,
                    url,
                    excerpt,
                    bytes_digest,
                    _now_utc().isoformat(),
                    principal.actor,
                    principal.workspace,
                    principal.project,
                ),
            )
        return {"status": "registered"}

    def _resolve_source_refs(
        self,
        refs: list[dict[str, Any]],
        *,
        principal: Principal,
    ) -> None:
        if not refs:
            return
        for ref in refs:
            ref_type = ref.get("type")
            ref_id = ref.get("id")
            if ref_type == "document":
                row = self._conn.execute(
                    """
                    SELECT 1 FROM source_documents
                    WHERE id = ?
                      AND principal_workspace = ?
                      AND principal_project = ?
                    """,
                    (str(ref_id), principal.workspace, principal.project),
                ).fetchone()
                if row is None:
                    raise ReferenceUnavailableError(
                        f"document {ref_id} not registered in this scope"
                    )
            elif ref_type == "execution":
                # Execution refs are resolved lazily — they must already
                # exist as events in the same scope.  The storage layer
                # never fetches URLs.
                row = self._conn.execute(
                    """
                    SELECT 1 FROM source_events
                    WHERE id = ?
                      AND principal_workspace = ?
                      AND principal_project = ?
                    """,
                    (str(ref_id), principal.workspace, principal.project),
                ).fetchone()
                if row is None:
                    raise ReferenceUnavailableError(
                        f"execution event {ref_id} not registered"
                    )
            else:
                raise ReferenceUnavailableError(f"unknown source ref type: {ref_type!r}")

    # -- proposals -----------------------------------------------------------

    def create_proposal(
        self,
        *,
        id: Any,
        version: int = 1,
        project_id: str | None = None,
        agent_id: str,
        occurred_at: datetime | None = None,
        action: str | None = None,
        result: str | None = None,
        lesson: str | None = None,
        draft: bool = False,
        source_refs: Iterable[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        principal = self._resolve_principal()
        self._enforce_scope(principal, project_id=project_id)

        source_refs_list = list(source_refs or [])
        ref_payload = [
            {"type": str(ref.get("type")), "id": str(ref.get("id"))}
            for ref in source_refs_list
        ]
        # ``occurred_at`` is optional. The router forwards whatever the
        # caller supplied (including ``None``); the storage layer never
        # substitutes a server clock for an absent event date.
        occurred_dt = _coerce_dt(occurred_at) if occurred_at is not None else None
        body = {
            "project_id": project_id,
            "agent_id": agent_id,
            "occurred_at": occurred_dt,
            "action": action,
            "result": result,
            "lesson": lesson,
            "draft": draft,
            "source_refs": ref_payload,
        }
        self._enforce_body_limit(body)
        self._enforce_privacy(body)

        # Server-owned workflow state: a draft stays draft until a separate
        # review operation promotes it.  The wire ``draft`` flag is
        # informational only; the storage layer enforces readiness.
        workflow_state = "draft" if draft else "ready"

        # Cross-workspace proposal creation is implicitly blocked by the
        # source_refs resolution below (refs must live in this scope).

        proposal_uuid = _coerce_uuid(id)
        proposal_id = str(proposal_uuid)
        self._resolve_source_refs(ref_payload, principal=principal)

        digest = canonical_proposal_digest(body)

        # create_proposal must respect the explicit ``version`` the caller
        # passes.  If a revision at exactly that (id, version) already
        # exists:
        #   * same payload  -> idempotent duplicate
        #   * different payload -> ConflictError (no implicit auto-increment)
        # If the id exists at a different version, that is also a
        # Conflict — new revisions are produced by update_proposal with a
        # CAS expected_version, never by re-creating at a different
        # version on the same id.
        with self._conn:
            existing = self._conn.execute(
                """
                SELECT version, payload_digest FROM proposal_revisions
                WHERE id = ?
                """,
                (proposal_id,),
            ).fetchall()
            if existing:
                versions = sorted(row["version"] for row in existing)
                if version != versions[-1]:
                    # Caller is asking for a version that does not match
                    # the current latest — either they need to use
                    # update_proposal with CAS, or this is an attempt to
                    # create a stale/duplicate revision.
                    if version in versions:
                        # The same version already exists for this id.  The
                        # idempotency check below decides duplicate vs
                        # conflict on that specific row.
                        pass
                    else:
                        # Requested version is neither the latest nor a
                        # known one.  Reject: use update_proposal.
                        raise ConflictError(
                            f"create_proposal version={version} but latest "
                            f"is {versions[-1]}; use update_proposal"
                        )
                target = self._conn.execute(
                    """
                    SELECT payload_digest FROM proposal_revisions
                    WHERE id = ? AND version = ?
                    """,
                    (proposal_id, version),
                ).fetchone()
                if target is not None:
                    if target["payload_digest"] == digest:
                        return {
                            "status": "duplicate",
                            "version": version,
                            "digest": digest,
                            "workflow_state": workflow_state,
                        }
                    raise ConflictError(
                        f"proposal {proposal_id}@{version} exists with a "
                        f"different payload digest"
                    )
                new_version = version
            else:
                if version != 1:
                    raise ConflictError(
                        f"create_proposal version={version} but id is new"
                    )
                new_version = 1

            received_at = _now_utc().isoformat()
            self._conn.execute(
                """
                INSERT OR REPLACE INTO proposal_revisions(
                    id, version, project_id, agent_id, occurred_at,
                    action, result, lesson, draft, source_refs,
                    workflow_state, payload_digest, principal_actor,
                    principal_workspace, principal_project, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    new_version,
                    project_id,
                    agent_id,
                    occurred_dt.isoformat() if occurred_dt is not None else None,
                    action,
                    result,
                    lesson,
                    1 if draft else 0,
                    _serialise(ref_payload),
                    workflow_state,
                    digest,
                    principal.actor,
                    principal.workspace,
                    principal.project,
                    received_at,
                ),
            )
            self._conn.execute(
                """
                INSERT OR REPLACE INTO proposal_current(
                    id, version, digest, workflow_state, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (proposal_id, new_version, digest, workflow_state, received_at),
            )
        return {
            "status": "created",
            "version": new_version,
            "digest": digest,
            "workflow_state": workflow_state,
        }

    def update_proposal(
        self,
        *,
        proposal_id: str,
        expected_version: int,
        lesson: str | None = None,
    ) -> dict[str, Any]:
        principal = self._resolve_principal()
        # CAS compares against the CURRENT pointer, not any historical
        # revision row. proposal_current is the authoritative "latest"
        # record; the revisions table holds every snapshot.  Reading the
        # historical row would let a stale expected_version (one that
        # matches an older snapshot) slip through.
        cur = self._conn.execute(
            """
            SELECT pc.version, pc.workflow_state,
                   pr.id, pr.project_id, pr.agent_id, pr.occurred_at,
                   pr.action, pr.result, pr.lesson, pr.draft,
                   pr.source_refs, pr.payload_digest,
                   pr.principal_actor, pr.principal_workspace,
                   pr.principal_project, pr.received_at
            FROM proposal_current pc
            JOIN proposal_revisions pr
              ON pr.id = pc.id AND pr.version = pc.version
            WHERE pc.id = ?
              AND pr.principal_workspace = ? AND pr.principal_project = ?
            """,
            (proposal_id, principal.workspace, principal.project),
        )
        row = cur.fetchone()
        if row is None:
            raise NotFoundError(f"proposal {proposal_id} not found")
        # CAS: the caller's expected_version must equal the CURRENT version.
        if expected_version != row["version"]:
            raise ConflictError(
                f"expected_version={expected_version} does not match current revision"
            )

        # Lifecycle (draft -> ready) is a separate, server-owned flow.
        # update_proposal only enriches the existing draft revision; it
        # MUST NOT promote workflow_state to ready.  Lifecycle transitions
        # go through a dedicated review / publish endpoint (not exposed
        # by this method).

        body = {
            "project_id": row["project_id"],
            "agent_id": row["agent_id"],
            "occurred_at": _coerce_dt(row["occurred_at"]) if row["occurred_at"] is not None else None,
            "action": row["action"],
            "result": row["result"],
            "lesson": lesson,
            "draft": bool(row["draft"]),
            "source_refs": _deserialise(row["source_refs"]) or [],
        }
        self._enforce_body_limit(body)
        self._enforce_privacy(body)

        new_digest = canonical_proposal_digest(body)
        if new_digest == row["payload_digest"]:
            return {
                "status": "no_change",
                "version": row["version"],
                "digest": new_digest,
                "workflow_state": row["workflow_state"],
            }

        new_version = row["version"] + 1
        received_at = _now_utc().isoformat()
        with self._conn:
            # Lock and atomically fence the pointer before inserting history.
            # A concurrent writer cannot replace the same immutable revision.
            self._conn.execute("BEGIN IMMEDIATE")
            changed = self._conn.execute(
                "UPDATE proposal_current SET version=?, digest=?, updated_at=? WHERE id=? AND version=?",
                (new_version, new_digest, received_at, proposal_id, expected_version),
            )
            if changed.rowcount != 1:
                raise ConflictError("expected version changed concurrently")
            self._conn.execute(
                """
                INSERT INTO proposal_revisions(
                    id, version, project_id, agent_id, occurred_at,
                    action, result, lesson, draft, source_refs,
                    workflow_state, payload_digest, principal_actor,
                    principal_workspace, principal_project, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    new_version,
                    row["project_id"],
                    row["agent_id"],
                    row["occurred_at"],
                    row["action"],
                    row["result"],
                    lesson,
                    row["draft"],
                    row["source_refs"],
                    row["workflow_state"],
                    new_digest,
                    row["principal_actor"],
                    row["principal_workspace"],
                    row["principal_project"],
                    received_at,
                ),
            )

        return {
            "status": "updated",
            "version": new_version,
            "digest": new_digest,
            "workflow_state": row["workflow_state"],
        }

    def get_current_proposal(self, proposal_id: str) -> dict[str, Any]:
        principal = self._resolve_principal()
        cur = self._conn.execute(
            """
            SELECT pc.id, pc.version, pc.digest, pc.workflow_state,
                   pc.updated_at, pr.project_id, pr.agent_id, pr.occurred_at,
                   pr.action, pr.result, pr.lesson, pr.draft, pr.source_refs
            FROM proposal_current pc
            JOIN proposal_revisions pr
              ON pr.id = pc.id AND pr.version = pc.version
            WHERE pc.id = ?
              AND pr.principal_workspace = ?
              AND pr.principal_project = ?
            """,
            (proposal_id, principal.workspace, principal.project),
        )
        row = cur.fetchone()
        if row is None:
            # Use a single error class for both "absent" and "out of scope"
            # so the API does not leak which proposal IDs exist in other
            # workspaces (avoid enumeration).  Clients that want to
            # distinguish should rely on the wire-level response code, not
            # on different exception classes.
            raise NotFoundError(f"proposal {proposal_id} not found")
        return {
            "id": row["id"],
            "version": row["version"],
            "digest": row["digest"],
            "workflow_state": row["workflow_state"],
            "updated_at": row["updated_at"],
            "project_id": row["project_id"],
            "agent_id": row["agent_id"],
            "occurred_at": row["occurred_at"],
            "action": row["action"],
            "result": row["result"],
            "lesson": row["lesson"],
            "draft": bool(row["draft"]),
            "source_refs": _deserialise(row["source_refs"]) or [],
        }

    # -- check runs ----------------------------------------------------------

    def record_check_run(
        self,
        *,
        proposal_id: str,
        proposal_version: int,
        kind: str,
        status: str,
        detail: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        principal = self._resolve_principal()
        # A check run references a known proposal in this scope.
        row = self._conn.execute(
            """
            SELECT 1 FROM proposal_revisions
            WHERE id = ? AND version = ?
              AND principal_workspace = ? AND principal_project = ?
            """,
            (proposal_id, proposal_version, principal.workspace, principal.project),
        ).fetchone()
        if row is None:
            raise NotFoundError(
                f"proposal {proposal_id}@{proposal_version} not found in scope"
            )
        run_id = str(uuid.uuid4())
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO check_runs(
                    id, proposal_id, proposal_version, kind, status,
                    detail, recorded_at, principal_actor,
                    principal_workspace, principal_project
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    proposal_id,
                    proposal_version,
                    kind,
                    status,
                    _serialise(dict(detail or {})),
                    _now_utc().isoformat(),
                    principal.actor,
                    principal.workspace,
                    principal.project,
                ),
            )
        return {
            "id": run_id,
            "status": status,
            "kind": kind,
            "proposal_id": proposal_id,
            "proposal_version": proposal_version,
        }

    def list_check_runs(self, *, proposal_id: str) -> list[dict[str, Any]]:
        principal = self._resolve_principal()
        cur = self._conn.execute(
            """
            SELECT id, proposal_id, proposal_version, kind, status,
                   detail, recorded_at, principal_actor,
                   principal_workspace, principal_project
            FROM check_runs
            WHERE proposal_id = ?
              AND principal_workspace = ? AND principal_project = ?
            ORDER BY recorded_at ASC
            """,
            (proposal_id, principal.workspace, principal.project),
        )
        return [
            {
                "id": row["id"],
                "proposal_id": row["proposal_id"],
                "proposal_version": row["proposal_version"],
                "kind": row["kind"],
                "status": row["status"],
                "detail": _deserialise(row["detail"]) or {},
                "recorded_at": row["recorded_at"],
            }
            for row in cur.fetchall()
        ]

    # -- durable jobs --------------------------------------------------------

    def enqueue_durable_job(self, *, kind: str, payload: Mapping[str, Any]) -> str:
        principal = self._resolve_principal()
        body = {"kind": kind, "payload": dict(payload)}
        self._enforce_body_limit(body)
        self._enforce_privacy(body)
        job_id = str(uuid.uuid4())
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO durable_jobs(
                    id, kind, payload, state, enqueued_at,
                    principal_actor, principal_workspace, principal_project
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    kind,
                    _serialise(dict(payload)),
                    "queued",
                    _now_utc().isoformat(),
                    principal.actor,
                    principal.workspace,
                    principal.project,
                ),
            )
        return job_id

    def list_durable_jobs(self, *, kind: str | None = None) -> list[dict[str, Any]]:
        principal = self._resolve_principal()
        if kind is None:
            cur = self._conn.execute(
                """
                SELECT id, kind, payload, state, enqueued_at
                FROM durable_jobs
                WHERE principal_workspace = ? AND principal_project = ?
                ORDER BY enqueued_at ASC
                """,
                (principal.workspace, principal.project),
            )
        else:
            cur = self._conn.execute(
                """
                SELECT id, kind, payload, state, enqueued_at
                FROM durable_jobs
                WHERE kind = ?
                  AND principal_workspace = ? AND principal_project = ?
                ORDER BY enqueued_at ASC
                """,
                (kind, principal.workspace, principal.project),
            )
        return [
            {
                "id": row["id"],
                "kind": row["kind"],
                "payload": _deserialise(row["payload"]) or {},
                "state": row["state"],
                "enqueued_at": row["enqueued_at"],
            }
            for row in cur.fetchall()
        ]

    # -- outbox --------------------------------------------------------------

    def record_outbox_event(
        self,
        *,
        kind: str,
        reference_id: str,
        payload: Mapping[str, Any],
    ) -> str:
        principal = self._resolve_principal()
        body = {"kind": kind, "reference_id": reference_id, "payload": dict(payload)}
        self._enforce_body_limit(body)
        self._enforce_privacy(body)
        out_id = str(uuid.uuid4())
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO outbox_events(
                    id, kind, reference_id, payload, recorded_at,
                    principal_actor, principal_workspace, principal_project
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    out_id,
                    kind,
                    reference_id,
                    _serialise(dict(payload)),
                    _now_utc().isoformat(),
                    principal.actor,
                    principal.workspace,
                    principal.project,
                ),
            )
        return out_id

    def list_outbox_events(self, *, kind: str | None = None) -> list[dict[str, Any]]:
        principal = self._resolve_principal()
        if kind is None:
            cur = self._conn.execute(
                """
                SELECT id, kind, reference_id, payload, recorded_at
                FROM outbox_events
                WHERE principal_workspace = ? AND principal_project = ?
                ORDER BY recorded_at ASC
                """,
                (principal.workspace, principal.project),
            )
        else:
            cur = self._conn.execute(
                """
                SELECT id, kind, reference_id, payload, recorded_at
                FROM outbox_events
                WHERE kind = ?
                  AND principal_workspace = ? AND principal_project = ?
                ORDER BY recorded_at ASC
                """,
                (kind, principal.workspace, principal.project),
            )
        return [
            {
                "id": row["id"],
                "kind": row["kind"],
                "reference_id": row["reference_id"],
                "payload": _deserialise(row["payload"]) or {},
                "recorded_at": row["recorded_at"],
            }
            for row in cur.fetchall()
        ]

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass

    def __enter__(self) -> "EventStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


__all__ = [
    "EventStore",
    "EventStoreError",
    "ConflictError",
    "NotFoundError",
    "ReferenceUnavailableError",
    "UnauthorizedError",
    "BodyTooLargeError",
    "SensitiveRejectedError",
    "StaticPrincipalAdapter",
    "Principal",
    "MAX_BODY_BYTES",
    "SCHEMA_VERSION",
    "canonical_proposal_digest",
]
