from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_policy import VerifiedUseLedger
from hermes.knowledge_promotion import PromotionPolicy

def test_explicit_test_policy_promotes_only_current_checked_candidate(tmp_path):
    s=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p'); row=s.create(p,'lesson',[])
    with s.conn:s.conn.execute('INSERT INTO brain_v2_knowledge_states VALUES(?,?,?)',(row['id'],1,'candidate'))
    proof={'verified':True,'classification':'production','knowledge_id':row['id'],'version':1,'task_id':'one','execution_id':'exec-one'}
    ledger=VerifiedUseLedger(s,verifier=lambda p,e:proof)
    ledger.record(p,row['id'],1,'one','exec-one')
    policy=PromotionPolicy(s,ledger,threshold=2,readiness=lambda p,i,v:True)
    assert not policy.promote(p,row['id'],1)
    proof.update(task_id='two',execution_id='exec-two')
    ledger.record(p,row['id'],1,'two','exec-two')
    assert policy.promote(p,row['id'],1)
    assert s.get(p,row['id'])['state']=='formal'
    revised=s.revise(p,row['id'],1,'changed',[])
    assert revised['state']=='draft'
    assert not policy.promote(p,row['id'],2)
    s.close()
