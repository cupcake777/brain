import uuid
import pytest
from hermes.event_store import EventStore, StaticPrincipalAdapter, ConflictError

def test_registered_document_revision_cannot_be_overwritten(tmp_path):
    store = EventStore(tmp_path / 'db.sqlite3', principal=StaticPrincipalAdapter(actor='actor',workspace='workspace',project='project'))
    identity = uuid.uuid4()
    try:
        store.register_source_document(doc_id=identity, url='https://example.org/paper', version=1, excerpt='original')
        with pytest.raises(ConflictError):
            store.register_source_document(doc_id=identity, url='https://example.org/paper', version=1, excerpt='changed')
        row = store._conn.execute('SELECT excerpt FROM source_documents WHERE id=?', (str(identity),)).fetchone()
        assert row['excerpt'] == 'original'
    finally:
        store.close()
