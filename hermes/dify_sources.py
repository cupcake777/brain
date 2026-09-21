"""Read-only Dify evidence adapter; no knowledge writes or query persistence."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import logging
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlparse
from uuid import UUID
import httpx

LOG = logging.getLogger('hermes.dify_sources')
BASE = 'https://api.dify.ai/v1'
MAX_BODY = 2 * 1024 * 1024

class DifyConfigError(Exception):
    pass

class DifyUpstreamError(Exception):
    def __init__(self, code: str, http_status: int = 502, retry_after: int | None = None):
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.retry_after = retry_after

@dataclass(frozen=True)
class DifyConfig:
    enabled: bool = False
    api_key: str = field(default='', repr=False)
    datasets: dict[str, str] = field(default_factory=dict)
    daily_limit: int = 50
    quota_db_path: Path = Path("data/dify-quota.sqlite3")

    def __post_init__(self):
        if type(self.daily_limit) is not int or self.daily_limit < 1:
            raise DifyConfigError('invalid_config')
        for alias, ident in self.datasets.items():
            if not isinstance(alias, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', alias):
                raise DifyConfigError('invalid_config')
            try:
                if str(UUID(ident)) != ident:
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                raise DifyConfigError('invalid_config') from None

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        flag = env.get('BRAIN_DIFY_ENABLED', 'false').lower()
        if flag not in ('false','0','true','1'):
            raise DifyConfigError('invalid_config')
        if flag in ('false','0'):
            return cls()
        try:
            key_file = Path(env.get(
                "BRAIN_DIFY_KEY_FILE",
                str(Path.home() / ".config" / "brain" / "dify-dataset-key"),
            )).expanduser()
            datasets_file = Path(env.get(
                "BRAIN_DIFY_DATASETS_FILE",
                "config/dify-sources.json",
            )).expanduser()
            quota_db = Path(env.get(
                "BRAIN_DIFY_QUOTA_DB",
                "data/dify-quota.sqlite3",
            )).expanduser()
            key = key_file.read_text().strip()
            datasets = json.loads(datasets_file.read_text())
            if not key or not isinstance(datasets, dict) or not datasets:
                raise ValueError
            return cls(
                enabled=True,
                api_key=key,
                datasets=datasets,
                daily_limit=int(env.get("BRAIN_DIFY_DAILY_LIMIT", "50")),
                quota_db_path=quota_db,
            )
        except (OSError, ValueError, TypeError):
            raise DifyConfigError('invalid_config') from None


def reserve_quota(db_path: Path, limit: int, now=None):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(timezone.utc).date()
    next_day = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    retry_after = max(1, math.ceil((next_day-now).total_seconds()))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path, timeout=1) as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('CREATE TABLE IF NOT EXISTS dify_quota(day TEXT PRIMARY KEY,count INTEGER NOT NULL CHECK(count>=0))')
        conn.execute('INSERT OR IGNORE INTO dify_quota(day,count) VALUES (?,0)', (day.isoformat(),))
        count = conn.execute('SELECT count FROM dify_quota WHERE day=?',(day.isoformat(),)).fetchone()[0]
        if count >= limit:
            raise DifyUpstreamError('quota_exceeded',429,retry_after)
        conn.execute('UPDATE dify_quota SET count=count+1 WHERE day=?',(day.isoformat(),))


def _text(value):
    return value.strip() if isinstance(value,str) and value.strip() else None


def parse_records(records, *, dataset_id):
    parsed=[]
    for record in records:
        if not isinstance(record,dict):
            continue
        s=record.get('segment')
        if not isinstance(s,dict):
            continue
        doc=s.get('document') or {}
        if not isinstance(doc,dict):
            continue
        sid=_text(s.get('id'))
        did=_text(s.get('document_id')) or _text(doc.get('id'))
        content=s.get('content')
        if not sid or not did or not isinstance(content,str) or not content.strip():
            continue
        if doc.get('id') and doc['id']!=did:
            continue
        # Reject ambiguous separators/control characters in citation components.
        if any(not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',v) for v in (sid,did)):
            continue
        meta=doc.get('doc_metadata')
        meta=meta if isinstance(meta,dict) else {}
        url=_text(meta.get('source_url')) or _text(meta.get('url'))
        if url:
            try:
                u=urlparse(url)
                if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:
                    url=None
            except ValueError:
                url=None
        doi=_text(meta.get('doi'))
        if doi and not re.fullmatch(r'10\.\d{4,9}/\S+',doi):
            doi=None
        page=meta.get('page') # segment.position is chunk order, never paper page
        page=str(page) if type(page) is int and page>0 else _text(page)
        if page and not re.fullmatch(r'[0-9]+(?:[-–][0-9]+)?',page):
            page=None
        score=record.get('score')
        if type(score) not in (int,float) or not math.isfinite(score):
            score=None
        parsed.append({'citation_id':f'dify:{dataset_id}:{did}:{sid}', 'dataset_id':dataset_id,
                       'document_id':did,'segment_id':sid,'title':_text(doc.get('name')),
                       'content':content[:4000],'score':score,'source_url':url,'doi':doi,
                       'page':page,'truncated':len(content)>4000})
    return parsed


class DifyAdapter:
    def __init__(self, *, config: DifyConfig, transport=None):
        self.config=config
        self.transport=transport
        self.semaphore=asyncio.Semaphore(2)
        self.total_timeout=12.0

    async def retrieve(self, *, dataset_alias, query, limit):
        if dataset_alias not in self.config.datasets:
            raise ValueError('dataset_not_allowed')
        if not self.config.enabled:
            raise DifyUpstreamError('disabled',503)
        if type(limit) is not int or not 1<=limit<=10 or not isinstance(query,str) or not query.strip() or len(query)>1000:
            raise ValueError('invalid_input')
        start=time.monotonic()
        count=0; status=200; error='none'
        try:
            async with asyncio.timeout(self.total_timeout):
                async with self.semaphore:
                    # short transactional operation; offloaded so SQLite contention cannot stall the event loop
                    try:
                        await asyncio.to_thread(reserve_quota,self.config.quota_db_path,self.config.daily_limit)
                    except (sqlite3.Error,OSError):
                        raise DifyUpstreamError('quota_storage_unavailable',503) from None
                    ident=self.config.datasets[dataset_alias]
                    timeout=httpx.Timeout(10.0,connect=3.0)
                    async with httpx.AsyncClient(timeout=timeout,transport=self.transport,follow_redirects=False) as client:
                        async with client.stream('POST', f'{BASE}/datasets/{ident}/retrieve',
                            headers={'Authorization':'Bearer '+self.config.api_key},
                            json={'query':query.strip(),'retrieval_model':{'search_method':'semantic_search','reranking_enable':False,'top_k':limit,'score_threshold_enabled':False}}) as response:
                            if response.status_code!=200:
                                code={401:'upstream_unauthorized',403:'upstream_unauthorized',429:'upstream_rate_limited'}.get(response.status_code,'upstream_server_error' if response.status_code>=500 else 'upstream_http_error')
                                raise DifyUpstreamError(code)
                            body=bytearray()
                            async for chunk in response.aiter_bytes():
                                body.extend(chunk)
                                if len(body)>MAX_BODY:
                                    raise DifyUpstreamError('invalid_upstream_response')
                    try:
                        data=json.loads(body)
                    except (ValueError,UnicodeError):
                        raise DifyUpstreamError('invalid_upstream_response') from None
                    if not isinstance(data,dict) or not isinstance(data.get('records'),list):
                        raise DifyUpstreamError('invalid_upstream_response')
                    records=data['records']
                    if not records:
                        return [],'empty',False
                    parsed=parse_records(records,dataset_id=ident)
                    if not parsed:
                        raise DifyUpstreamError('invalid_upstream_response')
                    count=min(len(parsed),limit)
                    return parsed[:limit],'ok',len(parsed)<len(records)
        except (TimeoutError,httpx.TimeoutException):
            status=504;error='upstream_timeout'
            raise DifyUpstreamError(error,status) from None
        except httpx.RequestError:
            status=502;error='upstream_network_error'
            raise DifyUpstreamError(error,status) from None
        except DifyUpstreamError as exc:
            status=exc.http_status;error=exc.code
            raise
        finally:
            LOG.info('source=%s elapsed_ms=%d hits=%d http_status=%d error=%s',dataset_alias,int((time.monotonic()-start)*1000),count,status,error)
