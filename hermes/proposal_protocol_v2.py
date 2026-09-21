"""Standalone v2 proposal / event API router.

Task 4 of the backend convergence plan. This module exposes a thin FastAPI
``APIRouter`` that delegates every read and write to the additive
:class:`hermes.event_store.EventStore` storage layer. It is intentionally
narrow:

* POST /api/v2/brain/events          -> record an ExecutionEvent
* GET  /api/v2/brain/events          -> list events in scope
* POST /api/v2/brain/proposals       -> create a ProposalRevision
* PUT  /api/v2/brain/proposals/{id}  -> CAS update (lesson only)
* GET  /api/v2/brain/proposals/{id}  -> current revision in scope

The router never touches the storage contract or repository modules
directly. The principal is supplied by an *injectable* trusted adapter
that maps a FastAPI :class:`fastapi.Request` to a
:class:`hermes.event_store.Principal` (actor, workspace, project). The
default adapter is fail-closed: when no adapter is configured (or the
adapter cannot resolve a principal) every endpoint returns ``503
principal unavailable`` — the router never trusts caller-supplied header
authority.

Server-owned metadata (``origin``, ``classification``, ``draft``,
``workflow_state``, ``principal``, ``received_at``, ``payload_digest``)
is always derived from the principal and the validated body; it is never
accepted from the request body. DTOs are strict Pydantic models that
use ``extra=forbid`` so callers cannot smuggle privileged fields.

Body size is enforced *before* Pydantic parses the payload — bodies
above the storage-layer limit are rejected with ``413 Payload Too
Large`` without ever reaching the contract layer.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Mapping, Protocol
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from starlette.status import HTTP_413_CONTENT_TOO_LARGE, HTTP_422_UNPROCESSABLE_CONTENT
from pydantic import BaseModel, ConfigDict, Field, ValidationError, StrictInt, StrictStr

from hermes.contracts import (
    ExecutionEvent,
    ProposalRevision,
    SourceRef,
    ProposalSourceRef,
)
from hermes.event_store import (
    MAX_BODY_BYTES,
    BodyTooLargeError,
    ConflictError,
    EventStore,
    NotFoundError,
    Principal,
    ReferenceUnavailableError,
    SensitiveRejectedError,
    UnauthorizedError,
)


# ---------------------------------------------------------------------------
# Principal adapter protocol
# ---------------------------------------------------------------------------


class PrincipalAdapter(Protocol):
    """Maps an HTTP request to an authenticated :class:`Principal`.

    The adapter is the *only* authority the router recognises. It is
    injected at construction time; the router itself never inspects
    headers, cookies or query strings to decide who the caller is.
    """

    def authenticate(self, request: Request) -> Principal | None: ...


class _DenyAllAdapter:
    """Default fail-closed adapter.

    Production must inject a session-aware adapter. Until then every
    request returns ``None`` and the router responds with 503.
    """

    def authenticate(self, request: Request) -> Principal | None:
        return None


DEFAULT_PRINCIPAL_ADAPTER: PrincipalAdapter = _DenyAllAdapter()


# ---------------------------------------------------------------------------
# Strict DTOs
# ---------------------------------------------------------------------------


class _StrictModel(BaseModel):
    """Wire DTO base — extra=forbid so privileged fields cannot leak in."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# Events --------------------------------------------------------------------


class _EventSourceRefIn(_StrictModel):
    type: StrictStr = Field(pattern=r"^(execution|document)$")
    id: UUID


class EventCreate(_StrictModel):
    """Inbound event payload.

    Server-owned fields (``origin``, ``classification``, ``principal_*``)
    are NOT accepted here. ``origin`` defaults to ``hook`` and
    ``classification`` defaults to ``production`` on the server side; the
    storage layer treats both as authoritative.
    """

    id: UUID
    project_id: StrictStr | None = None
    agent_id: StrictStr = Field(min_length=1, max_length=128)
    occurred_at: datetime
    target_id: StrictStr | None = None
    action: StrictStr | None = None
    result: StrictStr | None = None
    source_refs: list[_EventSourceRefIn] = Field(default_factory=list)
    client_digest: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class EventOut(_StrictModel):
    id: str
    version: int
    project_id: str | None
    agent_id: str
    occurred_at: str
    client_digest: str
    action: str | None
    result: str | None
    origin: str
    classification: str
    payload_digest: str
    principal_actor: str
    principal_workspace: str
    principal_project: str
    received_at: str
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


# Proposals ------------------------------------------------------------------


class _ProposalSourceRefIn(_StrictModel):
    type: StrictStr = Field(pattern=r"^(execution|document)$")
    id: UUID


class ProposalCreate(_StrictModel):
    """Inbound proposal payload.

    ``draft`` is informational only on input — the storage layer derives
    ``workflow_state`` server-side. ``expected_version`` is not part of
    create; use the CAS PUT endpoint to advance a revision.
    """

    id: UUID
    version: StrictInt = Field(ge=1, le=1_000_000, default=1)
    project_id: StrictStr | None = None
    agent_id: StrictStr = Field(min_length=1, max_length=128)
    occurred_at: datetime | None = None
    target_id: StrictStr | None = None
    action: StrictStr | None = None
    result: StrictStr | None = None
    lesson: StrictStr | None = None
    draft: bool = False
    source_refs: list[_ProposalSourceRefIn] = Field(default_factory=list)


class ProposalUpdate(_StrictModel):
    """CAS update — only ``lesson`` can change.

    The wire body MUST include ``expected_version`` so the storage layer
    can detect a stale update and reject it with 409.
    """

    expected_version: StrictInt = Field(ge=1, le=1_000_000)
    lesson: StrictStr | None = None


class ProposalOut(_StrictModel):
    id: str
    version: int
    digest: str
    workflow_state: str
    updated_at: str
    project_id: str | None
    agent_id: str
    occurred_at: str | None
    action: str | None
    result: str | None
    lesson: str | None
    draft: bool
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


class EventAck(BaseModel):
    """Acknowledgement for ``POST /events``.

    Includes the exact ``id`` / ``version`` / ``digest`` that the storage
    layer committed so clients can correlate without re-reading.
    """

    status: str
    id: str | None = None
    version: int | None = None
    digest: str | None = None
    received_at: str | None = None


class ProposalAck(BaseModel):
    status: str
    version: int
    digest: str
    workflow_state: str


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


StoreFactory = Callable[[Principal], EventStore]


def _validation_detail(exc: ValidationError) -> list[dict[str, Any]]:
    """Pydantic errors -> JSON-safe list (never raw exception)."""

    out: list[dict[str, Any]] = []
    for err in exc.errors():
        out.append(
            {
                "loc": list(err.get("loc", ())),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )
    return out


async def _bounded_json_async(request: Request) -> Mapping[str, Any]:
    """Async body reader used by every endpoint that takes a body."""

    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > MAX_BODY_BYTES:
                raise HTTPException(
                    status_code=HTTP_413_CONTENT_TOO_LARGE,
                    detail="payload exceeds MAX_BODY_BYTES",
                )
        except ValueError:
            pass
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(
            status_code=HTTP_413_CONTENT_TOO_LARGE,
            detail="payload exceeds MAX_BODY_BYTES",
        )
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid JSON: {exc.msg}",
        ) from exc


def build_router(
    *,
    store_factory: StoreFactory,
    principal_adapter: PrincipalAdapter = DEFAULT_PRINCIPAL_ADAPTER,
) -> APIRouter:
    """Build a router bound to ``store_factory() -> EventStore``.

    ``store_factory`` is invoked per request so the connection lifecycle
    is bounded by the request scope. The router is responsible for
    closing the store in a ``finally`` block — connection leaks are not
    acceptable even on error paths.
    """

    router = APIRouter(prefix="/api/v2/brain", tags=["v2-brain"])

    def _resolve_principal(request: Request) -> Principal:
        principal = principal_adapter.authenticate(request)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="principal unavailable",
            )
        return principal

    def _scope_check(principal: Principal, project_id: str | None) -> None:
        if project_id is not None and project_id != principal.project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="cross-project access rejected",
            )

    # -- events --------------------------------------------------------------

    @router.post("/events", response_model=EventAck)
    async def create_event(request: Request) -> EventAck:
        principal = _resolve_principal(request)
        payload = await _bounded_json_async(request)
        try:
            dto = EventCreate.model_validate(payload)
            contract = ExecutionEvent(
                id=dto.id,
                project_id=dto.project_id,
                agent_id=dto.agent_id,
                occurred_at=dto.occurred_at,
                target_id=dto.target_id,
                action=dto.action,
                result=dto.result,
                source_refs=[{"type": r.type, "id": r.id} for r in dto.source_refs],
                origin="hook",
                classification="production",
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE_CONTENT,
                detail=_validation_detail(exc),
            ) from exc
        _scope_check(principal, dto.project_id)
        store = store_factory(principal)
        try:
            result = store.record_event(
                id=contract.id,
                project_id=contract.project_id,
                agent_id=contract.agent_id,
                occurred_at=contract.occurred_at,
                action=contract.action,
                result=contract.result,
                source_refs=[{"type": r.type.value, "id": str(r.id)} for r in contract.source_refs],
                client_digest=dto.client_digest,
            )
            if result.get("id") != str(contract.id):
                raise ConflictError("event receipt id mismatch")
            if type(result.get("version")) is not int:
                raise ConflictError("event receipt version missing")
            if result.get("digest") is None:
                raise ConflictError("event receipt digest missing")
        except UnauthorizedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        except ReferenceUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except BodyTooLargeError as exc:
            raise HTTPException(
                status_code=HTTP_413_CONTENT_TOO_LARGE,
                detail=str(exc),
            ) from exc
        except SensitiveRejectedError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE_CONTENT,
                detail="payload rejected by privacy gate",
            ) from exc
        except ConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        finally:
            store.close()
        return EventAck(
            status=result["status"],
            id=result.get("id"),
            version=result.get("version"),
            digest=result.get("digest"),
            received_at=result.get("received_at"),
        )

    @router.get("/events", response_model=list[EventOut])
    def list_events(request: Request) -> list[EventOut]:
        principal = _resolve_principal(request)
        store = store_factory(principal)
        try:
            rows = store.list_events()
        except UnauthorizedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        finally:
            store.close()
        return [EventOut.model_validate(row) for row in rows]

    @router.get("/events/{event_id}", response_model=EventOut)
    def get_event(event_id: str, request: Request, version: int = 1) -> EventOut:
        principal = _resolve_principal(request)
        store = store_factory(principal)
        try:
            row = store.get_event(event_id, version=version)
        except NotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        finally:
            store.close()
        return EventOut.model_validate(row)

    @router.get("/events/{event_id}/ack")
    def get_event_ack(event_id: str, request: Request, version: int = 1) -> dict[str, Any]:
        principal = _resolve_principal(request)
        store = store_factory(principal)
        try:
            row = store.get_event(event_id, version=version)
        except NotFoundError:
            return {
                "status": "absent",
                "authorized": True,
                "id": event_id,
                "version": version,
                "digest": None,
            }
        finally:
            store.close()
        return {
            "status": "accepted",
            "authorized": True,
            "id": row["id"],
            "version": row["version"],
            "digest": (
                row["client_digest"]
                if row.get("client_digest")
                else row["payload_digest"]
                if row["payload_digest"]
                else None
            ),
        }

    # -- proposals ----------------------------------------------------------

    @router.post("/proposals", response_model=ProposalAck)
    async def create_proposal(request: Request) -> ProposalAck:
        principal = _resolve_principal(request)
        payload = await _bounded_json_async(request)
        try:
            dto = ProposalCreate.model_validate(payload)
            contract = ProposalRevision(
                id=dto.id,
                version=dto.version,
                project_id=dto.project_id,
                agent_id=dto.agent_id,
                occurred_at=dto.occurred_at,
                target_id=dto.target_id,
                action=dto.action,
                result=dto.result,
                lesson=dto.lesson,
                draft=dto.draft,
                source_refs=[{"type": r.type, "id": r.id} for r in dto.source_refs],
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE_CONTENT,
                detail=_validation_detail(exc),
            ) from exc
        _scope_check(principal, contract.project_id)
        store = store_factory(principal)
        try:
            result = store.create_proposal(
                id=contract.id,
                version=contract.version,
                project_id=contract.project_id,
                agent_id=contract.agent_id,
                occurred_at=contract.occurred_at,
                action=contract.action,
                result=contract.result,
                lesson=contract.lesson,
                draft=contract.draft,
                source_refs=[{"type": r.type.value, "id": str(r.id)} for r in contract.source_refs],
            )
        except UnauthorizedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        except ReferenceUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except BodyTooLargeError as exc:
            raise HTTPException(
                status_code=HTTP_413_CONTENT_TOO_LARGE,
                detail=str(exc),
            ) from exc
        except SensitiveRejectedError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE_CONTENT,
                detail="payload rejected by privacy gate",
            ) from exc
        except ConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        finally:
            store.close()
        return ProposalAck(
            status=result["status"],
            version=result["version"],
            digest=result["digest"],
            workflow_state=result["workflow_state"],
        )

    @router.put("/proposals/{proposal_id}", response_model=ProposalAck)
    async def update_proposal(proposal_id: str, request: Request) -> ProposalAck:
        principal = _resolve_principal(request)
        payload = await _bounded_json_async(request)
        try:
            dto = ProposalUpdate.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE_CONTENT,
                detail=_validation_detail(exc),
            ) from exc
        store = store_factory(principal)
        try:
            result = store.update_proposal(
                proposal_id=proposal_id,
                expected_version=dto.expected_version,
                lesson=dto.lesson,
            )
        except UnauthorizedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        except NotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except BodyTooLargeError as exc:
            raise HTTPException(
                status_code=HTTP_413_CONTENT_TOO_LARGE,
                detail=str(exc),
            ) from exc
        except SensitiveRejectedError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE_CONTENT,
                detail="payload rejected by privacy gate",
            ) from exc
        finally:
            store.close()
        return ProposalAck(
            status=result["status"],
            version=result["version"],
            digest=result["digest"],
            workflow_state=result["workflow_state"],
        )

    @router.get("/proposals/{proposal_id}", response_model=ProposalOut)
    def get_proposal(proposal_id: str, request: Request) -> ProposalOut:
        principal = _resolve_principal(request)
        store = store_factory(principal)
        try:
            row = store.get_current_proposal(proposal_id)
        except UnauthorizedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        except NotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        finally:
            store.close()
        return ProposalOut.model_validate(row)

    return router


__all__ = [
    "PrincipalAdapter",
    "DEFAULT_PRINCIPAL_ADAPTER",
    "build_router",
    "EventCreate",
    "EventOut",
    "ProposalCreate",
    "ProposalUpdate",
    "ProposalOut",
    "EventAck",
    "ProposalAck",
]