"""Execute explicit, independent proposal reviews with atomic audit records.

Content and applicability digests bind every decision to what was reviewed.
No model calls or inferred approvals occur while applying a plan.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from uuid import NAMESPACE_URL, uuid4, uuid5

from .editorial_relations import EditorialRelations
from .environment_scope import assign, get_scope
from .review_notes import ReviewNotes

ACTIONS = {'retain_db', 'refine', 'supersede', 'archive'}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class ProposalCuration:
    def __init__(self, repo):
        self.repo = repo
        self.notes = ReviewNotes(repo)
        EditorialRelations(repo, self.notes)

    def prepare(self, *, reviewer, session_id):
        if not reviewer.strip() or not session_id.strip():
            raise ValueError('reviewer and real session_id are required')
        with self.repo._connect() as conn:
            decisions = []
            for row in conn.execute("SELECT * FROM proposals WHERE state='pending' ORDER BY inserted_at,proposal_id"):
                item = dict(row)
                decisions.append(dict(proposal_id=item['proposal_id'],
                    expected_digest=self.notes._digest('proposal', item, conn), action='', reason='',
                    evidence_assessment='', related_proposal_id='', related_knowledge_id='',
                    target_digest='', proposed_memory='', environment=None))
        return dict(schema=1, plan_id=str(uuid4()), reviewer=reviewer, session_id=session_id, decisions=decisions)

    def validate(self, conn, plan):
        if plan.get('schema') != 1 or not all(isinstance(plan.get(k), str) and plan[k].strip()
                for k in ('plan_id', 'reviewer', 'session_id')):
            raise ValueError('plan identity is required')
        decisions = plan.get('decisions')
        if not isinstance(decisions, list) or not decisions:
            raise ValueError('nonempty reviewed decisions are required')
        ids = [d.get('proposal_id') for d in decisions]
        if not all(isinstance(x, str) and x for x in ids) or len(set(ids)) != len(ids):
            raise ValueError('duplicate or missing proposal_id')
        by_id, items = {d['proposal_id']: d for d in decisions}, {}
        for d in decisions:
            if d.get('action') not in ACTIONS or not all(isinstance(d.get(k), str) and d[k].strip()
                    for k in ('reason', 'evidence_assessment', 'expected_digest')):
                raise ValueError('explicit decision, evidence assessment and digest are required')
            row = conn.execute('SELECT * FROM proposals WHERE proposal_id=?', (d['proposal_id'],)).fetchone()
            if row is None or row['state'] != 'pending':
                raise ValueError('proposal is no longer pending')
            item = dict(row)
            if item['source_agent'].casefold() == plan['reviewer'].casefold():
                raise ValueError('proposal author must not approve their own submission')
            if self.notes._digest('proposal', item, conn) != d['expected_digest']:
                raise ValueError('proposal content or scope changed since review')
            if d['action'] in {'retain_db', 'refine'} and not str(item['evidence']).strip():
                raise ValueError('retained knowledge requires submitted evidence')
            if d['action'] == 'refine' and not str(d.get('proposed_memory') or '').strip():
                raise ValueError('refine requires complete proposed_memory')
            if d.get('relation', 'related_to') not in {'related_to', 'refines', 'conflicts_with'}:
                raise ValueError('invalid reviewed relation')
            if not isinstance(d.get('additional_evidence', []), list):
                raise ValueError('additional_evidence must be a list')
            if d.get('environment') is not None:
                env = d['environment']
                if not isinstance(env, dict) or not isinstance(env.get('server_id'), str) or not env['server_id'].strip():
                    raise ValueError('explicit environment server_id is required')
            pid, nid = d.get('related_proposal_id'), d.get('related_knowledge_id')
            if pid and nid:
                raise ValueError('choose one exact comparison target')
            if d['action'] == 'supersede' and not (pid or nid):
                raise ValueError('supersede requires a retained canonical target')
            if pid or nid:
                kind, table, key, identity = ('proposal', 'proposals', 'proposal_id', pid) if pid else ('knowledge', 'knowledge_nodes', 'id', nid)
                target = conn.execute(f'SELECT * FROM {table} WHERE {key}=?', (identity,)).fetchone()
                if target is None or (kind == 'proposal' and identity == item['proposal_id']):
                    raise ValueError('comparison target missing or self-referential')
                target = dict(target)
                if self.notes._digest(kind, target, conn) != d.get('target_digest'):
                    raise ValueError('comparison target changed since review')
                if target.get('stage') == 'deprecated':
                    raise ValueError('canonical knowledge is deprecated')
                if d['action'] == 'supersede' and pid:
                    target_action = by_id.get(pid, {}).get('action')
                    if target['state'] not in {'approved_db_only', 'approved_for_export'} and target_action not in {'retain_db', 'refine'}:
                        raise ValueError('canonical proposal must be retained without duplicate chains')
                    if target['state'] != 'pending':
                        link = conn.execute('SELECT knowledge_id FROM proposal_knowledge_links WHERE proposal_id=?', (pid,)).fetchone()
                        if not link:
                            raise ValueError('canonical proposal has no materialized knowledge')
                        canonical = conn.execute('SELECT * FROM knowledge_nodes WHERE id=?', (link['knowledge_id'],)).fetchone()
                        if canonical is None or canonical['stage'] == 'deprecated':
                            raise ValueError('canonical knowledge is missing or deprecated')
                        if d.get('canonical_knowledge_id') != link['knowledge_id'] or d.get('canonical_knowledge_digest') != self.notes._digest('knowledge', dict(canonical), conn):
                            raise ValueError('canonical knowledge link, content or scope changed since review')
            items[item['proposal_id']] = item
        return items

    def apply(self, plan, *, dry_run=True):
        digest = hashlib.sha256(encoded(plan).encode()).hexdigest()
        with self.repo._connect() as conn:
            conn.execute('BEGIN' if dry_run else 'BEGIN IMMEDIATE')
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='proposal_curation_batches'").fetchone()
            previous = conn.execute('SELECT plan_digest,result FROM proposal_curation_batches WHERE plan_id=?',
                (plan.get('plan_id'),)).fetchone() if exists else None
            if previous:
                if previous['plan_digest'] != digest:
                    raise ValueError('applied plan_id was reused with different decisions')
                return {**json.loads(previous['result']), 'replayed': True}
            items = self.validate(conn, plan)
            result = dict(plan_id=plan['plan_id'], reviewed=len(items),
                actions=dict(Counter(d['action'] for d in plan['decisions'])),
                dry_run=dry_run, replayed=False, knowledge_created=0)
            if dry_run:
                return result
            conn.execute('''CREATE TABLE IF NOT EXISTS proposal_curation_batches (
                plan_id TEXT PRIMARY KEY, plan_digest TEXT NOT NULL, reviewer TEXT NOT NULL,
                session_id TEXT NOT NULL, plan TEXT NOT NULL, result TEXT NOT NULL, applied_at TEXT NOT NULL)''')
            now = datetime.now(timezone.utc).isoformat()
            created_nodes = {}
            for d in plan['decisions']:
                p = items[d['proposal_id']]
                if d.get('environment') is not None:
                    assign(conn, 'proposal', p['proposal_id'], d['environment'], 'independent-agent-review')
                # Refresh the existing navigation membership only after an explicit scope review.
                topic = conn.execute("SELECT topic_id FROM editorial_topic_members WHERE entity_type='proposal' AND entity_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (p['proposal_id'],)).fetchone()
                if topic and d.get('environment') is not None:
                    conn.execute('INSERT INTO editorial_topic_members VALUES (?,?,?,?,?,?,?,?)',
                        (str(uuid4()), topic['topic_id'], 'proposal', p['proposal_id'], self.notes._digest('proposal', p, conn), plan['reviewer'], plan['session_id'], now))
                if d['action'] not in {'retain_db', 'refine'}:
                    continue
                nid = str(uuid5(NAMESPACE_URL, 'brain:curated:' + p['proposal_id']))
                content = str(d.get('proposed_memory') or p['suggested_memory']).strip()
                evidence = [dict(source_type='stored_proposal', source_uri='brain://proposal/' + p['proposal_id'],
                    quoted_excerpt=p['evidence'], assessment=d['evidence_assessment'])]
                for duplicate in plan['decisions']:
                    if duplicate['action'] == 'supersede' and duplicate.get('related_proposal_id') == p['proposal_id']:
                        original = items[duplicate['proposal_id']]
                        evidence.append(dict(source_type='stored_proposal', source_uri='brain://proposal/' + original['proposal_id'],
                            quoted_excerpt=original['evidence'], assessment=duplicate['evidence_assessment']))
                node = dict(id=nid, parent_id=None, content=content, summary=d.get('title_zh') or p['summary'][:240],
                    category=p['category'], domain=p['domain'], stage='refined', operation='refine', confidence=0.6,
                    source='proposal:' + p['proposal_id'][:12], evidence=encoded(evidence + d.get('additional_evidence', [])), supersedes=None,
                    merged_from='[]', contradicts='[]', verified_by='[]', created_at=now, refined_at=now,
                    verified_at=None, deprecated_at=None, retrieval_count=0, last_used_at=None, correction_count=0,
                    outcome_count=0, last_outcome_at=None, kind=p['category'], trigger_terms='[]',
                    use_when=d.get('scope_requirement') or p['scope'], avoid_when='', success_signal='', failure_signal='')
                conn.execute('INSERT INTO knowledge_nodes (' + ','.join(node) + ') VALUES (' + ','.join('?' for _ in node) + ')', tuple(node.values()))
                created_nodes[p['proposal_id']] = nid
                self.repo._replace_knowledge_fts(conn, nid, node['summary'], content, node['category'], node['domain'])
                scope = get_scope(conn, 'proposal', p['proposal_id'])
                if scope['server_id']:
                    assign(conn, 'knowledge', nid, scope, scope['attribution'])
                conn.execute('INSERT INTO proposal_knowledge_links VALUES (?,?,?,?)', (p['proposal_id'], nid, 'independent_review_refine' if d['action'] == 'refine' else 'independent_review', now))
                conn.execute("UPDATE proposals SET state='approved_db_only' WHERE proposal_id=?", (p['proposal_id'],))
                conn.execute('INSERT INTO thought_chains VALUES (?,?,?,?,?,?,?,?)',
                    (str(uuid4()), nid, 'refine', d['reason'], encoded(evidence), 'retain_db', 0.6, now))
                topic = conn.execute("SELECT topic_id FROM editorial_topic_members WHERE entity_type='proposal' AND entity_id=? ORDER BY created_at DESC LIMIT 1", (p['proposal_id'],)).fetchone()
                if topic:
                    conn.execute('INSERT INTO editorial_topic_members VALUES (?,?,?,?,?,?,?,?)',
                        (str(uuid4()), topic['topic_id'], 'knowledge', nid, self.notes._digest('knowledge', node, conn), plan['reviewer'], plan['session_id'], now))
                conn.execute('INSERT INTO editorial_reviews VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (str(uuid4()), 'knowledge', nid, self.notes._digest('knowledge', node, conn), plan['reviewer'], plan['session_id'],
                     node['summary'], content[:400], 'retain', d['reason'],
                     '保留提交证据；按适用范围检索，后续任务继续验证。', p['proposal_id'], 'submitted_text_only', now))
                result['knowledge_created'] += 1
            for d in plan['decisions']:
                p = items[d['proposal_id']]
                pid, nid = d.get('related_proposal_id'), d.get('related_knowledge_id')
                if d['action'] == 'archive':
                    conn.execute("UPDATE proposals SET state='rejected' WHERE proposal_id=?", (p['proposal_id'],))
                elif d['action'] == 'supersede':
                    if pid:
                        nid = conn.execute('SELECT knowledge_id FROM proposal_knowledge_links WHERE proposal_id=?', (pid,)).fetchone()['knowledge_id']
                    conn.execute("UPDATE proposals SET state='superseded',semantic_duplicate_of=? WHERE proposal_id=?", (pid or None, p['proposal_id']))
                    conn.execute('INSERT INTO proposal_knowledge_links VALUES (?,?,?,?)', (p['proposal_id'], nid, 'reviewed_duplicate', now))
                current = dict(conn.execute('SELECT * FROM proposals WHERE proposal_id=?', (p['proposal_id'],)).fetchone())
                disposition = dict(retain_db='retain', refine='scope', archive='archive', supersede='merge')[d['action']]
                next_step = dict(retain_db='已入库，按适用范围检索；导出另行批准。', refine='已收窄后入库；保留原始提案和证据。',
                    archive='已归档原始记录；补齐所述证据后可重新提交。', supersede='已关联保留对象，停止重复入库。')[d['action']]
                conn.execute('INSERT INTO editorial_reviews VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (str(uuid4()), 'proposal', p['proposal_id'], self.notes._digest('proposal', current, conn), plan['reviewer'], plan['session_id'],
                     d.get('title_zh') or p['summary'][:180], d.get('summary_zh') or p['suggested_memory'][:400], disposition,
                     d['reason'], next_step, pid or nid or '', 'submitted_text_only', now))
                if pid or nid:
                    kind, identity, table, key = ('proposal', pid, 'proposals', 'proposal_id') if pid else ('knowledge', nid, 'knowledge_nodes', 'id')
                    target = dict(conn.execute(f'SELECT * FROM {table} WHERE {key}=?', (identity,)).fetchone())
                    relation = 'duplicate_of' if d['action'] == 'supersede' else d.get('relation', 'related_to')
                    evidence = [dict(source_uri='brain://proposal/' + p['proposal_id'], quoted_excerpt=p['suggested_memory']),
                        dict(source_uri=f'brain://{kind}/{identity}', quoted_excerpt=target.get('suggested_memory', target.get('content', '')))]
                    conn.execute('INSERT INTO editorial_relationships VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (str(uuid4()), 'proposal', p['proposal_id'], kind, identity, self.notes._digest('proposal', current, conn),
                         self.notes._digest(kind, target, conn), relation, d['reason'], encoded(evidence), plan['reviewer'], plan['session_id'], now))
            # Keep source provenance visible beside each new knowledge record.
            for pid, nid in created_nodes.items():
                source = dict(conn.execute('SELECT * FROM proposals WHERE proposal_id=?', (pid,)).fetchone())
                node = dict(conn.execute('SELECT * FROM knowledge_nodes WHERE id=?', (nid,)).fetchone())
                conn.execute('INSERT INTO editorial_relationships VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (str(uuid4()), 'knowledge', nid, 'proposal', pid,
                     self.notes._digest('knowledge', node, conn), self.notes._digest('proposal', source, conn),
                     'related_to', '入库来源：独立审核后的具体提案；原文与提交证据保留。',
                     encoded([dict(source_type='stored_proposal', source_uri='brain://proposal/' + pid, quoted_excerpt=source['evidence'])]),
                     plan['reviewer'], plan['session_id'], now))
            result['knowledge_relationships'] = self.project_relationships(conn, plan, now)
            conn.execute('INSERT INTO proposal_curation_batches VALUES (?,?,?,?,?,?,?)',
                (plan['plan_id'], digest, plan['reviewer'], plan['session_id'], encoded(plan), encoded(result), now))
            return result


    def project_relationships(self, conn, plan, now):
        """Carry explicit current comparisons across exact proposal/node links."""
        items = {}
        for kind, table, key in [('proposal', 'proposals', 'proposal_id'), ('knowledge', 'knowledge_nodes', 'id')]:
            for row in conn.execute('SELECT * FROM ' + table):
                items[(kind, row[key])] = dict(row)
        links = dict(conn.execute('SELECT proposal_id,knowledge_id FROM proposal_knowledge_links'))
        # Only exact-text mappings can carry an old proposal comparison forward.
        # This remains true in later, unrelated batches, after the plan is gone.
        refined = {pid for pid, nid in links.items()
            if ('proposal', pid) in items and ('knowledge', nid) in items
            and str(items[('proposal', pid)]['suggested_memory']).strip() != str(items[('knowledge', nid)]['content']).strip()}
        refined.update(d['proposal_id'] for d in plan['decisions'] if d['action'] == 'refine')
        created = 0
        for raw in list(conn.execute('SELECT * FROM editorial_relationships')):
            edge = dict(raw)
            if edge['source_type'] == edge['target_type'] == 'knowledge':
                continue
            keys = [(edge['source_type'], edge['source_id']), (edge['target_type'], edge['target_id'])]
            if any(kind == 'proposal' and identity in refined for kind, identity in keys):
                continue
            if any(k not in items for k in keys):
                continue
            if any(self.notes._digest(k[0], items[k], conn) != edge[f'{side}_digest'] for k, side in zip(keys, ('source', 'target'))):
                continue
            node_ids = [links.get(identity) if kind == 'proposal' else identity for kind, identity in keys]
            if not all(node_ids) or node_ids[0] == node_ids[1]:
                continue
            nodes = [items.get(('knowledge', identity)) for identity in node_ids]
            if any(n is None or n['stage'] == 'deprecated' for n in nodes):
                continue
            if edge['relation'] in {'related_to', 'conflicts_with'} and node_ids[0] > node_ids[1]:
                node_ids.reverse(); nodes.reverse()
            digests = [self.notes._digest('knowledge', node, conn) for node in nodes]
            if conn.execute("SELECT 1 FROM editorial_relationships WHERE source_type='knowledge' AND target_type='knowledge' AND source_id=? AND target_id=? AND relation=? AND source_digest=? AND target_digest=?",
                    (*node_ids, edge['relation'], *digests)).fetchone():
                continue
            evidence = [dict(source_type='stored_editorial_comparison', source_uri='brain://relationship/' + edge['id'],
                quoted_excerpt=edge['reasoning'], original_evidence=edge['evidence'])]
            conn.execute('INSERT INTO editorial_relationships VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (str(uuid4()), 'knowledge', node_ids[0], 'knowledge', node_ids[1], *digests, edge['relation'],
                 '沿用精确提案入库映射的内容比对：' + edge['reasoning'], encoded(evidence), plan['reviewer'], plan['session_id'], now))
            created += 1
        return created
