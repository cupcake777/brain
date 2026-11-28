"""Attributed topic membership and typed, version-bound editorial relationships.

A shared topic is an index, not evidence that two claims are equivalent. Relations
are recommendations based on recorded comparisons; they never merge or approve.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from uuid import uuid4

from .review_notes import ReviewNotes

RELATIONS = {
    'duplicate_of': ('建议并入', '待并入此条'),
    'conflicts_with': ('存在冲突', '存在冲突'),
    'refines': ('补充或收窄', '相关补充'),
    'related_to': ('相关背景', '相关背景'),
}


class EditorialRelations:
    def __init__(self, repo, notes: ReviewNotes | None = None):
        self.repo = repo
        self.notes = notes or ReviewNotes(repo)
        with repo._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS editorial_relationship_retirements (
                relation_id TEXT PRIMARY KEY, reasoning TEXT NOT NULL,
                reviewer TEXT NOT NULL, session_id TEXT NOT NULL, retired_at TEXT NOT NULL)''')
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS editorial_topics (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS editorial_topic_members (
                    id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES editorial_topics(id),
                    entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, content_digest TEXT NOT NULL,
                    reviewer TEXT NOT NULL, session_id TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS editorial_member_entity ON editorial_topic_members(entity_type,entity_id,created_at);
                CREATE TABLE IF NOT EXISTS editorial_relationships (
                    id TEXT PRIMARY KEY, source_type TEXT NOT NULL, source_id TEXT NOT NULL,
                    target_type TEXT NOT NULL, target_id TEXT NOT NULL,
                    source_digest TEXT NOT NULL, target_digest TEXT NOT NULL,
                    relation TEXT NOT NULL, reasoning TEXT NOT NULL, evidence TEXT NOT NULL,
                    reviewer TEXT NOT NULL, session_id TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS editorial_relation_source ON editorial_relationships(source_type,source_id);
                CREATE INDEX IF NOT EXISTS editorial_relation_target ON editorial_relationships(target_type,target_id);
            ''')

    @staticmethod
    def _entity(conn, kind, entity_id):
        if kind not in {'proposal', 'knowledge'}:
            raise ValueError('invalid entity type')
        table, key = ('proposals', 'proposal_id') if kind == 'proposal' else ('knowledge_nodes', 'id')
        row = conn.execute(f'SELECT * FROM {table} WHERE {key}=?', (entity_id,)).fetchone()
        if row is None:
            raise ValueError('relationship target no longer exists')
        return dict(row)

    def _check(self, conn, kind, entity_id, expected):
        item = self._entity(conn, kind, entity_id)
        if self.notes._digest(kind, item, conn) != expected:
            raise ValueError('content changed since comparison')
        return item

    def add_topic(self, topic_id, title, description):
        if not all(isinstance(v, str) and v.strip() for v in (topic_id,title,description)):
            raise ValueError('topic identity and description are required')
        with self.repo._connect() as conn:
            conn.execute('INSERT OR IGNORE INTO editorial_topics VALUES (?,?,?)', (topic_id,title,description))
            current = conn.execute('SELECT title,description FROM editorial_topics WHERE id=?',(topic_id,)).fetchone()
            if tuple(current) != (title, description):
                raise ValueError('existing topic differs')

    def assign(self, topic_id, kind, entity_id, *, expected_digest, reviewer, session_id):
        if not all(isinstance(v,str) and v.strip() for v in (reviewer,session_id)):
            raise ValueError('review identity is required')
        with self.repo._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._check(conn,kind,entity_id,expected_digest)
            previous = conn.execute('SELECT * FROM editorial_topic_members WHERE entity_type=? AND entity_id=? ORDER BY created_at DESC,id DESC LIMIT 1', (kind,entity_id)).fetchone()
            if previous and previous['topic_id']==topic_id and previous['content_digest']==expected_digest:
                return previous['id']
            member_id = str(uuid4())
            conn.execute('INSERT INTO editorial_topic_members VALUES (?,?,?,?,?,?,?,?)',
                         (member_id,topic_id,kind,entity_id,expected_digest,reviewer,session_id,datetime.now(timezone.utc).isoformat()))
            return member_id

    def link(self, source_type, source_id, target_type, target_id, relation, *, source_digest,
             target_digest, reasoning, evidence, reviewer, session_id):
        if relation not in RELATIONS or (source_type,source_id)==(target_type,target_id):
            raise ValueError('invalid relation')
        if not all(isinstance(v,str) and v.strip() for v in (reasoning,reviewer,session_id)) or not isinstance(evidence,list) or not evidence:
            raise ValueError('comparison reasoning, evidence and identity are required')
        # Symmetric claims get one canonical row; directed merge suggestions keep direction.
        if relation in {'conflicts_with','related_to'} and (source_type,source_id)>(target_type,target_id):
            source_type,target_type=target_type,source_type
            source_id,target_id=target_id,source_id
            source_digest,target_digest=target_digest,source_digest
        with self.repo._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._check(conn,source_type,source_id,source_digest)
            self._check(conn,target_type,target_id,target_digest)
            previous=conn.execute('SELECT id FROM editorial_relationships WHERE source_type=? AND source_id=? AND target_type=? AND target_id=? AND relation=? AND source_digest=? AND target_digest=?',
                                  (source_type,source_id,target_type,target_id,relation,source_digest,target_digest)).fetchone()
            if previous:return previous['id']
            rid=str(uuid4())
            conn.execute('INSERT INTO editorial_relationships VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (rid,source_type,source_id,target_type,target_id,source_digest,target_digest,relation,reasoning,
                 json.dumps(evidence,ensure_ascii=False),reviewer,session_id,datetime.now(timezone.utc).isoformat()))
            return rid

    def retire(self, relation_id, *, reasoning, reviewer, session_id):
        """Withdraw a reviewed comparison without erasing its original evidence."""
        if not all(isinstance(v, str) and v.strip() for v in (relation_id, reasoning, reviewer, session_id)):
            raise ValueError('relation identity, reasoning and reviewer are required')
        with self.repo._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if not conn.execute('SELECT 1 FROM editorial_relationships WHERE id=?', (relation_id,)).fetchone():
                raise ValueError('reviewed relationship no longer exists')
            conn.execute('INSERT OR IGNORE INTO editorial_relationship_retirements VALUES (?,?,?,?,?)',
                (relation_id, reasoning, reviewer, session_id, datetime.now(timezone.utc).isoformat()))

    def snapshot(self):
        """Batch-load both endpoints and reject stale notes/edges on either side."""
        with self.repo._connect() as conn:
            entities = {}
            for kind,table,key in [('proposal','proposals','proposal_id'),('knowledge','knowledge_nodes','id')]:
                for row in conn.execute(f'SELECT * FROM {table}'):
                    item=dict(row)
                    entities[(kind,str(item[key]))]=item
            digests={key:self.notes._digest(key[0],item,conn) for key,item in entities.items()}
            reviews={}
            for row in conn.execute('SELECT * FROM editorial_reviews ORDER BY reviewed_at,id'):
                note=dict(row);reviews[(note['entity_type'],note['entity_id'])]=note
            for key,item in entities.items():
                note=reviews.get(key)
                item['editorial_review']=note if note and note['content_digest']==digests[key] else None
                item['review_outdated']=bool(note and not item['editorial_review'])
            topics={r['id']:dict(r) for r in conn.execute('SELECT * FROM editorial_topics ORDER BY title,id')}
            memberships={}
            for row in conn.execute('SELECT * FROM editorial_topic_members ORDER BY created_at,id'):
                memberships[(row['entity_type'],row['entity_id'])]=dict(row)
            for key,member in memberships.items():
                if member['content_digest']!=digests.get(key):continue
                if key in entities:entities[key]['topic']=topics.get(member['topic_id'])
            retired={r[0] for r in conn.execute('SELECT relation_id FROM editorial_relationship_retirements')}
            by_entity=defaultdict(list);edges=[];stale=0
            for row in conn.execute('SELECT * FROM editorial_relationships ORDER BY created_at,id'):
                if row['id'] in retired:continue
                edge=dict(row);source=(edge['source_type'],edge['source_id']);target=(edge['target_type'],edge['target_id'])
                if edge['source_digest']!=digests.get(source) or edge['target_digest']!=digests.get(target):
                    stale+=1;continue
                edges.append(edge)
                for index,(mine,other) in enumerate([(source,target),(target,source)]):
                    by_entity[mine].append({**edge,'other_type':other[0],'other_id':other[1],
                        'other':entities[other], 'outgoing':index==0,'label':RELATIONS[edge['relation']][index]})
        return {'entities':entities,'topics':topics,'by_entity':dict(by_entity),'edges':edges,'stale':stale}

    @staticmethod
    def decorate(snapshot, kind, items):
        result=[]
        for item in items:
            item=dict(item);key=(kind,str(item.get('proposal_id') if kind=='proposal' else item.get('id')))
            current=snapshot['entities'].get(key,{})
            for name in ('editorial_review','review_outdated','topic'):
                item[name]=current.get(name)
            item['relationships']=snapshot['by_entity'].get(key,[])
            result.append(item)
        return result
