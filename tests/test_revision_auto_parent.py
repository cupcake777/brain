from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_history import RevisionGraph

def test_regular_revision_automatically_keeps_parent(tmp_path):
    s=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p')
    first=s.create(p,'one',[]); second=s.revise(p,first['id'],1,'two',[])
    assert RevisionGraph(s).parents(p,second['revision_id'])==[{'parent':first['revision_id'],'kind':'parent'}]
    s.close()
