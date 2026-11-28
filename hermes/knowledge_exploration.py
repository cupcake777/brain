"""Read-only neighborhood and history. No retrieval or governance side effects."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from urllib.parse import quote

from hermes.environment_scope import get_scope

STAGES = {'draft': '草稿', 'refined': '已整理', 'verified': '已核实', 'canonized': '已入库', 'deprecated': '已停用', 'quarantined': '已隔离'}
RELATIONS = {
    'duplicate_of': ('建议并入', 'review'), 'conflicts_with': ('存在冲突', 'conflict'),
    'refines': ('补充或收窄', 'refine'), 'related_to': ('相关背景', 'related'),
    'parent': ('来源于', 'lineage'), 'derived_from': ('来源于', 'lineage'),
    'supersedes': ('替代', 'lineage'), 'merged_from': ('合并自', 'lineage'), 'contradicts': ('记录的冲突', 'conflict'),
}
TRAFFIC = {'task': '任务流量', 'audit': '审计流量', 'probe': '连接检查', 'evaluation': '评估流量', 'unknown': '未分类流量'}


def _list(value):
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value or '[]')
        return parsed if isinstance(parsed, list) else []
    except (ValueError, TypeError):
        return []


def _text(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)


def _entity(kind, identity, item, scope):
    note = item.get('editorial_review') or {}
    state = item.get('stage') if kind == 'knowledge' else item.get('state')
    label = STAGES.get(state, {'pending': '待整理', 'approved_db_only': '已保留', 'approved_for_export': '已批准同步', 'rejected': '已拒绝', 'superseded': '已替代'}.get(state, state or '未标明'))
    return {'key': f'{kind}:{identity}', 'id': identity, 'kind': kind,
        'title': note.get('title_zh') or item.get('summary') or identity,
        'description': note.get('summary_zh') or item.get('content') or item.get('suggested_memory') or item.get('observation') or '',
        'status': label, 'url': ('/knowledge/' if kind == 'knowledge' else '/review/') + quote(identity, safe=''),
        'scope': ' / '.join(scope.get(k, '') for k in ('server_id', 'user_root', 'project_root') if scope.get(k)) or '共享适用范围',
        'evidence': _text(item.get('evidence') or '暂无证据记录')}


def build_exploration(repo, snapshot, node_id):
    """Use the digest-validated snapshot already used by the readable detail."""
    entities = snapshot['entities']
    root_key = ('knowledge', node_id)
    root = entities[root_key]
    nodes, edges, signatures, timeline = {}, [], set(), []
    with repo._connect() as conn:
        def add_node(key):
            if key not in entities:
                return None
            if key not in nodes:
                nodes[key] = _entity(*key, entities[key], get_scope(conn, *key))
            return nodes[key]['key']

        def add_edge(source, target, relation, **extra):
            if relation not in RELATIONS or source == target:
                return
            left, right = add_node(source), add_node(target)
            if not left or not right:
                return
            signature = (left, right, relation, extra.get('origin', 'lineage'))
            if relation in {'contradicts', 'conflicts_with', 'related_to'}:
                signature = (*sorted((left, right)), relation, extra.get('origin', 'lineage'))
            if signature in signatures:
                return
            signatures.add(signature)
            label, group = RELATIONS[relation]
            edges.append({'id': f'edge-{len(edges)}', 'source': left, 'target': right, 'relation': relation, 'label': label, 'group': group, **extra})

        add_node(root_key)
        for edge in snapshot['by_entity'].get(root_key, []):
            add_edge((edge['source_type'], edge['source_id']), (edge['target_type'], edge['target_id']), edge['relation'],
                origin='editorial', origin_label='内容比对建议', reasoning=edge['reasoning'], evidence=_text(edge['evidence']), reviewer=edge['reviewer'], date=edge['created_at'])
        for (kind, identity), item in entities.items():
            if kind != 'knowledge':
                continue
            for field, relation in [('parent_id', 'parent'), ('supersedes', 'supersedes')]:
                target = item.get(field)
                if target and (identity == node_id or str(target) == node_id):
                    add_edge((kind, identity), (kind, str(target)), relation, origin='lineage', origin_label='保存的版本关系', reasoning='来自经验记录中保存的版本或来源关系。')
            for field, relation in [('merged_from', 'merged_from'), ('contradicts', 'contradicts')]:
                for target in _list(item.get(field)):
                    if isinstance(target, str) and (identity == node_id or target == node_id):
                        add_edge((kind, identity), (kind, target), relation, origin='lineage', origin_label='保存的经验关系', reasoning='来自经验记录中保存的合并或冲突关系。')
        for row in conn.execute('SELECT * FROM memory_edges WHERE from_id=? OR to_id=?', (node_id, node_id)):
            edge = dict(row)
            relation = {'refine': 'refines', 'supersede': 'supersedes', 'merge': 'merged_from'}.get(edge['edge_type'], edge['edge_type'])
            evidence = ''
            if edge.get('evidence_id'):
                observation = conn.execute('SELECT * FROM observations WHERE id=?', (edge['evidence_id'],)).fetchone()
                evidence = _text(dict(observation)) if observation else '原始依据记录当前不可用'
            add_edge(('knowledge', edge['from_id']), ('knowledge', edge['to_id']), relation,
                origin='lineage', origin_label='保存的经验关系', date=edge['created_at'], reasoning='来自已保存的关系记录。', evidence=evidence)

        def event(identity, date, title, category, body='', actor='', **extra):
            if date:
                timeline.append({'id': identity, 'date': date, 'title': title, 'category': category, 'body': body or '未记录详细说明', 'actor': actor, **extra})

        for field, title in [('created_at', '创建经验记录'), ('refined_at', '记录了整理时间'), ('verified_at', '记录了核实时间'), ('deprecated_at', '经验停用记录')]:
            event('lifecycle-' + field, root.get(field), title, 'formation', '来源：经验记录保存的时间。当前状态为“' + STAGES.get(root['stage'], root['stage']) + '”。')
        chains = conn.execute('SELECT * FROM thought_chains WHERE node_id=? ORDER BY created_at DESC,id DESC LIMIT 61', (node_id,)).fetchall()
        actions = {'dedup_check': '去重判断', 'merge': '合并处理', 'refine': '内容整理', 'contradiction_detect': '冲突检查', 'canonize': '入库处理', 'supersede': '替代处理'}
        for chain in chains[:60]:
            item = dict(chain)
            event('chain-' + item['id'], item['created_at'], actions.get(item['action'], '处理记录 · ' + item['action']), 'formation', item['reasoning'], decision=item['decision'], evidence=_text(item['evidence_used']))
        notes = conn.execute("SELECT * FROM editorial_reviews WHERE entity_type='knowledge' AND entity_id=? ORDER BY reviewed_at DESC,id DESC LIMIT 41", (node_id,)).fetchall()
        current_note = (root.get('editorial_review') or {}).get('id')
        for note in notes[:40]:
            item = dict(note)
            event('review-' + item['id'], item['reviewed_at'], '内容初审' if item['id'] == current_note else '历史内容初审', 'review', item['reasoning'], item['reviewer'], evidence={'submitted_text_only': '仅核对已提交文字，未重新执行原始任务'}.get(item['evidence_check'], item['evidence_check']), decision=item['next_step'], historical=item['id'] != current_note)
        for edge in edges:
            if edge.get('origin') == 'editorial':
                event('comparison-' + edge['id'], edge.get('date'), '记录关系：' + edge['label'], 'review', edge.get('reasoning'), edge.get('reviewer', ''), evidence=edge.get('evidence', ''), edge_id=edge['id'])
        for row in conn.execute('SELECT l.*,p.summary FROM proposal_knowledge_links l LEFT JOIN proposals p ON p.proposal_id=l.proposal_id WHERE l.knowledge_id=?', (node_id,)):
            item = dict(row)
            event('proposal-' + item['proposal_id'], item['synced_at'], '关联来源提案', 'formation', item['summary'] or '提案正文当前不可用', url='/review/' + quote(item['proposal_id'], safe=''))
        retrievals = conn.execute("""SELECT * FROM knowledge_retrieval_events r WHERE EXISTS
            (SELECT 1 FROM json_each(CASE WHEN json_valid(r.node_ids) THEN CASE WHEN json_type(r.node_ids)='array' THEN r.node_ids ELSE '[]' END ELSE '[]' END) WHERE value=?)
            ORDER BY created_at DESC,id DESC LIMIT 41""", (node_id,)).fetchall()
        for row in retrievals[:40]:
            item = dict(row)
            event('retrieval-' + item['id'], item['created_at'], '作为检索候选返回', 'use', item['query'], item['agent'], traffic=TRAFFIC.get(item.get('traffic_kind', 'unknown'), '未分类流量'), proof='被返回为候选，不表示已采用或任务成功。')
        outcomes = conn.execute('''SELECT o.*,r.traffic_kind,r.agent FROM outcome_log o
            LEFT JOIN knowledge_retrieval_events r ON r.id=o.retrieval_log_id
            WHERE o.memory_id=? ORDER BY o.created_at DESC,o.id DESC LIMIT 41''', (node_id,)).fetchall()
        for row in outcomes[:40]:
            item = dict(row)
            result = {'success': '任务报告成功', 'failure': '任务报告失败', 'partial': '任务报告部分完成'}.get(item['task_success'], '任务结果未报告')
            helpful = {'helpful': '有帮助', 'partially_helpful': '部分有帮助', 'partially_helped': '部分有帮助', 'applied': '已采用', 'harmful': '产生负面影响', 'unknown': '帮助程度未报告', 'failed': '未解决问题', 'contradicted': '与当前事实矛盾', 'not_used': '未采用', 'neutral': '效果中性'}.get(item['helpfulness'], item['helpfulness'])
            event('outcome-' + item['id'], item['created_at'], '使用反馈：' + ('已采用' if item['used'] else '未采用'), 'use', item['notes'], item.get('agent') or '', evidence=item.get('verification_note') or '',
                decision=helpful + ' · ' + result + (' · 用户已确认' if item['user_validated'] == 1 else ''), traffic=TRAFFIC.get(item.get('traffic_kind'), '未分类流量'), proof='反馈由调用方提交；任务结果与这条经验的帮助程度分别记录。')
    def order(item):
        try:
            stamp = datetime.fromisoformat(item['date'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            return stamp.timestamp(), item['id']
        except (ValueError, TypeError):
            return float('-inf'), item['id']
    timeline.sort(key=order, reverse=True)
    return {'root': nodes[root_key]['key'], 'nodes': list(nodes.values()), 'edges': edges, 'timeline': timeline,
        'history_limited': any((len(chains) > 60, len(notes) > 40, len(retrievals) > 40, len(outcomes) > 40)),
        'counts': {'neighbors': len(nodes) - 1, 'relations': len(edges), 'events': len(timeline)}}


def exploration_sections(data):
    """History remains readable without JavaScript; JS enhances graph and filters."""
    e = lambda value: html.escape(str(value if value is not None else ''), quote=True)
    payload = json.dumps(data, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    root = next(node for node in data['nodes'] if node['key'] == data['root'])
    events = []
    for item in data['timeline']:
        tags = ''.join(f'<span class="kx-tag">{e(value)}</span>' for value in [item.get('actor'), item.get('traffic'), '历史记录' if item.get('historical') else ''] if value)
        details = ''.join(f'<div><dt>{label}</dt><dd><pre>{e(item[key])}</pre></dd></div>' for key, label in [('body', '记录说明'), ('decision', '处理或反馈'), ('evidence', '依据记录')] if item.get(key))
        link = f'<a class="text-link" href="{e(item["url"])}">打开来源提案 →</a>' if item.get('url') else ''
        button = f'<button class="text-link kx-text-button" type="button" data-kx-edge="{e(item["edge_id"])}">在关系图中查看 →</button>' if item.get('edge_id') else ''
        proof = f'<p class="kx-record-note">{e(item["proof"])}</p>' if item.get('proof') else ''
        events.append(f'<li class="kx-event" data-category="{e(item["category"])}" id="{e(item["id"])}"><span class="kx-event-dot" aria-hidden="true"></span><div class="kx-event-head"><h3>{e(item["title"])}</h3><time datetime="{e(item["date"])}">{e(item["date"])}</time></div><div class="kx-event-tags">{tags}</div><p class="kx-event-preview">{e(item["body"])}</p><details><summary>查看记录与依据</summary><dl>{details}</dl>{proof}{link}{button}<p class="kx-record-id">记录编号：{e(item["id"])}</p></details></li>')
    filters = ''.join(f'<button type="button" class="kx-filter {"active" if value=="all" else ""}" data-kx-history="{value}" aria-pressed="{"true" if value=="all" else "false"}">{label}<span>{len(data["timeline"]) if value=="all" else sum(item["category"]==value for item in data["timeline"])}</span></button>' for value,label in [('all','全部记录'),('formation','形成与处理'),('review','审阅与关系'),('use','检索与反馈')])
    limit_note = '<p class="kx-record-note">历史较多，当前展示各类最近记录。</p>' if data['history_limited'] else ''
    return f'''<link rel="stylesheet" href="/workspace-assets/knowledge-explorer.css?v=1">
<div class="kx-explorer" id="knowledge-exploration">
<nav class="kx-jumps" aria-label="经验详情导航"><a href="#local-graph">关系图</a><a href="#evolution-history">演变时间线</a><a href="#knowledge-content">经验原文</a></nav>
<section class="panel kx-panel" id="local-graph" aria-labelledby="kx-graph-title">
<div class="kx-section-head"><div><p class="kx-eyebrow">从一条经验，看见它的上下文</p><h2 id="kx-graph-title">局部关系图</h2><p class="muted">{data['counts']['neighbors']} 条关联记录 · {data['counts']['relations']} 条关系</p></div><label class="kx-relation-filter" hidden>关系类型<select id="kx-relation-type"><option value="all">全部关系</option><option value="conflict">冲突</option><option value="refine">补充与收窄</option><option value="review">合并建议</option><option value="lineage">来源与版本</option><option value="related">相关背景</option></select></label></div>
<div class="kx-graph-layout"><div class="kx-canvas-wrap"><div id="kx-canvas" aria-label="当前经验的局部关系图"><p class="kx-loading">启用 JavaScript 后可交互探索关系，下方保留文字关系与记录。</p></div><div class="kx-graph-footer"><div class="kx-legend"><span>● 当前经验</span><span>□ 已有经验</span><span>┄ 关联提案</span></div><p id="kx-graph-status" role="status" aria-live="polite"></p><button type="button" id="kx-more" class="btn" hidden>查看更多关联</button></div></div>
<aside class="kx-inspector" aria-label="选中记录或关系的详情" aria-live="polite"><p class="kx-eyebrow" id="kx-selection-kind">当前经验</p><h3 id="kx-selection-title">{e(root['title'])}</h3><p id="kx-selection-description">{e(root['description'])}</p><dl id="kx-selection-meta"><div><dt>适用范围</dt><dd>{e(root['scope'])}</dd></div></dl><details id="kx-selection-evidence"><summary>查看依据</summary><div id="kx-evidence-content"><pre>{e(root['evidence'])}</pre></div></details><a class="btn" id="kx-selection-link" href="{e(root['url'])}#knowledge-content">阅读经验原文 →</a></aside></div>
<p class="kx-record-note">箭头从来源记录指向其关系对象；冲突与背景关系不分方向。同一主题不代表存在关系，合并建议也不代表已经合并。</p></section>
<section class="panel kx-panel" id="evolution-history" aria-labelledby="kx-history-title"><div class="kx-section-head"><div><p class="kx-eyebrow">每一步，都有记录可查</p><h2 id="kx-history-title">演变时间线</h2><p class="muted">回看形成、处理、审阅和使用反馈。</p></div><button type="button" class="btn" id="kx-order" aria-label="切换时间排序" hidden>最近在前 ↓</button></div><div class="kx-history-filters" role="group" aria-label="筛选演变记录" hidden>{filters}</div><p class="kx-record-note">仅展示已保存的记录；处理说明不等于保存了修改前后的正文。检索返回、实际采用与任务验收分别呈现。</p>{limit_note}<ol class="kx-timeline">{''.join(events)}</ol><button type="button" class="btn" id="kx-history-more" hidden>查看更多记录</button><p class="kx-timeline-empty" {'hidden' if events else ''}>暂无对应的历史记录。</p></section>
</div><script id="knowledge-exploration-data" type="application/json">{payload}</script><script src="/workspace-assets/knowledge-explorer.js?v=1" defer></script>'''
