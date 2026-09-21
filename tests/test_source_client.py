import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills' / 'brain-loop' / 'scripts' / 'brain.py'

def load_client():
    spec = importlib.util.spec_from_file_location('source_client', SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_source_command_uses_protected_endpoint(monkeypatch):
    client = load_client()
    calls = []
    monkeypatch.setattr(client, 'request', lambda path, **kwargs: calls.append((path, kwargs)) or {'status': 'empty'})
    args = client.parser().parse_args(['source-retrieve', '--query', 'TET2', '--dataset', 'literature', '--limit', '3'])
    assert args.handler(args) == {'status': 'empty'}
    assert calls == [('/api/v1/brain/sources/retrieve', {'write': True, 'payload': {'query': 'TET2', 'source': 'dify', 'dataset': 'literature', 'limit': 3}})]


def test_source_requires_token_before_network(monkeypatch):
    import pytest
    client = load_client()
    monkeypatch.delenv('BRAIN_TOKEN', raising=False)
    monkeypatch.setattr(client.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('unauthenticated network dispatch'))
    args = client.parser().parse_args(['source-retrieve', '--query', 'TET2'])
    with pytest.raises(RuntimeError, match='BRAIN_TOKEN'):
        args.handler(args)


def test_source_sends_only_authorized_query_and_bearer(monkeypatch):
    import json
    client = load_client()
    monkeypatch.setenv('BRAIN_TOKEN', 'test-token')
    monkeypatch.setenv('BRAIN_URL', 'http://localhost:8083')
    monkeypatch.setenv('BRAIN_SESSION_ID', 'do-not-transmit-session')
    captures = []
    class Reply:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return b'{"status":"empty","results":[]}'
    def urlopen(req, **kwargs):
        captures.append(req)
        return Reply()
    monkeypatch.setattr(client.urllib.request, 'urlopen', urlopen)
    args = client.parser().parse_args(['source-retrieve', '--query', 'TET2'])
    assert args.handler(args)['status'] == 'empty'
    req = captures[0]
    assert req.full_url == 'http://localhost:8083/api/v1/brain/sources/retrieve'
    assert req.get_header('Authorization') == 'Bearer test-token'
    assert json.loads(req.data) == {'query': 'TET2', 'source': 'dify', 'dataset': 'literature', 'limit': 5}
