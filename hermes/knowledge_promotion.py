"""Explicit promotion policy; unset values disable transitions."""
import time

class PromotionPolicy:
    def __init__(self,store,ledger,*,threshold=None,readiness=None,window_seconds=None,clock=time.time):
        if threshold is not None and (type(threshold) is not int or threshold<1):
            raise ValueError('positive explicit promotion threshold required')
        if window_seconds is not None and (type(window_seconds) is not int or window_seconds<1):
            raise ValueError('positive explicit window required')
        self.window_seconds=window_seconds; self.clock=clock
        self.store=store; self.ledger=ledger; self.threshold=threshold; self.readiness=readiness
    def promote(self,p,identity,version):
        if self.threshold is None or self.readiness is None:return False
        with self.store.conn:
            self.store.conn.execute('BEGIN IMMEDIATE')
            row=self.store.get(p,identity)
            if type(version) is not int or row['version']!=version or row['kind']!='experience' or row['state']!='candidate':
                return False
            if self.readiness(p,identity,version) is not True:return False
            since=self.clock()-self.window_seconds if self.window_seconds is not None else None
            if self.ledger.count(p,identity,version,since=since)<self.threshold:return False
            self.store.conn.execute("UPDATE brain_v2_knowledge_states SET state='formal' WHERE id=? AND version=? AND state='candidate'",(identity,version))
        return True
