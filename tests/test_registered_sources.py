import uuid
import pytest
from hermes.event_store import EventStore,StaticPrincipalAdapter,Principal,UnauthorizedError
from hermes.knowledge_sources import RegisteredSources
from datetime import datetime,timezone

def test_registered_source_adapter_rechecks_authenticated_scope(tmp_path):
    adapter=StaticPrincipalAdapter(actor='a',workspace='w',project='p')
    store=EventStore(tmp_path/'db',principal=adapter); identity=str(uuid.uuid4())
    store.record_event(id=identity,agent_id='a',project_id='p',occurred_at=datetime.now(timezone.utc),action='test',result='ok')
    resolver=RegisteredSources(store)
    refs=[{'type':'execution','id':identity}]
    assert resolver(Principal('a','w','p'),refs)=={identity:1}
    with pytest.raises(UnauthorizedError):resolver(Principal('b','w','other'),refs)
    store.close()
