"""Explicit archive lookup; numeric automatic archive policy intentionally unset."""
import secrets
import time
from hermes.event_store import UnauthorizedError
from hermes.knowledge_retrieval_v2 import retrieve

class InactivityPolicy:
    """Inactivity archive; unset cutoff disables transitions entirely.

    No universal hardcoded cutoff. Directives and protected rare-critical
    items are exempt. Archival is a lifecycle transition, never deletion.
    """
    def __init__(self,store,*,cutoff_seconds=None,clock=time.time):
        if cutoff_seconds is not None and (type(cutoff_seconds) is not int or cutoff_seconds<1):
            raise ValueError('positive explicit inactivity cutoff required')
        self.store=store; self.cutoff=cutoff_seconds; self.clock=clock
    def archive(self,p,identity,version,*,last_used_at):
        if self.cutoff is None: return False
        if type(last_used_at) not in (int,float) or last_used_at<0:
            raise ValueError('verified last-use timestamp required')
        with self.store.conn:
            self.store.conn.execute('BEGIN IMMEDIATE')
            row=self.store.get(p,identity)
            if type(version) is not int or row['version']!=version: return False
            if row['kind']=='directive' or row['protected']: return False
            if row['state'] not in ('draft','candidate','formal','deprecated'): return False
            if self.clock()-last_used_at < self.cutoff: return False
            self.store.conn.execute(
                "INSERT INTO brain_v2_knowledge_states VALUES(?,?,'archive') ON CONFLICT(id,version) DO UPDATE SET state='archive'",
                (identity,version))
        return True

class ArchiveSearch:
    def __init__(self,store,*,clock=time.time,ttl=120,directives=None):
        if type(ttl) is not int or ttl<1 or ttl>600: raise ValueError('invalid ticket lifetime')
        self.store=store; self.clock=clock; self.ttl=ttl; self.directives=directives
        store.conn.execute('''CREATE TABLE IF NOT EXISTS brain_v2_archive_tickets(
          token TEXT PRIMARY KEY, actor TEXT NOT NULL, workspace TEXT NOT NULL,
          project TEXT NOT NULL, query TEXT NOT NULL, expires REAL NOT NULL, used INTEGER NOT NULL)''')
        store.conn.commit()
    def normal_search(self,p,query):
        result=retrieve(self.store,p,query,directives=self.directives)
        result['archive_ticket']=None
        if not any(result[lane] for lane in ('directives','formal','candidates')):
            token=secrets.token_urlsafe(32)
            with self.store.conn:
                self.store.conn.execute('INSERT INTO brain_v2_archive_tickets VALUES(?,?,?,?,?,?,0)',
                   (token,p.actor,p.workspace,p.project,query,self.clock()+self.ttl))
            result['archive_ticket']=token
        return result
    def search(self,p,ticket,*,explicit=False):
        if explicit is not True: raise UnauthorizedError('explicit archive request required')
        with self.store.conn:
            self.store.conn.execute('BEGIN IMMEDIATE')
            row=self.store.conn.execute('SELECT * FROM brain_v2_archive_tickets WHERE token=?',(ticket,)).fetchone()
            if row is None or row['used'] or row['expires']<=self.clock():
                raise UnauthorizedError('invalid archive ticket')
            if (row['actor'],row['workspace'],row['project'])!=(p.actor,p.workspace,p.project):
                raise UnauthorizedError('archive scope mismatch')
            # Recheck normal results: a newly usable record cancels access.
            normal=retrieve(self.store,p,row['query'],directives=self.directives)
            if any(normal[lane] for lane in ('directives','formal','candidates')):
                raise UnauthorizedError('normal search has usable knowledge')
            self.store.conn.execute('UPDATE brain_v2_archive_tickets SET used=1 WHERE token=?',(ticket,))
            terms=row['query'].casefold().split()
            return [{**item,'requires_revalidation':True} for item in self.store.list_current(p)
                    if item['state']=='archive' and any(term in item['content'].casefold() for term in terms)][:10]
