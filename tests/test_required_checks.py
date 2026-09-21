import pytest
from hermes.event_store import Principal, ConflictError
from hermes.knowledge_store import KnowledgeStore
from hermes.checks import CheckLedger

def test_checks_bind_current_revision_policy_and_sources(tmp_path):
    p=Principal('a','w','p')
    store=KnowledgeStore(tmp_path/'db')
    row=store.create(p,'lesson',[])
    ledger=CheckLedger(store, required=('privacy','support'), policy_version='one')
    ledger.record(p,row['id'],1,'privacy','passed',row['digest'],{})
    assert not ledger.ready(p,row['id'],1,{})
    ledger.record(p,row['id'],1,'support','pending',row['digest'],{})
    assert not ledger.ready(p,row['id'],1,{})
    ledger.record(p,row['id'],1,'support','passed',row['digest'],{})
    assert ledger.ready(p,row['id'],1,{})
    assert not ledger.ready(p,row['id'],1,{'source':'changed'})
    ledger.policy_version='two'
    assert not ledger.ready(p,row['id'],1,{})
    ledger.policy_version='one'
    store.revise(p,row['id'],1,'changed claim',[])
    assert not ledger.ready(p,row['id'],1,{})
    with pytest.raises(ConflictError):
        ledger.record(p,row['id'],1,'support','passed',row['digest'],{})
    store.close()
