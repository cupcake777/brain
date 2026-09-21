"""Scoped immutable knowledge revision persistence; no automatic acceptance."""
import json
import sqlite3
import uuid
from hermes.contracts import canonical_digest
from hermes.event_store import ConflictError, UnauthorizedError, NotFoundError, _storage_privacy_scan, SensitiveRejectedError

class KnowledgeStore:
    def __init__(self, path):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS brain_v2_knowledge_revisions(
          id TEXT NOT NULL, version INTEGER NOT NULL, revision_id TEXT UNIQUE NOT NULL,
          workspace TEXT NOT NULL, project TEXT NOT NULL, payload TEXT NOT NULL,
          PRIMARY KEY(id,version));
        CREATE TABLE IF NOT EXISTS brain_v2_revision_edges(
          child TEXT NOT NULL,parent TEXT NOT NULL,kind TEXT NOT NULL,
          PRIMARY KEY(child,parent,kind));
        CREATE TABLE IF NOT EXISTS brain_v2_knowledge_states(
          id TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL,
          PRIMARY KEY(id,version));
        CREATE TABLE IF NOT EXISTS brain_v2_knowledge_current(
          id TEXT PRIMARY KEY, version INTEGER NOT NULL);
        ''')
    def _validate(self, content, source_refs):
        if not isinstance(content, str) or not content.strip() or len(content)>8000:
            raise ValueError('bounded nonblank content required')
        if not isinstance(source_refs,list) or len(source_refs)>100:
            raise ValueError('bounded source references required')
        from hermes.contracts import SourceRef
        for reference in source_refs:
            SourceRef.model_validate(reference)
        if _storage_privacy_scan({'content':content,'source_refs':source_refs}):
            raise SensitiveRejectedError()
    def _insert(self, p, identity, version, content, source_refs, kind, protected):
        self._validate(content,source_refs)
        row = dict(id=identity,version=version,revision_id=str(uuid.uuid4()),workspace=p.workspace,
                   project=p.project,kind=kind,content=content,source_refs=source_refs,
                   state='draft',protected=protected)
        row['digest']=canonical_digest(row)
        self.conn.execute('INSERT INTO brain_v2_knowledge_revisions VALUES(?,?,?,?,?,?)',
                          (identity,version,row['revision_id'],p.workspace,p.project,json.dumps(row)))
        return row
    def create(self,p,content,source_refs,kind='experience',protected=False,parents=None):
        if kind!='experience' or parents:
            raise ValueError('directive and ancestry require dedicated checked workflow')
        identity=str(uuid.uuid4())
        with self.conn:
            row=self._insert(p,identity,1,content,source_refs,kind,protected)
            self.conn.execute('INSERT INTO brain_v2_knowledge_current VALUES(?,1)',(identity,))
        return row
    def get(self,p,identity,version=None):
        if version is None:
            current=self.conn.execute('SELECT version FROM brain_v2_knowledge_current WHERE id=?',(identity,)).fetchone()
            if current is None: raise NotFoundError('knowledge not found')
            version=current['version']
        row=self.conn.execute('SELECT * FROM brain_v2_knowledge_revisions WHERE id=? AND version=?',(identity,version)).fetchone()
        if row is None: raise NotFoundError('revision not found')
        if (row['workspace'],row['project'])!=(p.workspace,p.project):
            raise UnauthorizedError('knowledge scope mismatch')
        result = json.loads(row['payload'])
        lifecycle = self.conn.execute('SELECT state FROM brain_v2_knowledge_states WHERE id=? AND version=?',
                                      (identity, version)).fetchone()
        if lifecycle is not None:
            result['state'] = lifecycle['state']
        return result
    def revise(self,p,identity,expected_version,content,source_refs,parents=None):
        if type(expected_version) is not int or parents: raise ValueError('invalid revision input')
        with self.conn:
            self.conn.execute('BEGIN IMMEDIATE')
            prior=self.get(p,identity)
            if prior['state']=='disputed':
                raise ConflictError('unresolved conflict requires authorized disposition')
            if prior['version']!=expected_version: raise ConflictError('stale revision')
            row=self._insert(p,identity,expected_version+1,content,source_refs,prior['kind'],prior['protected'])
            self.conn.execute('INSERT INTO brain_v2_revision_edges VALUES(?,?,?)',
                              (row['revision_id'],prior['revision_id'],'parent'))
            self.conn.execute('UPDATE brain_v2_knowledge_current SET version=? WHERE id=? AND version=?',
                              (row['version'],identity,expected_version))
        return row
    def history(self,p,identity):
        self.get(p,identity)
        return [json.loads(row['payload']) for row in self.conn.execute(
            'SELECT payload FROM brain_v2_knowledge_revisions WHERE id=? ORDER BY version',(identity,))]
    def list_current(self,p):
        return [self.get(p,row['id'],row['version']) for row in self.conn.execute(
            'SELECT r.id,r.version FROM brain_v2_knowledge_current c JOIN brain_v2_knowledge_revisions r ON c.id=r.id AND c.version=r.version WHERE workspace=? AND project=?',(p.workspace,p.project))]
    def close(self): self.conn.close()
