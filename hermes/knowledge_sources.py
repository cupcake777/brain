"""Registered authorized immutable sources; no arbitrary source fetching."""
from hermes.contracts import SourceRef
from hermes.event_store import UnauthorizedError,ReferenceUnavailableError

class RegisteredSources:
    def __init__(self,event_store): self.events=event_store
    def __call__(self,p,references):
        bound=self.events._resolve_principal()
        if bound!=p: raise UnauthorizedError('source principal mismatch')
        versions={}
        for raw in references:
            reference=SourceRef.model_validate(raw)
            identity=str(reference.id)
            if reference.type.value=='execution':
                versions_in_scope=[
                    row['version'] for row in self.events.list_events()
                    if row['id']==identity
                ]
                if not versions_in_scope:
                    raise ReferenceUnavailableError('registered event unavailable')
                event=self.events.get_event(identity,version=max(versions_in_scope))
                if event['project_id']!=p.project: raise UnauthorizedError('event project mismatch')
                versions[identity]=event['version']
            else:
                row=self.events._conn.execute('SELECT version FROM source_documents WHERE id=? AND principal_workspace=? AND principal_project=? ORDER BY version DESC LIMIT 1',
                    (identity,p.workspace,p.project)).fetchone()
                if row is None: raise ReferenceUnavailableError('registered document unavailable')
                versions[identity]=row['version']
        return versions
