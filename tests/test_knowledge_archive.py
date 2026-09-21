import pytest
from hermes.event_store import Principal, UnauthorizedError
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_archive import ArchiveSearch

def test_archive_requires_empty_normal_search_explicit_request_and_single_use(tmp_path):
    p=Principal('a','w','p'); store=KnowledgeStore(tmp_path/'db')
    row=store.create(p,'rare safeguard',[])
    with store.conn:
        store.conn.execute('INSERT INTO brain_v2_knowledge_states VALUES(?,?,?)',(row['id'],1,'archive'))
    service=ArchiveSearch(store,clock=lambda:100)
    ticket=service.normal_search(p,'rare')['archive_ticket']
    with pytest.raises(UnauthorizedError): service.search(p,ticket,explicit=False)
    result=service.search(p,ticket,explicit=True)
    assert result[0]['state']=='archive'
    assert store.get(p,row['id'])['state']=='archive'
    with pytest.raises(UnauthorizedError): service.search(p,ticket,explicit=True)
    store.close()
