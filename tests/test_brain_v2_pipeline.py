import uuid
from datetime import datetime,timezone
from hermes.event_store import EventStore,StaticPrincipalAdapter,Principal
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_extraction import ExtractionQueue
from hermes.knowledge_sources import RegisteredSources
from hermes.checks import CheckLedger
from hermes.knowledge_workflow import KnowledgeWorkflow
from hermes.knowledge_retrieval_v2 import retrieve

def test_registered_event_to_checked_candidate_disposable_database(tmp_path):
    p=Principal('a','w','p'); adapter=StaticPrincipalAdapter(actor='a',workspace='w',project='p')
    events=EventStore(tmp_path/'events',principal=adapter)
    sid=str(uuid.uuid4())
    events.record_event(id=sid,project_id='p',agent_id='a',occurred_at=datetime.now(timezone.utc),action='assert fixture',result='fixture passed')
    knowledge=KnowledgeStore(tmp_path/'knowledge')
    def read(principal,identity):
        assert principal==p
        return events.get_event(identity)
    queue=ExtractionQueue(knowledge,event_reader=read)
    queue.enqueue(p,sid)
    queue.run_once(p,lambda event:[{'content':'verify fixture before accepting result'}])
    row=knowledge.list_current(p)[0]
    checks=CheckLedger(knowledge,required=('privacy','support'),policy_version='test-policy')
    sources=RegisteredSources(events); versions=sources(p,row['source_refs'])
    # Explicit sandbox test verifier, not production semantic verification.
    for name in checks.required:checks.record(p,row['id'],1,name,'passed',row['digest'],versions)
    KnowledgeWorkflow(knowledge,checks,source_resolver=sources).accept(p,row['id'],1)
    result=retrieve(knowledge,p,'fixture')
    assert result['candidates'][0]['id']==row['id']
    assert result['formal']==[]
    events.close();knowledge.close()
