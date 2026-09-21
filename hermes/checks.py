"""Immutable exact-version check history; trusted internal verifier interface."""
import json
from hermes.event_store import ConflictError

class CheckLedger:
    def __init__(self,store,*,required,policy_version):
        if not required or len(set(required)) != len(required) or not policy_version:
            raise ValueError('explicit required checks and policy required')
        self.store=store
        self.required=tuple(required)
        self.policy_version=policy_version
        store.conn.execute('''CREATE TABLE IF NOT EXISTS brain_v2_knowledge_checks(
          sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL,
          version INTEGER NOT NULL, digest TEXT NOT NULL, policy TEXT NOT NULL,
          name TEXT NOT NULL, status TEXT NOT NULL, sources TEXT NOT NULL)''')
        store.conn.execute('''CREATE TABLE IF NOT EXISTS brain_v2_check_invalidation(
          id TEXT NOT NULL, version INTEGER NOT NULL, through_sequence INTEGER NOT NULL,
          PRIMARY KEY(id,version))''')
        store.conn.commit()
    def record(self,p,identity,version,name,status,digest,source_versions):
        if name not in self.required or status not in ('passed','failed','pending','error'):
            raise ValueError('invalid check')
        sources=json.dumps(source_versions,sort_keys=True,separators=(',',':'),allow_nan=False)
        with self.store.conn:
            self.store.conn.execute('BEGIN IMMEDIATE')
            current=self.store.get(p,identity)
            if type(version) is not int or current['version']!=version or current['digest']!=digest:
                raise ConflictError('check must bind current exact revision')
            self.store.conn.execute('INSERT INTO brain_v2_knowledge_checks(id,version,digest,policy,name,status,sources) VALUES(?,?,?,?,?,?,?)',
                                   (identity,version,digest,self.policy_version,name,status,sources))
    def ready(self,p,identity,version,source_versions):
        current=self.store.get(p,identity)
        if type(version) is not int or current['version']!=version:
            return False
        sources=json.dumps(source_versions,sort_keys=True,separators=(',',':'),allow_nan=False)
        latest={}
        invalidation=self.store.conn.execute('SELECT through_sequence FROM brain_v2_check_invalidation WHERE id=? AND version=?',(identity,version)).fetchone()
        cutoff=invalidation[0] if invalidation is not None else 0
        for row in self.store.conn.execute('SELECT name,status,sources FROM brain_v2_knowledge_checks WHERE id=? AND version=? AND digest=? AND policy=? AND sequence>? ORDER BY sequence',
                                         (identity,version,current['digest'],self.policy_version,cutoff)):
            latest[row['name']]=(row['status'],row['sources'])
        return all(latest.get(name)==('passed',sources) for name in self.required)
