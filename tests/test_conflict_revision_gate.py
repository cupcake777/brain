import pytest
from hermes.event_store import Principal, ConflictError
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_conflicts import ConflictCases

def test_unresolved_conflict_cannot_be_escaped_by_revision(tmp_path):
    s=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p')
    a=s.create(p,'one',[]); b=s.create(p,'two',[])
    ConflictCases(s,authorize=lambda p:False).open(p,[a['id'],b['id']])
    with pytest.raises(ConflictError): s.revise(p,a['id'],1,'bypass',[])
    s.close()
