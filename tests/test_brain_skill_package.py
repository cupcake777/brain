from pathlib import Path
import importlib.util
import pytest

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'skills'/'brain-loop'

def load():
    spec=importlib.util.spec_from_file_location('portable_brain',PACKAGE/'scripts'/'brain.py')
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_packaged_skill_and_dependencies_exist():
    for p in ['SKILL.md','scripts/brain.py','references/protocol.md','templates/proposal.json']:
        assert (PACKAGE/p).is_file()
    text=(PACKAGE/'SKILL.md').read_text()
    assert 'finalize' in text and 'source-retrieve' in text
    assert 'brain.bioinfo.pro' not in text and '/root/' not in text

def test_service_defaults_to_repository_skill(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from hermes.app import create_app
    from hermes.config import HermesConfig
    from hermes.repository import HermesRepository
    monkeypatch.delenv('BRAIN_LOOP_SKILL_ROOT',raising=False)
    config=HermesConfig(sync_root=tmp_path,db_path=tmp_path/'brain.db')
    c=TestClient(create_app(repo=HermesRepository(config.db_path),sync_root=tmp_path,config=config))
    assert c.get('/skills/brain-loop/SKILL.md').text==(PACKAGE/'SKILL.md').read_text()


def test_client_defaults_local_not_private_server(monkeypatch):
    c=load();monkeypatch.delenv('BRAIN_URL',raising=False)
    assert c.api_url()=='http://127.0.0.1:8083'

def test_finalize_uses_auth_and_minimal_payload(monkeypatch):
    c=load();calls=[]
    monkeypatch.setattr(c,'request',lambda p,**k:calls.append((p,k)) or {})
    args=c.parser().parse_args(['finalize','--session-id','session-1'])
    args.handler(args)
    assert calls[0][0]=='/api/v1/brain/finalize'
    assert calls[0][1]['write'] is True
    assert set(calls[0][1]['payload'])=={'agent','host_hash','session_id'}

def test_invalid_url_rejected_before_dispatch(monkeypatch):
    c=load();monkeypatch.setenv('BRAIN_URL','https://name:secret@example.org')
    with pytest.raises(RuntimeError):c.api_url()
