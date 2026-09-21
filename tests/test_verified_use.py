from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_policy import VerifiedUseLedger

def test_credit_requires_trusted_production_verification_and_dedups(tmp_path):
    p=Principal('a','w','p'); store=KnowledgeStore(tmp_path/'db')
    row=store.create(p,'lesson',[])
    proof={'verified':True,'classification':'production','knowledge_id':row['id'],'version':1,'task_id':'task','execution_id':'exec'}
    ledger=VerifiedUseLedger(store,verifier=lambda p,e:proof)
    assert ledger.record(p,row['id'],1,'task','exec') is True
    assert ledger.record(p,row['id'],1,'task','exec') is False
    assert ledger.count(p,row['id'],1)==1
    proof['classification']='evaluation'; proof['task_id']='probe'
    assert ledger.record(p,row['id'],1,'probe','exec') is False
    store.revise(p,row['id'],1,'changed conclusion',[])
    assert ledger.count(p,row['id'],2)==0
    assert ledger.promotion_threshold is None
    store.close()
