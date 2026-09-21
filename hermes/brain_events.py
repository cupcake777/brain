"""Durable reference-only notification queue; delivery grants no decision authority."""
import json
import subprocess
import uuid

class ReferenceEvents:
    def __init__(self,store):
        self.store=store
        store.conn.execute('''CREATE TABLE IF NOT EXISTS brain_v2_reference_events(
          id TEXT PRIMARY KEY, workspace TEXT NOT NULL, project TEXT NOT NULL,
          kind TEXT NOT NULL, reference TEXT NOT NULL, state TEXT NOT NULL,
          attempts INTEGER NOT NULL, UNIQUE(workspace,project,kind,reference))'''); store.conn.commit()
    def emit(self,p,kind,reference):
        if kind not in ('awaiting-recovery','needs-decision','conflict','completed'): raise ValueError('invalid reference event')
        if not isinstance(reference,str) or not reference or len(reference)>128: raise ValueError('bounded reference identity required')
        with self.store.conn:
            self.store.conn.execute('INSERT OR IGNORE INTO brain_v2_reference_events VALUES(?,?,?,?,?,?,0)',
                (str(uuid.uuid4()),p.workspace,p.project,kind,reference,'pending'))
        return self.store.conn.execute('SELECT id FROM brain_v2_reference_events WHERE workspace=? AND project=? AND kind=? AND reference=?',
            (p.workspace,p.project,kind,reference)).fetchone()['id']
    def deliver_once(self,p,sender):
        row=self.store.conn.execute("SELECT * FROM brain_v2_reference_events WHERE workspace=? AND project=? AND state='pending' ORDER BY id LIMIT 1",(p.workspace,p.project)).fetchone()
        if row is None: return None
        payload={k:row[k] for k in ('id','workspace','project','kind','reference')}
        try:
            receipt=sender(payload)
            delivered=isinstance(receipt,dict) and type(receipt.get('delivered')) is int and receipt['delivered']>0
        except Exception:
            delivered=False
        state='delivered' if delivered else 'pending'
        with self.store.conn:
            self.store.conn.execute("UPDATE brain_v2_reference_events SET state=?,attempts=attempts+1 WHERE id=? AND state='pending'",(state,row['id']))
        return {'id':row['id'],'state':state}


class ANotifyReferenceSender:
    """Minimal authenticated anotify transport for reference-only events.

    The payload deliberately contains no knowledge text. A 2xx response is
    not enough: the response must explicitly report a positive delivery
    count. Notification receipt never performs a Brain state transition.
    """

    def __init__(self, url, *, token=None, timeout=5, runner=None):
        if not isinstance(url,str) or not url.startswith(('http://','https://')):
            raise ValueError('explicit anotify http(s) URL required')
        if type(timeout) not in (int,float) or not 0 < timeout <= 30:
            raise ValueError('bounded anotify timeout required')
        self.url=url; self.token=token; self.timeout=timeout
        self.runner=runner or subprocess.run

    def __call__(self,event):
        if not isinstance(event,dict) or set(event)!={'id','workspace','project','kind','reference'}:
            raise ValueError('reference-only event required')
        body=json.dumps({'event':'brain-reference','reference_event':event},sort_keys=True,separators=(',',':'))
        command=['curl','-sS','--max-time',str(self.timeout),'-X','POST',self.url,
                 '-H','Content-Type: application/json','-d',body,'-w','\n%{http_code}']
        if self.token:
            command.extend(['-H','Authorization: Bearer ' + self.token])
        completed=self.runner(command,capture_output=True,text=True,timeout=self.timeout+1)
        if completed.returncode != 0: return {'delivered':0}
        raw=completed.stdout or ''
        payload_text,separator,status_text=raw.rpartition('\n')
        if not separator: return {'delivered':0}
        try: status=int(status_text.strip())
        except ValueError: return {'delivered':0}
        if not 200 <= status < 300: return {'delivered':0}
        try: payload=json.loads(payload_text)
        except ValueError: return {'delivered':0}
        delivered=payload.get('delivered')
        return {'delivered':delivered if type(delivered) is int and delivered>0 else 0}
