import pytest
from hermes.event_store import Principal, ConflictError
from hermes.knowledge_store import KnowledgeStore
from hermes.checks import CheckLedger
from hermes.knowledge_workflow import KnowledgeWorkflow

def test_candidate_acceptance_requires_sources_and_checks(tmp_path):
    p=Principal('a','w','p'); store=KnowledgeStore(tmp_path/'db')
    row=store.create(p,'lesson',[])
    checks=CheckLedger(store,required=('support',),policy_version='one')
    workflow=KnowledgeWorkflow(store,checks,source_resolver=lambda p, refs: {})
    checks.record(p,row['id'],1,'support','passed',row['digest'],{})
    with pytest.raises(ConflictError): workflow.accept(p,row['id'],1)
    assert store.get(p,row['id'])['state']=='draft'
    store.close()
