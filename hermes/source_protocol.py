"""Authenticated external-source protocol, deliberately separate from Brain outcomes."""
from __future__ import annotations
import hmac
import json
from typing import Literal
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError
from hermes.dify_sources import DifyAdapter, DifyConfig, DifyConfigError, DifyUpstreamError

class SourceRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query: StrictStr=Field(min_length=1,max_length=1000)
    source: Literal['dify']='dify'
    dataset: StrictStr=Field(min_length=1,max_length=64,pattern=r'^[a-z][a-z0-9_-]*$')
    limit: StrictInt=Field(default=5,ge=1,le=10)


def register_source_protocol_routes(app: FastAPI, *, config, session_cookie_value=None, scoped_registry=None):
    adapter=None
    cached_config=None
    cached_transport=None

    def reply(dataset, status='unavailable', results=None, partial=False, error=None, http_status=200, headers=None):
        return JSONResponse({'schema':1,'source':'dify','dataset':dataset,'status':status,
                             'results':results or [],'partial':partial,'error':{'code':error} if error else None},
                            status_code=http_status,headers=headers)

    @app.post('/api/v1/brain/sources/retrieve')
    async def source_retrieve(request: Request):
        nonlocal adapter,cached_config,cached_transport
        token=config.auth_token
        authorization=request.headers.get('authorization','')
        bearer_ok=bool(token and authorization.startswith('Bearer ') and hmac.compare_digest(authorization[7:],token))
        cookie=request.cookies.get('hermes_auth','')
        session_ok=bool((config.auth_token or config.auth_username) and session_cookie_value and cookie and hmac.compare_digest(cookie,session_cookie_value))
        scoped_ok=bool(scoped_registry and scoped_registry.authenticate(request,permission='sources:read'))
        if not (bearer_ok or session_ok or scoped_ok):
            return reply(None,error='unauthorized',http_status=401)
        # Existing app CSRF middleware remains authoritative for session calls.
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>16384:
                return reply(None,error='invalid_input',http_status=413)
        try:
            raw=json.loads(body)
            payload=SourceRequest.model_validate(raw)
            if not payload.query.strip():
                raise ValueError
        except (ValueError,UnicodeError,ValidationError):
            # Do not return pydantic input values (queries may be sensitive).
            return reply(None,error='invalid_input',http_status=400)
        try:
            source_config=DifyConfig.from_env()
        except DifyConfigError:
            return reply(payload.dataset,error='invalid_config',http_status=503)
        if not source_config.enabled:
            return reply(payload.dataset,error='disabled',http_status=503)
        if payload.dataset not in source_config.datasets:
            return reply(payload.dataset,error='dataset_not_allowed',http_status=400)
        transport=getattr(app.state,'dify_transport',None)
        if adapter is None or source_config!=cached_config or transport is not cached_transport:
            adapter=DifyAdapter(config=source_config,transport=transport)
            cached_config=source_config
            cached_transport=transport
        try:
            results,status,partial=await adapter.retrieve(dataset_alias=payload.dataset,query=payload.query,limit=payload.limit)
            return reply(payload.dataset,status,results,partial)
        except DifyUpstreamError as exc:
            headers={'Retry-After':str(exc.retry_after)} if exc.retry_after else None
            return reply(payload.dataset,error=exc.code,http_status=exc.http_status,headers=headers)
