"""Explicit conflict suspension; no automated semantic contradiction decisions."""
import json
import uuid
from hermes.event_store import UnauthorizedError, NotFoundError
from hermes.knowledge_history import RevisionGraph

class ConflictCases:
    def __init__(self,store,*,authorize):
        self.store=store; self.authorize=authorize; self.graph=RevisionGraph(store)
        store.conn.execute('''CREATE TABLE IF NOT EXISTS brain_v2_conflict_cases(
          id TEXT PRIMARY KEY,workspace TEXT NOT NULL,project TEXT NOT NULL,
          affected TEXT NOT NULL,state TEXT NOT NULL,decider TEXT)'''); store.conn.commit()
    def open(self,p,identities):
        if not isinstance(identities,list) or not 2<=len(set(identities))<=20:
            raise ValueError('bounded competing identities required')
        with self.store.conn:
            self.store.conn.execute('BEGIN IMMEDIATE')
            affected={}
            pending=[self.store.get(p,identity) for identity in identities]
            while pending:
                item=pending.pop()
                if item['id'] in affected: continue
                affected[item['id']]=item['version']
                for edge in self.store.conn.execute("SELECT child FROM brain_v2_revision_edges WHERE parent=? AND kind IN ('derived','parent','split','merge')",(item['revision_id'],)):
                    descendant=self.graph._revision(p,edge['child'])
                    current=self.store.get(p,descendant['id'])
                    if current['revision_id']==descendant['revision_id']: pending.append(current)
            identity=str(uuid.uuid4())
            self.store.conn.execute('INSERT INTO brain_v2_conflict_cases VALUES(?,?,?,?,?,NULL)',
                (identity,p.workspace,p.project,json.dumps(affected),'open'))
            for kid,version in affected.items():
                has_checks=self.store.conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='brain_v2_knowledge_checks'").fetchone()
                if has_checks:
                    cutoff=self.store.conn.execute('SELECT COALESCE(MAX(sequence),0) FROM brain_v2_knowledge_checks').fetchone()[0]
                    self.store.conn.execute('INSERT INTO brain_v2_check_invalidation VALUES(?,?,?) ON CONFLICT(id,version) DO UPDATE SET through_sequence=excluded.through_sequence',(kid,version,cutoff))
                self.store.conn.execute("INSERT INTO brain_v2_knowledge_states VALUES(?,?,'disputed') ON CONFLICT(id,version) DO UPDATE SET state='disputed'",(kid,version))
        return identity
    def resolve(self,p,case_id):
        if self.authorize(p) is not True: raise UnauthorizedError('authenticated human disposition required')
        with self.store.conn:
            self.store.conn.execute('BEGIN IMMEDIATE')
            case=self.store.conn.execute('SELECT * FROM brain_v2_conflict_cases WHERE id=?',(case_id,)).fetchone()
            if case is None: raise NotFoundError('conflict case missing')
            if (case['workspace'],case['project'])!=(p.workspace,p.project): raise UnauthorizedError('conflict scope mismatch')
            if case['state']=='resolved': return
            self.store.conn.execute("UPDATE brain_v2_conflict_cases SET state='resolved',decider=? WHERE id=?",(p.actor,case_id))
            for identity,version in json.loads(case['affected']).items():
                # Human disposition clears suspension, not verification gates.
                overlaps=False
                for other in self.store.conn.execute("SELECT affected FROM brain_v2_conflict_cases WHERE state='open' AND workspace=? AND project=?",(p.workspace,p.project)):
                    if json.loads(other['affected']).get(identity)==version: overlaps=True
                if not overlaps:
                    self.store.conn.execute("UPDATE brain_v2_knowledge_states SET state='draft' WHERE id=? AND version=?",(identity,version))
