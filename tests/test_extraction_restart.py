import uuid
from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_extraction import ExtractionQueue

def test_pending_extraction_recovers_after_reopening_database(tmp_path):
    path=tmp_path/'db'; p=Principal('a','w','p')
    event={'id':str(uuid.uuid4()),'project_id':'p','action':'test','result':'unknown'}
    store=KnowledgeStore(path); queue=ExtractionQueue(store,event_reader=lambda p,i:event)
    identity=queue.enqueue(p,event['id']); store.close()
    store=KnowledgeStore(path); queue=ExtractionQueue(store,event_reader=lambda p,i:event)
    result=queue.run_once(p,lambda e:[{'content':'unknown outcome is not success'},{'content':'verify exact evidence before retry'}])
    assert result=={'id':identity,'state':'completed'}
    assert len(store.list_current(p))==2
    store.close()
    store=KnowledgeStore(path); queue=ExtractionQueue(store,event_reader=lambda p,i:event)
    assert queue.run_once(p,lambda e:[]) is None
    assert len(store.list_current(p))==2
    store.close()
