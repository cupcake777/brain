import uuid
import pytest
from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore

def test_draft_source_reference_is_typed(tmp_path):
    store = KnowledgeStore(tmp_path / 'db')
    try:
        with pytest.raises(ValueError):
            store.create(Principal('a','w','p'), 'lesson', [{'type':'invented','id':str(uuid.uuid4())}])
    finally:
        store.close()
