"""Durable event extraction; provider output is proposed text, never authority."""
import json
import uuid
from hermes.event_store import UnauthorizedError

class ExtractionQueue:
    def __init__(self,store,*,event_reader):
        self.store=store; self.read=event_reader
        store.conn.execute('''CREATE TABLE IF NOT EXISTS brain_v2_extraction_jobs(
          id TEXT PRIMARY KEY, workspace TEXT NOT NULL, project TEXT NOT NULL,
          event_id TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL,
          error TEXT, UNIQUE(workspace,project,event_id))'''); store.conn.commit()
    def enqueue(self,p,event_id):
        event=self.read(p,event_id)
        if event['id']!=event_id or event['project_id']!=p.project:
            raise UnauthorizedError('event scope mismatch')
        with self.store.conn:
            self.store.conn.execute('INSERT OR IGNORE INTO brain_v2_extraction_jobs VALUES(?,?,?,?,?,0,NULL)',
                (str(uuid.uuid4()),p.workspace,p.project,event_id,'pending'))
        return self.store.conn.execute('SELECT id FROM brain_v2_extraction_jobs WHERE workspace=? AND project=? AND event_id=?',
            (p.workspace,p.project,event_id)).fetchone()['id']
    def run_once(self,p,provider):
        job=self.store.conn.execute("SELECT * FROM brain_v2_extraction_jobs WHERE workspace=? AND project=? AND state='pending' ORDER BY id LIMIT 1",
            (p.workspace,p.project)).fetchone()
        if job is None: return None
        try:
            event=self.read(p,job['event_id'])
            if event['project_id']!=p.project or event['id']!=job['event_id']:
                raise UnauthorizedError('event scope mismatch')
            proposed=provider(event)
            if not isinstance(proposed,list) or not 1<=len(proposed)<=10:
                raise ValueError('bounded extraction list required')
            for item in proposed:
                if not isinstance(item,dict) or not {'content'} <= set(item) or set(item)-{'content','source_refs'}:
                    raise ValueError('extraction can propose content and registered source associations only')
                refs=item.get('source_refs') or [{'type':'execution','id':job['event_id']}]
                if not isinstance(refs,list) or not refs:
                    raise ValueError('extraction requires source associations')
                if not any(ref.get('type')=='execution' and ref.get('id')==job['event_id'] for ref in refs if isinstance(ref,dict)):
                    raise ValueError('extraction must retain originating event')
                for ref in refs:
                    if not isinstance(ref,dict) or ref.get('id')!=job['event_id'] or ref.get('type')!='execution':
                        raise ValueError('hallucinated or unregistered source association')
                self.store._validate(item['content'],refs)
        except Exception:
            with self.store.conn:
                self.store.conn.execute("UPDATE brain_v2_extraction_jobs SET attempts=attempts+1,error='extraction-unavailable-or-invalid' WHERE id=?",(job['id'],))
            return {'id':job['id'],'state':'pending'}
        with self.store.conn:
            self.store.conn.execute('BEGIN IMMEDIATE')
            updated=self.store.conn.execute("UPDATE brain_v2_extraction_jobs SET state='completed',attempts=attempts+1,error=NULL WHERE id=? AND state='pending'",(job['id'],))
            if updated.rowcount==0: return None
            for item in proposed:
                identity=str(uuid.uuid4())
                refs=item.get('source_refs') or [{'type':'execution','id':job['event_id']}]
                self.store._insert(p,identity,1,item['content'],refs,'experience',False)
                self.store.conn.execute('INSERT INTO brain_v2_knowledge_current VALUES(?,1)',(identity,))
        return {'id':job['id'],'state':'completed'}
