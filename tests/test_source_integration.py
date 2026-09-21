from fastapi.testclient import TestClient
from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.repository import HermesRepository


def test_source_registered_disabled_and_local_retrieve_unaffected(tmp_path, monkeypatch):
    monkeypatch.setenv('BRAIN_DIFY_ENABLED', 'false')
    config = HermesConfig(sync_root=tmp_path, db_path=tmp_path / 'brain.sqlite3', auth_token='test-token')
    repo = HermesRepository(config.db_path)
    client = TestClient(create_app(repo=repo, sync_root=tmp_path, config=config))
    payload = {'query': 'TET2', 'source': 'dify', 'dataset': 'literature', 'limit': 3}
    assert client.post('/api/v1/brain/sources/retrieve', json=payload).status_code == 401
    response = client.post('/api/v1/brain/sources/retrieve', json=payload, headers={'Authorization': 'Bearer test-token'})
    assert response.status_code == 503
    assert response.json()['status'] == 'unavailable'
    assert not {'node_id', 'retrieval_id', 'outcome_required'} & response.json().keys()
    local = client.post('/api/v1/brain/retrieve', json={'query': 'provider logs'})
    assert local.status_code == 200
    assert 'retrieval_id' in local.json()
