import uuid
from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore
from hermes.checks import CheckLedger
from hermes.knowledge_workflow import KnowledgeWorkflow

def test_checked_candidate_state_is_visible_without_mutating_revision(tmp_path):
    p=Principal('a','w','p'); store=KnowledgeStore(tmp_path/'db')
    sid=str(uuid.uuid4()); refs=[{'type':'execution','id':sid}]
    row=store.create(p,'lesson',refs)
    checks=CheckLedger(store,required=('support',),policy_version='one')
    workflow=KnowledgeWorkflow(store,checks,source_resolver=lambda p, refs: {sid:1})
    checks.record(p,row['id'],1,'support','passed',row['digest'],{sid:1})
    result=workflow.accept(p,row['id'],1)
    assert result['state']=='candidate'
    raw=store.conn.execute('SELECT payload FROM brain_v2_knowledge_revisions').fetchone()['payload']
    assert '"state": "draft"' in raw
    store.revise(p,row['id'],1,'changed claim',refs)
    assert store.get(p,row['id'])['state']=='draft'
    store.close()
