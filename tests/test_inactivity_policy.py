from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_archive import InactivityPolicy

def test_archive_policy_disabled_and_protected_knowledge_exempt(tmp_path):
    s=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p')
    row=s.create(p,'ordinary',[]); protected=s.create(p,'rare critical',[],protected=True)
    policy=InactivityPolicy(s,clock=lambda:100)
    assert not policy.archive(p,row['id'],1,last_used_at=0)
    explicit=InactivityPolicy(s,cutoff_seconds=10,clock=lambda:100)
    assert not explicit.archive(p,protected['id'],1,last_used_at=0)
    assert explicit.archive(p,row['id'],1,last_used_at=0)
    assert s.get(p,row['id'])['state']=='archive'
    s.close()
