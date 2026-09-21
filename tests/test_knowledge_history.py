import pytest
from hermes.event_store import Principal, UnauthorizedError
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_history import RevisionGraph

def test_revision_graph_preserves_typed_same_scope_parent(tmp_path):
    store=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p')
    parent=store.create(p,'source lesson',[]); child=store.create(p,'derived lesson',[])
    graph=RevisionGraph(store)
    graph.link(p,child['revision_id'],parent['revision_id'],'derived')
    assert graph.parents(p,child['revision_id'])[0]['parent']==parent['revision_id']
    with pytest.raises(ValueError): graph.link(p,parent['revision_id'],child['revision_id'],'parent')
    other=store.create(Principal('a','w','other'),'other',[])
    with pytest.raises(UnauthorizedError): graph.link(p,child['revision_id'],other['revision_id'],'merge')
    store.close()
