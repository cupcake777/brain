import pytest
from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_policy import VerifiedUseLedger
from hermes.knowledge_promotion import PromotionPolicy

def test_promotion_credit_window_is_explicit(tmp_path):
    s=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p'); row=s.create(p,'lesson',[]); now=[100]
    with s.conn:s.conn.execute('INSERT INTO brain_v2_knowledge_states VALUES(?,?,?)',(row['id'],1,'candidate'))
    proof={'verified':True,'classification':'production','knowledge_id':row['id'],'version':1,'task_id':'one','execution_id':'exec'}
    ledger=VerifiedUseLedger(s,verifier=lambda p,e:proof,clock=lambda:now[0])
    ledger.record(p,row['id'],1,'one','exec')
    now[0]=120
    policy=PromotionPolicy(s,ledger,threshold=1,window_seconds=10,clock=lambda:now[0],readiness=lambda p,i,v:True)
    assert not policy.promote(p,row['id'],1)
    s.close()
