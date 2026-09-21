import pytest
from hermes.event_store import Principal, UnauthorizedError
from hermes.knowledge_policy import DirectiveStore

def test_directive_requires_server_authority_and_retains_history(tmp_path):
    p=Principal('human','w','p')
    denied=DirectiveStore(tmp_path/'db',authorize=lambda p:False)
    with pytest.raises(UnauthorizedError): denied.issue(p,'Never replay operations')
    denied.close()
    store=DirectiveStore(tmp_path/'db',authorize=lambda p:p.actor=='human')
    first=store.issue(p,'Never replay operations')
    second=store.issue(p,'Never replay side effects',identity=first['id'],expected_version=1)
    assert second['version']==2
    assert len(store.history(p,first['id']))==2
    assert store.list_active(p)[0]['content']=='Never replay side effects'
    assert store.list_active(Principal('agent','w','other'))==[]
    store.close()
