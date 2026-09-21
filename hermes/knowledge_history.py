"""Typed revision ancestry, independent from topical similarity edges."""
from hermes.event_store import UnauthorizedError, NotFoundError

class RevisionGraph:
    def __init__(self,store):
        self.store=store
        store.conn.execute('''CREATE TABLE IF NOT EXISTS brain_v2_revision_edges(
          child TEXT NOT NULL,parent TEXT NOT NULL,kind TEXT NOT NULL,
          PRIMARY KEY(child,parent,kind))'''); store.conn.commit()
    def _revision(self,p,revision):
        row=self.store.conn.execute('SELECT id,version FROM brain_v2_knowledge_revisions WHERE revision_id=?',(revision,)).fetchone()
        if row is None: raise NotFoundError('parent revision unavailable')
        return self.store.get(p,row['id'],row['version'])
    def link(self,p,child,parent,kind):
        if kind not in ('parent','derived','split','merge','replaces'): raise ValueError('invalid ancestry type')
        with self.store.conn:
            self.store.conn.execute('BEGIN IMMEDIATE')
            self._revision(p,child); self._revision(p,parent)
            pending=[parent]; seen=set()
            while pending:
                node=pending.pop()
                if node==child: raise ValueError('revision cycle')
                if node in seen: continue
                seen.add(node)
                pending.extend(row['parent'] for row in self.store.conn.execute('SELECT parent FROM brain_v2_revision_edges WHERE child=?',(node,)))
            self.store.conn.execute('INSERT OR IGNORE INTO brain_v2_revision_edges VALUES(?,?,?)',(child,parent,kind))
    def parents(self,p,revision):
        self._revision(p,revision)
        return [dict(row) for row in self.store.conn.execute('SELECT parent,kind FROM brain_v2_revision_edges WHERE child=? ORDER BY parent,kind',(revision,))]
