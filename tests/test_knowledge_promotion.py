import pytest
from hermes.event_store import Principal,ConflictError
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_policy import VerifiedUseLedger
from hermes.knowledge_promotion import PromotionPolicy

def test_promotion_disabled_without_policy_and_exact_credit_required(tmp_path):
    s=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p'); row=s.create(p,'lesson',[])
    ledger=VerifiedUseLedger(s,verifier=lambda p,e:None)
    policy=PromotionPolicy(s,ledger)
    assert policy.promote(p,row['id'],1) is False
    explicit=PromotionPolicy(s,ledger,threshold=2)
    assert explicit.promote(p,row['id'],1) is False
    with pytest.raises(ValueError):PromotionPolicy(s,ledger,threshold=True)
    s.close()
