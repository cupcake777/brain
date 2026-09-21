import pytest
from hermes.event_store import Principal, ConflictError, UnauthorizedError
from hermes.knowledge_store import KnowledgeStore

def test_revision_history_and_scope(tmp_path):
    store = KnowledgeStore(tmp_path / 'knowledge.db')
    p = Principal('agent', 'work', 'project')
    first = store.create(p, 'verified lesson', [])
    second = store.revise(p, first['id'], 1, 'updated lesson', [])
    assert second['version'] == 2
    assert store.get(p, first['id'], 1)['content'] == 'verified lesson'
    with pytest.raises(ConflictError):
        store.revise(p, first['id'], 1, 'stale', [])
    with pytest.raises(UnauthorizedError):
        store.get(Principal('other','work','other'), first['id'])
    assert len(store.history(p, first['id'])) == 2
    store.close()
