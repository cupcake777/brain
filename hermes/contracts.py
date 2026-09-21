"""Strict v2 Brain contracts.

This module is the single source of truth for the v2 Brain protocol objects.
It deliberately exposes:

* Pydantic 2.x ``BaseModel`` subclasses configured with ``extra=forbid``,
  ``strict=True`` and explicit maxima, so inputs are deterministic.
* Timezone-aware ``datetime`` values normalised to UTC.
* UUID4 identifiers only — no version coercion.
* Typed ``SourceRef`` unions resolving only to authorised registered objects.
* Separated server-owned metadata (origin, classification, principal,
  workflow, created_at) that clients cannot submit.
* A distinct ``KnowledgeDirectiveInput`` model so explicit-authority
  directives are never reduced to an agent-supplied boolean.
* Deterministic ``canonical_json`` / ``canonical_digest`` helpers suitable
  for required-check digests.

Public contracts exported by :mod:`hermes.contracts`:

* :class:`ExecutionEvent` — immutable capture contract for hooks/wrappers.
* :class:`ProposalRevision` — versioned submission contract.
* :class:`SourceRef`, :class:`SourceDocument`, :class:`SourceRefType`,
  :class:`ProposalSourceRef` — evidence link primitives.
* :class:`KnowledgeRevision`, :class:`KnowledgeRevisionLink`,
  :class:`KnowledgeScope`, :class:`KnowledgeKind`,
  :class:`KnowledgeLifecycleState`, :class:`KnowledgeSourceRef` —
  curated revision contracts.
* :class:`KnowledgeDirectiveInput`, :class:`KnowledgeDirectiveSource` —
  authenticated explicit-authority input.
* :func:`canonical_json`, :func:`canonical_digest`, :class:`CanonicalDigestError`.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)


# ---------------------------------------------------------------------------
# Constants and enums
# ---------------------------------------------------------------------------


# Project identifiers are short, portable and never arbitrary text.
DEFAULT_MAX_PROJECT_ID_LEN = 64
DEFAULT_MAX_TARGET_ID_LEN = 128
DEFAULT_MAX_AGENT_ID_LEN = 128
DEFAULT_MAX_OWNER_ID_LEN = 128
DEFAULT_MAX_WORKSPACE_ID_LEN = 128
DEFAULT_MAX_URL_LEN = 2048

# Action/result/lesson bodies are bounded so they remain reviewable.
DEFAULT_MAX_ACTION_CHARS = 8_000
DEFAULT_MIN_ACTION_CHARS = 1
DEFAULT_MAX_RESULT_CHARS = 16_000
DEFAULT_MIN_RESULT_CHARS = 1
DEFAULT_MAX_LESSON_CHARS = 8_000
DEFAULT_MIN_LESSON_CHARS = 1
DEFAULT_MAX_NOTE_CHARS = 4_000
DEFAULT_MAX_REASON_CHARS = 4_000

DEFAULT_MAX_VERSION_INT = 1_000_000
DEFAULT_MIN_REVISION_VERSION = 1

DEFAULT_MAX_EVIDENCE_BYTES = 32_000
DEFAULT_MAX_DOCUMENT_EXCERPT = 8_000

# Lifecycle / scope / kind / origin / classification surfaces.
EXECUTION_EVENT_ORIGINS: tuple[str, ...] = ("hook", "wrapper", "manual", "system")
EXECUTION_EVENT_CLASSIFICATIONS: tuple[str, ...] = ("production", "probe", "evaluation")
KNOWLEDGE_SCOPES: tuple[str, ...] = ("owner", "workspace", "project")
KNOWLEDGE_KINDS: tuple[str, ...] = ("directive", "experience")
KNOWLEDGE_LIFECYCLE_STATES: tuple[str, ...] = (
    "candidate",
    "formal",
    "disputed",
    "archive",
    "deprecated",
)


class ExecutionEventOrigin(str, Enum):
    HOOK = "hook"
    WRAPPER = "wrapper"
    MANUAL = "manual"
    SYSTEM = "system"


class ExecutionEventClassification(str, Enum):
    PRODUCTION = "production"
    PROBE = "probe"
    EVALUATION = "evaluation"


class ProposalWorkflow(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    REJECTED = "rejected"


class ProposalStatus(str, Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class SourceRefType(str, Enum):
    EXECUTION = "execution"
    DOCUMENT = "document"


class KnowledgeScope(str, Enum):
    OWNER = "owner"
    WORKSPACE = "workspace"
    PROJECT = "project"


class KnowledgeKind(str, Enum):
    DIRECTIVE = "directive"
    EXPERIENCE = "experience"


class KnowledgeLifecycleState(str, Enum):
    CANDIDATE = "candidate"
    FORMAL = "formal"
    DISPUTED = "disputed"
    ARCHIVE = "archive"
    DEPRECATED = "deprecated"


class KnowledgeRevisionLinkKind(str, Enum):
    PARENT = "parent"
    DERIVED = "derived"
    SPLIT = "split"
    MERGE = "merge"
    REPLACES = "replaces"


class KnowledgeDirectiveSource(str, Enum):
    """Authenticated source of an explicit directive.

    Agents cannot self-declare user authority; the only valid recorded
    source for a directive is a verified authenticated human interaction.
    """

    HUMAN_AUTHENTICATED = "human_authenticated"
    AGENT_INFERENCE = "agent_inference"  # rejected at validation time below


# ---------------------------------------------------------------------------
# Strict type helpers
# ---------------------------------------------------------------------------


_UUID4 = Annotated[UUID, Field(description="UUIDv4 identifier.")]


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError(f"UUID version 4 required; got version {value.version}")
    return value


_NON_BLANK = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _reject_whitespace_only(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be whitespace-only")
    return value


def _ensure_utc(value: datetime) -> datetime:
    """Coerce naive datetimes to UTC-aware values without silent coercion."""

    if value.tzinfo is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Base configuration
# ---------------------------------------------------------------------------


class _StrictModel(BaseModel):
    """Base config: no extras, frozen after validation.

    Per-field ``strict=True`` is used where literal-type discipline is
    required (booleans must remain booleans).  UUID/enum/datetime fields
    accept JSON wire-format strings (the standard Pydantic behaviour) and
    reject non-conforming values via field validators.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )


# ---------------------------------------------------------------------------
# Source references
# ---------------------------------------------------------------------------


class SourceRef(_StrictModel):
    """Tagged union of evidence references.

    Execution events and proposals reference source evidence via a typed
    tag (``execution`` or ``document``).  The ``document`` variant carries
    the registered document payload; the ``execution`` variant only carries
    the identifier — the server resolves it.
    """

    type: SourceRefType
    id: _UUID4

    @field_validator("id")
    @classmethod
    def _id_v4(cls, value: UUID) -> UUID:
        return _require_uuid4(value)


class ProposalSourceRef(_StrictModel):
    """Proposal-side mirror of :class:`SourceRef`.

    Kept separate so proposal rules (e.g. requiring at least one resolvable
    source on a ready proposal) live in their own module without altering
    the execution event contract.
    """

    type: SourceRefType
    id: _UUID4

    @field_validator("id")
    @classmethod
    def _id_v4(cls, value: UUID) -> UUID:
        return _require_uuid4(value)


class SourceDocument(_StrictModel):
    """Registered external document payload for a :class:`SourceRef`."""

    id: _UUID4
    url: Annotated[str, StringConstraints(max_length=DEFAULT_MAX_URL_LEN)]
    version: Annotated[int, Field(strict=True, ge=1, le=DEFAULT_MAX_VERSION_INT)]
    excerpt: Annotated[str, StringConstraints(max_length=DEFAULT_MAX_DOCUMENT_EXCERPT)] = ""

    @field_validator("id")
    @classmethod
    def _id_v4(cls, value: UUID) -> UUID:
        return _require_uuid4(value)

    @field_validator("url")
    @classmethod
    def _url_safe(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme.lower() == "file":
            raise ValueError("file:// URLs are not portable proof")
        if parsed.scheme not in {"http", "https", "ftp", "ftps"}:
            raise ValueError(f"unsupported URL scheme: {parsed.scheme!r}")
        return value


class KnowledgeSourceRef(_StrictModel):
    """Knowledge-side source reference (alias for :class:`SourceRef`)."""

    type: SourceRefType
    id: _UUID4

    @field_validator("id")
    @classmethod
    def _id_v4(cls, value: UUID) -> UUID:
        return _require_uuid4(value)


# ---------------------------------------------------------------------------
# ExecutionEvent
# ---------------------------------------------------------------------------


class ExecutionEvent(_StrictModel):
    """Immutable capture of one tool/completion event.

    Capture-time fields: ``id``, ``project_id``, ``agent_id``, ``occurred_at``,
    ``target_id``, ``action``, ``result``, ``source_refs``.

    Trusted provenance fields: ``classification`` (``production``, ``probe``,
    ``evaluation``) and ``origin`` (``hook``, ``wrapper``, ``manual``,
    ``system``).  These are server-owned classification metadata; clients
    may submit them when the capture pipeline has already classified the
    event, but they cannot silently promote events to ``production``.

    Server-owned, never accepted on input:

    * ``principal`` — the authenticated identity is recorded server-side.
    * ``principal_kind`` — distinct from claimed ``agent_id``.
    """

    id: _UUID4
    project_id: (
        Annotated[str, StringConstraints(max_length=DEFAULT_MAX_PROJECT_ID_LEN)] | None
    ) = None
    agent_id: Annotated[str, StringConstraints(max_length=DEFAULT_MAX_AGENT_ID_LEN)]
    occurred_at: datetime
    target_id: (
        Annotated[str, StringConstraints(max_length=DEFAULT_MAX_TARGET_ID_LEN)] | None
    ) = None
    action: (
        Annotated[str, StringConstraints(max_length=DEFAULT_MAX_ACTION_CHARS)] | None
    ) = None
    result: (
        Annotated[str, StringConstraints(max_length=DEFAULT_MAX_RESULT_CHARS)] | None
    ) = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    origin: ExecutionEventOrigin
    classification: ExecutionEventClassification

    @field_validator("id")
    @classmethod
    def _id_v4(cls, value: UUID) -> UUID:
        return _require_uuid4(value)

    @field_validator("occurred_at")
    @classmethod
    def _occurred_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value)

    @field_validator("action", "result")
    @classmethod
    def _no_ws(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("must not be whitespace-only")
        return value

    @field_validator("source_refs")
    @classmethod
    def _refs_nonempty_types(cls, value: list[SourceRef]) -> list[SourceRef]:
        # SourceRef itself enforces the type/tag discipline; the list
        # assertion is a belt-and-braces sanity check for client misuse.
        for ref in value:
            if not isinstance(ref, SourceRef):
                raise ValueError("source refs must be SourceRef instances")
        return value

    def model_post_init(self, __context: Any) -> None:
        if self.classification is ExecutionEventClassification.PRODUCTION:
            target = self.target_id
            action = self.action or ""
            looks_like_env_op = bool(
                re.search(r"\b(ssh|systemctl|rm|docker|kubectl|terraform)\b", action)
            )
            if looks_like_env_op and not target:
                raise ValueError(
                    "trusted production environment operation requires target_id"
                )


# ---------------------------------------------------------------------------
# ProposalRevision
# ---------------------------------------------------------------------------


class ProposalRevision(_StrictModel):
    """One versioned revision of a proposal.

    Clients submit ``id``, ``version`` and the writable fact fields.
    Server-owned metadata (``workflow``, ``status``, ``created_at``,
    ``received_at``, ``policy_version``, ``checks``) is rejected if supplied
    on input.
    """

    id: _UUID4
    version: Annotated[int, Field(strict=True, ge=1, le=DEFAULT_MAX_VERSION_INT)]
    project_id: (
        Annotated[str, StringConstraints(max_length=DEFAULT_MAX_PROJECT_ID_LEN)] | None
    ) = None
    agent_id: Annotated[str, StringConstraints(max_length=DEFAULT_MAX_AGENT_ID_LEN)]
    occurred_at: datetime | None = None
    target_id: (
        Annotated[str, StringConstraints(max_length=DEFAULT_MAX_TARGET_ID_LEN)] | None
    ) = None
    action: (
        Annotated[str, StringConstraints(max_length=DEFAULT_MAX_ACTION_CHARS)] | None
    ) = None
    result: (
        Annotated[str, StringConstraints(max_length=DEFAULT_MAX_RESULT_CHARS)] | None
    ) = None
    lesson: (
        Annotated[str, StringConstraints(max_length=DEFAULT_MAX_LESSON_CHARS)] | None
    ) = None
    draft: Annotated[bool, Field(strict=True)] = True
    source_refs: list[ProposalSourceRef] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_v4(cls, value: UUID) -> UUID:
        return _require_uuid4(value)

    @field_validator("occurred_at")
    @classmethod
    def _occurred_utc(cls, value: datetime | None) -> datetime | None:
        return _ensure_utc(value) if value is not None else None

    @field_validator("action", "result", "lesson")
    @classmethod
    def _no_ws(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("must not be whitespace-only")
        return value

    def model_post_init(self, __context: Any) -> None:
        if self.draft:
            return
        # Ready proposals must carry the minimum evidence set.
        missing: list[str] = []
        # Spec: project_id is nullable until ready; required on ready.
        if not self.project_id or not self.project_id.strip():
            missing.append("project_id")
        if not self.action or len(self.action.strip()) < DEFAULT_MIN_ACTION_CHARS:
            missing.append("action")
        if not self.result or len(self.result.strip()) < DEFAULT_MIN_RESULT_CHARS:
            missing.append("result")
        if not self.lesson or len(self.lesson.strip()) < DEFAULT_MIN_LESSON_CHARS:
            missing.append("lesson")
        if not self.source_refs:
            missing.append("source_refs")
        if missing:
            raise ValueError(
                "ready proposal requires non-empty " + ", ".join(missing)
            )


def is_proposal_ready(proposal: ProposalRevision) -> bool:
    """Pure readiness check — no model rebuild required."""

    if proposal.draft:
        return False
    # Spec: project_id is required on ready (nullable until ready).
    if not proposal.project_id or not proposal.project_id.strip():
        return False
    if not proposal.action or len(proposal.action.strip()) < DEFAULT_MIN_ACTION_CHARS:
        return False
    if not proposal.result or len(proposal.result.strip()) < DEFAULT_MIN_RESULT_CHARS:
        return False
    if not proposal.lesson or len(proposal.lesson.strip()) < DEFAULT_MIN_LESSON_CHARS:
        return False
    return bool(proposal.source_refs)


# ---------------------------------------------------------------------------
# Knowledge revision
# ---------------------------------------------------------------------------


class KnowledgeRevisionLink(_StrictModel):
    """Typed edge between immutable knowledge revisions."""

    kind: KnowledgeRevisionLinkKind
    target_revision_id: _UUID4

    @field_validator("target_revision_id")
    @classmethod
    def _id_v4(cls, value: UUID) -> UUID:
        return _require_uuid4(value)


class KnowledgeRevision(_StrictModel):
    """Immutable revision of a curated knowledge item."""

    id: _UUID4  # stable identity across revisions
    revision_id: _UUID4  # unique per revision
    version: Annotated[int, Field(strict=True, ge=1, le=DEFAULT_MAX_VERSION_INT)]
    scope: KnowledgeScope
    owner: Annotated[str, StringConstraints(max_length=DEFAULT_MAX_OWNER_ID_LEN)]
    workspace: Annotated[str, StringConstraints(max_length=DEFAULT_MAX_WORKSPACE_ID_LEN)]
    project_id: (
        Annotated[str, StringConstraints(max_length=DEFAULT_MAX_PROJECT_ID_LEN)] | None
    ) = None
    kind: KnowledgeKind
    lifecycle: KnowledgeLifecycleState
    statement: Annotated[str, StringConstraints(min_length=1, max_length=8_000)]
    source_refs: list[KnowledgeSourceRef] = Field(default_factory=list)
    links: list[KnowledgeRevisionLink] = Field(default_factory=list)
    policy_version: Annotated[int, Field(strict=True, ge=1, le=DEFAULT_MAX_VERSION_INT)] = 1

    @field_validator("id", "revision_id")
    @classmethod
    def _id_v4(cls, value: UUID) -> UUID:
        return _require_uuid4(value)

    @field_validator("scope")
    @classmethod
    def _scope_project_requires_project(cls, value: KnowledgeScope, info: Any) -> KnowledgeScope:
        # Defer cross-field validation to model_post_init (Pydantic v2 limitation).
        return value

    def model_post_init(self, __context: Any) -> None:
        if self.scope is KnowledgeScope.PROJECT and not self.project_id:
            raise ValueError("scope=project requires project_id")
        if self.scope is not KnowledgeScope.PROJECT and self.project_id:
            raise ValueError("non-project scope must not carry project_id")


class KnowledgeDirectiveInput(_StrictModel):
    """Authenticated explicit-authority directive input.

    Distinct from :class:`KnowledgeRevision` so the user-authority lane
    cannot be invoked from agent-supplied booleans.
    """

    authority_command: Annotated[str, StringConstraints(min_length=1, max_length=2_000)]
    owner: Annotated[str, StringConstraints(max_length=DEFAULT_MAX_OWNER_ID_LEN)]
    workspace: Annotated[str, StringConstraints(max_length=DEFAULT_MAX_WORKSPACE_ID_LEN)]
    scope: KnowledgeScope
    project_id: (
        Annotated[str, StringConstraints(max_length=DEFAULT_MAX_PROJECT_ID_LEN)] | None
    ) = None
    source: KnowledgeDirectiveSource
    recorded_at: datetime
    reference_revision_ids: list[_UUID4] = Field(default_factory=list)
    note: Annotated[str, StringConstraints(max_length=DEFAULT_MAX_NOTE_CHARS)] = ""

    @field_validator("recorded_at")
    @classmethod
    def _occurred_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value)

    def model_post_init(self, __context: Any) -> None:
        if self.source is KnowledgeDirectiveSource.AGENT_INFERENCE:
            raise ValueError(
                "agents cannot self-declare user authority; only "
                "human_authenticated directives are accepted"
            )
        # An owner identifier that begins with 'agent-' is a structural
        # indicator that the caller is an agent, not an authenticated human.
        if self.owner.lower().startswith("agent-"):
            raise ValueError(
                "directive owner must be a human principal; agents cannot "
                "author explicit directives"
            )
        if self.scope is KnowledgeScope.PROJECT and not self.project_id:
            raise ValueError("scope=project requires project_id")


# ---------------------------------------------------------------------------
# Canonical JSON + digest helpers
# ---------------------------------------------------------------------------


class CanonicalDigestError(ValueError):
    """Raised when a payload cannot be canonicalised deterministically."""


def canonical_json(payload: Any) -> str:
    """Return a deterministic JSON encoding of *payload*.

    The encoding uses sorted keys, no whitespace, UTF-8 and rejects
    non-JSON-compatible values.  The same logical object always produces
    the same bytes regardless of input ordering.
    """

    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
            default=_json_default,
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalDigestError(str(exc)) from exc


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        # Always serialise in UTC ISO 8601.
        return _ensure_utc(value).isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise CanonicalDigestError(f"unsupported value for canonical JSON: {value!r}")


def canonical_digest(payload: Any) -> str:
    """Return the SHA-256 hex digest of :func:`canonical_json` applied to *payload*."""

    body = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


# ---------------------------------------------------------------------------
# Public API surface (re-exported for schema generation)
# ---------------------------------------------------------------------------


__all__ = [
    # constants
    "DEFAULT_MAX_ACTION_CHARS",
    "DEFAULT_MAX_AGENT_ID_LEN",
    "DEFAULT_MAX_DOCUMENT_EXCERPT",
    "DEFAULT_MAX_EVIDENCE_BYTES",
    "DEFAULT_MAX_LESSON_CHARS",
    "DEFAULT_MAX_NOTE_CHARS",
    "DEFAULT_MAX_OWNER_ID_LEN",
    "DEFAULT_MAX_PROJECT_ID_LEN",
    "DEFAULT_MAX_REASON_CHARS",
    "DEFAULT_MAX_RESULT_CHARS",
    "DEFAULT_MAX_TARGET_ID_LEN",
    "DEFAULT_MAX_URL_LEN",
    "DEFAULT_MAX_VERSION_INT",
    "DEFAULT_MAX_WORKSPACE_ID_LEN",
    "DEFAULT_MIN_ACTION_CHARS",
    "DEFAULT_MIN_LESSON_CHARS",
    "DEFAULT_MIN_RESULT_CHARS",
    "EXECUTION_EVENT_CLASSIFICATIONS",
    "EXECUTION_EVENT_ORIGINS",
    "KNOWLEDGE_KINDS",
    "KNOWLEDGE_LIFECYCLE_STATES",
    "KNOWLEDGE_SCOPES",
    # helpers
    "canonical_digest",
    "canonical_json",
    "CanonicalDigestError",
    "is_proposal_ready",
    # enums
    "ExecutionEventClassification",
    "ExecutionEventOrigin",
    "KnowledgeDirectiveSource",
    "KnowledgeKind",
    "KnowledgeLifecycleState",
    "KnowledgeScope",
    "ProposalStatus",
    "ProposalWorkflow",
    "SourceRefType",
    "KnowledgeRevisionLinkKind",
    # models
    "ExecutionEvent",
    "KnowledgeDirectiveInput",
    "KnowledgeRevision",
    "KnowledgeRevisionLink",
    "KnowledgeSourceRef",
    "ProposalRevision",
    "ProposalSourceRef",
    "SourceDocument",
    "SourceRef",
    # type aliases for documentation
    "Literal",
]