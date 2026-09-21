import pytest
from hermes.event_store import Principal, UnauthorizedError
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_history import RevisionGraph
from hermes.knowledge_conflicts import ConflictCases

def test_conflict_suspends_dependents_and_requires_authorized_decision(tmp_path):
    s=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p')
    a=s.create(p,'claim one',[]); b=s.create(p,'claim two',[]); child=s.create(p,'dependent',[]); unrelated=s.create(p,'unrelated',[])
    RevisionGraph(s).link(p,child['revision_id'],a['revision_id'],'derived')
    cases=ConflictCases(s,authorize=lambda p:p.actor=='human')
    case=cases.open(p,[a['id'],b['id']])
    assert s.get(p,child['id'])['state']=='disputed'
    assert s.get(p,unrelated['id'])['state']=='draft'
    with pytest.raises(UnauthorizedError): cases.resolve(p,case)
    cases.resolve(Principal('human','w','p'),case)
    assert s.get(p,a['id'])['state']=='draft'
    assert s.get(p,child['id'])['state']=='draft'
    s.close()
