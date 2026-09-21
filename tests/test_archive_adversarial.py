import pytest
from hermes.event_store import Principal,UnauthorizedError
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_archive import ArchiveSearch

def test_archive_ticket_denies_other_actor_and_expiry(tmp_path):
    store=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p'); now=[100]
    service=ArchiveSearch(store,clock=lambda:now[0],ttl=10)
    token=service.normal_search(p,'missing')['archive_ticket']
    with pytest.raises(UnauthorizedError): service.search(Principal('b','w','p'),token,explicit=True)
    now[0]=110
    with pytest.raises(UnauthorizedError): service.search(p,token,explicit=True)
    store.close()

def test_new_usable_result_cancels_archive_ticket(tmp_path):
    store=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p')
    service=ArchiveSearch(store)
    token=service.normal_search(p,'lesson')['archive_ticket']
    row=store.create(p,'lesson',[])
    with store.conn: store.conn.execute('INSERT INTO brain_v2_knowledge_states VALUES(?,?,?)',(row['id'],1,'candidate'))
    with pytest.raises(UnauthorizedError): service.search(p,token,explicit=True)
    store.close()
