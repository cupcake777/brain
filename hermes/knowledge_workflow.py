"""Candidate acceptance is not formal promotion. Trusted internal workflow only."""
import json
from hermes.event_store import ConflictError

class KnowledgeWorkflow:
    def __init__(self,store,checks,*,source_resolver):
        self.store=store; self.checks=checks; self.resolve=source_resolver
        store.conn.execute('''CREATE TABLE IF NOT EXISTS brain_v2_knowledge_states(
            id TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL,
            PRIMARY KEY(id,version))''')
        store.conn.commit()
    def accept(self,p,identity,expected_version):
        # Resolve authorized registered evidence before locking. Checks must
        # bind the exact returned source versions; failures never fabricate them.
        row=self.store.get(p,identity)
        if not row['source_refs']:
            raise ConflictError('registered execution evidence required')
        if not any(ref['type']=='execution' for ref in row['source_refs']):
            raise ConflictError('execution evidence required')
        versions=self.resolve(p,row['source_refs'])
        if not isinstance(versions,dict) or len(versions)!=len({ref['id'] for ref in row['source_refs']}):
            raise ConflictError('unresolved sources')
        if set(versions)!={ref['id'] for ref in row['source_refs']}:
            raise ConflictError('source identities mismatch')
        if any(type(v) is not int or v<1 for v in versions.values()):
            raise ConflictError('invalid source versions')
        with self.store.conn:
            self.store.conn.execute('BEGIN IMMEDIATE')
            current=self.store.get(p,identity)
            if current['state'] not in ('draft','candidate'):
                raise ConflictError('lifecycle blocks candidate acceptance')
            if not self.checks.ready(p,identity,expected_version,versions):
                raise ConflictError('required exact-version checks incomplete')
            self.store.conn.execute('INSERT OR IGNORE INTO brain_v2_knowledge_states VALUES(?,?,?)',
                                    (identity,expected_version,'candidate'))
        return self.store.get(p,identity)
