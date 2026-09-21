import uuid
from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_extraction import ExtractionQueue

def test_extraction_survives_provider_failure_and_derives_once(tmp_path):
    p=Principal('a','w','p'); store=KnowledgeStore(tmp_path/'db')
    event={'id':str(uuid.uuid4()),'project_id':'p','action':'test','result':'failed'}
    queue=ExtractionQueue(store,event_reader=lambda p,i:event)
    job=queue.enqueue(p,event['id'])
    def offline(event): raise RuntimeError('private failure')
    assert queue.run_once(p,offline)['state']=='pending'
    assert queue.run_once(p,lambda e:[{'content':'verified failure lesson'}])['state']=='completed'
    assert queue.enqueue(p,event['id'])==job
    assert queue.run_once(p,lambda e:[{'content':'duplicate'}]) is None
    assert len(store.list_current(p))==1
    assert store.list_current(p)[0]['state']=='draft'
    store.close()
