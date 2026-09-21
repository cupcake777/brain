"""Explicit scoped directives. Authority callback is configured server-side.

No client authority boolean, automatic expiry, usage gate or scope expansion.
"""
import json
import sqlite3
import uuid
import time
from hermes.event_store import UnauthorizedError, ConflictError, _storage_privacy_scan, SensitiveRejectedError

class DirectiveStore:
    def __init__(self,path,*,authorize):
        self.authorize=authorize
        self.conn=sqlite3.connect(str(path)); self.conn.row_factory=sqlite3.Row
        self.conn.execute('''CREATE TABLE IF NOT EXISTS brain_v2_directives(
          id TEXT NOT NULL, version INTEGER NOT NULL, owner TEXT NOT NULL,
          workspace TEXT NOT NULL, project TEXT NOT NULL, content TEXT NOT NULL,
          PRIMARY KEY(id,version))'''); self.conn.commit()
    def issue(self,p,content,*,identity=None,expected_version=None):
        if self.authorize(p) is not True: raise UnauthorizedError('authenticated directive authority required')
        if not isinstance(content,str) or not content.strip() or len(content)>8000: raise ValueError('bounded directive required')
        if _storage_privacy_scan({'content':content}): raise SensitiveRejectedError()
        with self.conn:
            self.conn.execute('BEGIN IMMEDIATE')
            if identity is None:
                if expected_version is not None: raise ConflictError('new directive has no prior version')
                identity=str(uuid.uuid4()); version=1
            else:
                history=self.history(p,identity)
                if not history: raise UnauthorizedError('directive not authorized')
                prior=history[-1]
                if prior['owner']!=p.actor: raise UnauthorizedError('directive owner mismatch')
                if type(expected_version) is not int or prior['version']!=expected_version: raise ConflictError('stale directive')
                version=expected_version+1
            self.conn.execute('INSERT INTO brain_v2_directives VALUES(?,?,?,?,?,?)',
                              (identity,version,p.actor,p.workspace,p.project,content))
        return dict(id=identity,version=version,owner=p.actor,workspace=p.workspace,project=p.project,content=content,kind='directive',state='formal',protected=True)
    def history(self,p,identity):
        rows=self.conn.execute('SELECT * FROM brain_v2_directives WHERE id=? ORDER BY version',(identity,)).fetchall()
        if rows and (rows[0]['workspace'],rows[0]['project'])!=(p.workspace,p.project): raise UnauthorizedError('directive scope mismatch')
        return [dict(row) for row in rows]
    def list_active(self,p):
        return [{**dict(row),'kind':'directive','state':'formal','protected':True} for row in self.conn.execute(
           'SELECT d.* FROM brain_v2_directives d WHERE workspace=? AND project=? AND version=(SELECT MAX(version) FROM brain_v2_directives x WHERE x.id=d.id)',(p.workspace,p.project))]
    def close(self): self.conn.close()

class VerifiedUseLedger:
    """Internal trusted verification ledger; never accepts self-reported applied.

    Promotion remains disabled until threshold/window policy is approved.
    """
    promotion_threshold = None
    def __init__(self,store,*,verifier,clock=time.time):
        self.store=store; self.verify=verifier; self.clock=clock
        store.conn.execute('''CREATE TABLE IF NOT EXISTS brain_v2_verified_use(
            id TEXT NOT NULL, version INTEGER NOT NULL, task TEXT NOT NULL,
            execution TEXT NOT NULL, PRIMARY KEY(id,version,task))''')
        columns={r[1] for r in store.conn.execute('PRAGMA table_info(brain_v2_verified_use)')}
        if 'verified_at' not in columns:
            store.conn.execute('ALTER TABLE brain_v2_verified_use ADD COLUMN verified_at REAL')
        store.conn.commit()
    def record(self,p,identity,version,task_id,execution_id):
        if not isinstance(task_id,str) or not task_id or len(task_id)>128:
            raise ValueError('bounded task identity required')
        if not isinstance(execution_id,str) or not execution_id or len(execution_id)>128:
            raise ValueError('bounded execution identity required')
        proof=self.verify(p,execution_id)
        if not isinstance(proof,dict) or proof.get('verified') is not True or proof.get('classification')!='production':
            return False
        if (proof.get('knowledge_id'),proof.get('version'),proof.get('task_id'),proof.get('execution_id'))!=(identity,version,task_id,execution_id):
            return False
        if type(version) is not int or type(proof.get('version')) is not int:
            return False
        with self.store.conn:
            self.store.conn.execute('BEGIN IMMEDIATE')
            current=self.store.get(p,identity)
            if current['version']!=version: return False
            inserted=self.store.conn.execute('INSERT OR IGNORE INTO brain_v2_verified_use(id,version,task,execution,verified_at) VALUES(?,?,?,?,?)',
                                             (identity,version,task_id,execution_id,self.clock()))
            return inserted.rowcount==1
    def count(self,p,identity,version,*,since=None):
        self.store.get(p,identity,version)
        return self.store.conn.execute('SELECT COUNT(*) FROM brain_v2_verified_use WHERE id=? AND version=? AND (? IS NULL OR verified_at>=?)',
                                        (identity,version,since,since)).fetchone()[0]
