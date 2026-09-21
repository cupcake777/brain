import json
import httpx
from fastapi.testclient import TestClient
import pytest
from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.repository import HermesRepository

DS='019a2b27-12d5-4709-b379-cf0797d55607'
PAYLOAD={'query':'TET2','source':'dify','dataset':'literature','limit':3}
AUTH={'Authorization':'Bearer test-token'}


def client(tmp_path,monkeypatch,auth=True):
    (tmp_path/'key').write_text('cloud-secret')
    (tmp_path/'ds').write_text(json.dumps({'literature':DS}))
    for key,value in {'BRAIN_DIFY_ENABLED':'true','BRAIN_DIFY_KEY_FILE':str(tmp_path/'key'),'BRAIN_DIFY_DATASETS_FILE':str(tmp_path/'ds'),'BRAIN_DIFY_QUOTA_DB':str(tmp_path/'quota')}.items():
        monkeypatch.setenv(key,value)
    config=HermesConfig(sync_root=tmp_path,db_path=tmp_path/'brain.db',auth_token='test-token' if auth else None)
    app=create_app(repo=HermesRepository(config.db_path),sync_root=tmp_path,config=config)
    app.state.dify_transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'records':[]}))
    return TestClient(app)


def test_auth_required_no_dispatch(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    assert c.post('/api/v1/brain/sources/retrieve',json=PAYLOAD).status_code==401
    assert not (tmp_path/'quota').exists()


def test_auth_disabled_still_fail_closed(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch,auth=False)
    assert c.post('/api/v1/brain/sources/retrieve',json=PAYLOAD).status_code==401
    assert not (tmp_path/'quota').exists()


def test_empty_contract(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    r=c.post('/api/v1/brain/sources/retrieve',headers=AUTH,json=PAYLOAD)
    assert r.status_code==200
    assert r.json()=={'schema':1,'source':'dify','dataset':'literature','status':'empty','results':[],'partial':False,'error':None}

@pytest.mark.parametrize('change',[{'limit':True},{'limit':'3'},{'limit':0},{'limit':11},{'query':' '},{'query':'x'*1001},{'source':'unknown'},{'dataset':DS},{'url':'https://evil'}])
def test_bad_input_no_quota(tmp_path,monkeypatch,change):
    c=client(tmp_path,monkeypatch)
    r=c.post('/api/v1/brain/sources/retrieve',headers=AUTH,json=PAYLOAD|change)
    assert r.status_code in (400,422)
    assert not (tmp_path/'quota').exists()
    assert 'cloud-secret' not in r.text


def test_invalid_json_no_echo(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    r=c.post('/api/v1/brain/sources/retrieve',headers=AUTH,content='{secret-private-query')
    assert r.status_code==400 and 'secret-private-query' not in r.text


def test_all_bad_is_failure(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    c.app.state.dify_transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'records':[{}]}))
    r=c.post('/api/v1/brain/sources/retrieve',headers=AUTH,json=PAYLOAD)
    assert r.status_code==502 and r.json()['error']['code']=='invalid_upstream_response'


def test_quota_error_contract(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    monkeypatch.setenv('BRAIN_DIFY_DAILY_LIMIT','1')
    assert c.post('/api/v1/brain/sources/retrieve',headers=AUTH,json=PAYLOAD).status_code==200
    r=c.post('/api/v1/brain/sources/retrieve',headers=AUTH,json=PAYLOAD)
    assert r.status_code==429 and r.json()['error']['code']=='quota_exceeded'
    assert int(r.headers['retry-after'])>0


def test_cookie_auth_requires_csrf(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    c.post('/login',data={'username':'agent','password':'test-token'})
    assert c.post('/api/v1/brain/sources/retrieve',json=PAYLOAD).status_code==403
    assert not (tmp_path/'quota').exists()
    r=c.post('/api/v1/brain/sources/retrieve',json=PAYLOAD,headers={'Origin':'http://testserver'})
    assert r.status_code==200


def test_missing_config_does_not_break_startup(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    monkeypatch.setenv('BRAIN_DIFY_KEY_FILE',str(tmp_path/'missing'))
    r=c.post('/api/v1/brain/sources/retrieve',headers=AUTH,json=PAYLOAD)
    assert r.status_code==503 and r.json()['error']['code']=='invalid_config'
    assert c.get('/api/v1/brain/health').status_code==200
