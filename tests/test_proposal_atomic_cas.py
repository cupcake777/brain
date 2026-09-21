import uuid
import pytest
from hermes.event_store import EventStore, StaticPrincipalAdapter, ConflictError

def test_proposal_write_uses_atomic_expected_version(tmp_path):
    adapter = StaticPrincipalAdapter(actor='agent', workspace='work', project='project')
    store = EventStore(tmp_path / 'db', principal=adapter)
    identity = str(uuid.uuid4())
    try:
        store.create_proposal(id=identity, agent_id='agent', project_id='project', draft=True)
        statements = []
        store._conn.set_trace_callback(statements.append)
        store.update_proposal(proposal_id=identity, expected_version=1, lesson='new lesson')
        assert any('UPDATE proposal_current' in sql and 'version=1' in sql for sql in statements)
        with pytest.raises(ConflictError):
            store.update_proposal(proposal_id=identity, expected_version=1, lesson='stale lesson')
    finally:
        store.close()
