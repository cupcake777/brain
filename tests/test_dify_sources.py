import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import httpx
import pytest
from hermes.dify_sources import DifyAdapter, DifyConfig, DifyConfigError, DifyUpstreamError, parse_records, reserve_quota

DS='019a2b27-12d5-4709-b379-cf0797d55607'

def config(tmp_path, limit=50):
    return DifyConfig(enabled=True, api_key='private-key', datasets={'literature':DS}, quota_db_path=tmp_path/'quota.db', daily_limit=limit)

def record():
    return {'segment':{'id':'seg','document_id':'doc','content':'TET2 evidence','position':3,'document':{'id':'doc','name':'Paper','doc_metadata':None}},'score':0.8}

def run(adapter, records=None):
    return asyncio.run(adapter.retrieve(dataset_alias='literature',query='TET2',limit=3))

def adapter(tmp_path, response=None, handler=None, limit=50):
    return DifyAdapter(config=config(tmp_path,limit),transport=httpx.MockTransport(handler or (lambda r: response or httpx.Response(200,json={'records':[record()]}))))

def test_default_disabled():
    assert not DifyConfig.from_env({}).enabled

def test_lazy_config_missing_key(tmp_path):
    with pytest.raises(DifyConfigError):
        DifyConfig.from_env({'BRAIN_DIFY_ENABLED':'true','BRAIN_DIFY_KEY_FILE':str(tmp_path/'absent')})

def test_config_reads_whitelist(tmp_path):
    (tmp_path/'key').write_text('secret')
    (tmp_path/'ds').write_text(json.dumps({'literature':DS}))
    c=DifyConfig.from_env({'BRAIN_DIFY_ENABLED':'true','BRAIN_DIFY_KEY_FILE':str(tmp_path/'key'),'BRAIN_DIFY_DATASETS_FILE':str(tmp_path/'ds'),'BRAIN_DIFY_QUOTA_DB':str(tmp_path/'q')})
    assert c.datasets=={'literature':DS} and c.daily_limit==50
    assert 'secret' not in repr(c)

@pytest.mark.parametrize('limit',['0','-1','bad'])
def test_invalid_daily_limit(tmp_path,limit):
    (tmp_path/'key').write_text('secret'); (tmp_path/'ds').write_text(json.dumps({'literature':DS}))
    with pytest.raises(DifyConfigError):
        DifyConfig.from_env({'BRAIN_DIFY_ENABLED':'true','BRAIN_DIFY_KEY_FILE':str(tmp_path/'key'),'BRAIN_DIFY_DATASETS_FILE':str(tmp_path/'ds'),'BRAIN_DIFY_DAILY_LIMIT':limit})

def test_success_payload_and_no_context(tmp_path):
    seen=[]
    def handler(r):
        seen.append(r)
        return httpx.Response(200,json={'records':[record()]})
    a=adapter(tmp_path,handler=handler)
    results,status,partial=run(a)
    assert status=='ok' and not partial
    assert results[0]['citation_id']==f'dify:{DS}:doc:seg'
    assert results[0]['page'] is None # position is chunk order, NOT page
    assert results[0]['doi'] is None
    assert str(seen[0].url)==f'https://api.dify.ai/v1/datasets/{DS}/retrieve'
    assert seen[0].headers['authorization']=='Bearer private-key'
    payload=json.loads(seen[0].content)
    assert payload=={'query':'TET2','retrieval_model':{'search_method':'semantic_search','reranking_enable':False,'top_k':3,'score_threshold_enabled':False}}

def test_empty(tmp_path):
    assert run(adapter(tmp_path,httpx.Response(200,json={'records':[]})))==([], 'empty',False)

@pytest.mark.parametrize('body',[{}, {'records':None},{'records':'bad'},{'records':[{'segment':{}}]},[],{'records':[{'score':1}]}])
def test_malformed_not_empty(tmp_path,body):
    with pytest.raises(DifyUpstreamError) as exc:
        run(adapter(tmp_path,httpx.Response(200,json=body)))
    assert exc.value.code=='invalid_upstream_response' and exc.value.http_status==502

def test_bad_json(tmp_path):
    with pytest.raises(DifyUpstreamError,match='invalid_upstream_response'):
        run(adapter(tmp_path,httpx.Response(200,text='private upstream error')))

def test_partial(tmp_path):
    rows,status,partial=run(adapter(tmp_path,httpx.Response(200,json={'records':[record(),{},None]})))
    assert len(rows)==1 and status=='ok' and partial

def test_excerpt_metadata_and_identity():
    r=record(); r['segment']['content']='x'*4100
    r['segment']['document']['doc_metadata']={'page':'12','doi':'10.1234/abc','source_url':'https://example.org/p'}
    rows=parse_records([r],dataset_id=DS)
    assert len(rows[0]['content'])==4000 and rows[0]['truncated']
    assert rows[0]['page']=='12' and rows[0]['doi']=='10.1234/abc'
    r['segment']['document']['id']='different'
    assert parse_records([r],dataset_id=DS)==[]

def test_bad_metadata_no_invention():
    r=record();r['score']=float('nan');r['segment']['document']['name']=''
    r['segment']['document']['doc_metadata']={'source_url':'javascript:alert(1)','doi':'garbage','page':False}
    row=parse_records([r],dataset_id=DS)[0]
    assert row['score'] is None and row['title'] is None
    assert row['source_url'] is None and row['doi'] is None and row['page'] is None

@pytest.mark.parametrize('code,error',[(401,'upstream_unauthorized'),(429,'upstream_rate_limited'),(500,'upstream_server_error'),(400,'upstream_http_error')])
def test_upstream_errors_safe(tmp_path,code,error,caplog):
    with pytest.raises(DifyUpstreamError) as exc:
        run(adapter(tmp_path,httpx.Response(code,text='secret-private-key')))
    assert exc.value.code==error
    assert 'secret-private-key' not in str(exc.value)+caplog.text
    assert 'TET2' not in caplog.text

def test_timeout(tmp_path):
    def handler(r):raise httpx.ReadTimeout('private text')
    with pytest.raises(DifyUpstreamError) as exc:run(adapter(tmp_path,handler=handler))
    assert exc.value.http_status==504

def test_failed_dispatch_counts_and_restart(tmp_path):
    with pytest.raises(DifyUpstreamError):run(adapter(tmp_path,httpx.Response(500),limit=1))
    with pytest.raises(DifyUpstreamError) as exc:run(adapter(tmp_path,limit=1))
    assert exc.value.code=='quota_exceeded' and exc.value.retry_after>0

def test_alias_refusal_no_quota(tmp_path):
    a=adapter(tmp_path)
    with pytest.raises(ValueError):asyncio.run(a.retrieve(dataset_alias=DS,query='q',limit=3))
    assert not (tmp_path/'quota.db').exists()

def test_atomic_quota_race_and_rollover(tmp_path):
    db=tmp_path/'quota.db'
    def take(_):
        try: reserve_quota(db,5,now=datetime(2026,1,1,23,59,tzinfo=timezone.utc));return True
        except DifyUpstreamError as e:assert e.code=='quota_exceeded';return False
    with ThreadPoolExecutor(max_workers=10) as pool:assert sum(pool.map(take,range(20)))==5
    reserve_quota(db,5,now=datetime(2026,1,2,tzinfo=timezone.utc))
    with sqlite3.connect(db) as conn:assert conn.execute('select day,count from dify_quota order by day').fetchall()==[('2026-01-01',5),('2026-01-02',1)]

def test_concurrency_and_total_queue_budget(tmp_path):
    async def driver():
        active=0;peak=0
        async def handler(r):
            nonlocal active,peak
            active+=1;peak=max(peak,active)
            try:await asyncio.sleep(.03)
            finally:active-=1
            return httpx.Response(200,json={'records':[]})
        a=adapter(tmp_path,handler=handler)
        await asyncio.gather(*(a.retrieve(dataset_alias='literature',query='q',limit=1) for _ in range(6)))
        assert peak==2
        a.total_timeout=.01
        a.semaphore=asyncio.Semaphore(0)
        with pytest.raises(DifyUpstreamError) as exc:await a.retrieve(dataset_alias='literature',query='q',limit=1)
        assert exc.value.http_status==504
        with sqlite3.connect(tmp_path/'quota.db') as c:assert c.execute('select sum(count) from dify_quota').fetchone()[0]==6
    asyncio.run(driver())
