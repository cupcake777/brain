import uuid
import pytest
from hermes.event_store import Principal,ConflictError
from hermes.knowledge_store import KnowledgeStore
from hermes.checks import CheckLedger
from hermes.knowledge_workflow import KnowledgeWorkflow
from hermes.knowledge_conflicts import ConflictCases

def test_resolution_invalidates_previous_checks(tmp_path):
    s=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p'); sid=str(uuid.uuid4()); refs=[{'type':'execution','id':sid}]
    a=s.create(p,'one',refs); b=s.create(p,'two',refs)
    checks=CheckLedger(s,required=('support',),policy_version='one')
    checks.record(p,a['id'],1,'support','passed',a['digest'],{sid:1})
    cases=ConflictCases(s,authorize=lambda p:True); case=cases.open(p,[a['id'],b['id']]); cases.resolve(p,case)
    flow=KnowledgeWorkflow(s,checks,source_resolver=lambda p,r:{sid:1})
    with pytest.raises(ConflictError): flow.accept(p,a['id'],1)
    s.close()
