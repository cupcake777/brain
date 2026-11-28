"""Proposal topics and explicit comparisons, with links in both directions."""
from __future__ import annotations
from collections import Counter
from urllib.parse import quote, urlencode

from .review_notes import DISPOSITIONS
from .workspace import description_for, e, review_badge, shell, title_for


def entity_url(kind, item_id):
    return ('/review/' if kind=='proposal' else '/knowledge/')+quote(str(item_id),safe='')


def relationship_section(item):
    relations=item.get('relationships') or []
    topic=item.get('topic')
    topic_link=f'<a class="text-link" href="/proposals?topic={e(quote(topic["id"],safe=""))}">查看“{e(topic["title"])}”主题 →</a>' if topic else ''
    if not relations:
        return f'<section class="panel"><h2>与其他记录的关系</h2><p class="muted">尚未记录经过比较的重复、冲突或补充关系。</p>{topic_link}</section>'
    cards=[]
    for edge in sorted(relations,key=lambda r:(0 if r['relation']=='conflicts_with' else 1 if r['relation']=='duplicate_of' else 2,r['other_id'])):
        other=edge['other'];kind='提案' if edge['other_type']=='proposal' else '已有经验'
        tone='red' if edge['relation']=='conflicts_with' else 'purple'
        state={'pending':'待处理','approved_db_only':'已保留','approved_for_export':'已同步','rejected':'已拒绝','superseded':'已替代'}.get(other.get('state'),'')
        cards.append(f'''<div class="relationship-card"><div class="relation-head"><span class="tag {tone}">{e(edge['label'])}</span><span class="muted">{kind} {e(state)}</span></div><a href="{e(entity_url(edge['other_type'],edge['other_id']))}">{e(title_for(other))} →</a><p>{e(edge['reasoning'])}</p><small>{e(edge['reviewer'])} · {e(edge['created_at'][:10])} · 比对当前保存内容</small><details><summary>查看比对依据</summary><pre class="raw">{e(edge['evidence'])}</pre></details></div>''')
    return f'<section class="panel" id="relationships"><div class="section-head"><h2>与其他记录的关系</h2><span class="muted">{len(relations)} 条</span></div><div class="relationship-list">{"".join(cards)}</div><p class="subtle-note">同一主题只表示便于一起查看；合并与冲突建议需要具体比对。任一端原文或适用范围改变后，旧关系会退出当前展示。</p>{topic_link}</section>'


def _row(item):
    note=item.get('editorial_review');relations=item.get('relationships') or []
    counts=Counter(r['relation'] for r in relations)
    labels=[f'{counts[k]} 条{label}' for k,label in [('duplicate_of','合并关系'),('conflicts_with','冲突关系'),('refines','补充关系'),('related_to','相关背景')] if counts[k]]
    # These are spans inside a single row link: there are no invalid nested anchors.
    hints=f'<div class="row-relations">{" · ".join(labels)}</div>' if labels else ''
    reviewer=f'<strong>{e(note["reviewer"])} · 已初审</strong>{e(note["reviewed_at"][:10])}' if note else '<strong>等待初审</strong>新内容尚未判断'
    return f'''<a class="queue-row" href="{e(entity_url('proposal',item['proposal_id']))}"><div><strong class="record-title">{e(title_for(item))}</strong><span class="record-desc">{e(description_for(item)[:200])}</span>{hints}<div class="record-meta"><span>提交于 {e(str(item.get('created_at') or '')[:10])}</span><span>{e(item.get('source_agent'))}</span></div></div><div>{review_badge(note,outdated=item.get('review_outdated',False))}</div><div class="queue-reviewer">{reviewer}</div></a>'''


def proposal_queue(*, proposals, counts, query='', bucket='', page=1, v2=None, topic='', view='topics', stale_relations=0):
    all_items=proposals;reviewed=sum(bool(p.get('editorial_review')) for p in all_items)
    def url(**kw):return '/proposals?'+urlencode({'q':query,'bucket':bucket,'topic':topic,'view':view,**kw})
    selected=all_items
    if topic:selected=[p for p in selected if (p.get('topic') or {}).get('id','unclassified')==topic]
    if bucket=='unreviewed':selected=[p for p in selected if not p.get('editorial_review')]
    elif bucket:selected=[p for p in selected if (p.get('editorial_review') or {}).get('disposition')==bucket]
    if query.strip():
        needle=query.strip().casefold()
        selected=[p for p in selected if needle in ' '.join([str(p.get('summary','')),str(p.get('suggested_memory','')),title_for(p),description_for(p),str(p.get('source_agent','')),str(p.get('topic') or '')]).casefold()]
    selected=sorted(selected,key=lambda p:(bool(p.get('editorial_review')),0 if (p.get('editorial_review') or {}).get('disposition')=='conflict' else 1,str(p.get('created_at') or '')))
    pills=[]
    for key,label in [('', '全部'),('unreviewed','尚未初审'),*DISPOSITIONS.items()]:
        count=len(all_items) if not key else sum(not p.get('editorial_review') for p in all_items) if key=='unreviewed' else sum((p.get('editorial_review') or {}).get('disposition')==key for p in all_items)
        if count or not key:pills.append(f'<a class="pill {"active" if bucket==key else ""}" href="{e(url(bucket=key,page=1))}">{e(label)} <span>{count}</span></a>')
    topics={p['topic']['id']:p['topic'] for p in all_items if p.get('topic')}
    options=''.join(f'<option value="{e(key)}" {"selected" if key==topic else ""}>{e(value["title"])}</option>' for key,value in sorted(topics.items(),key=lambda pair:pair[1]['title']))
    options+=f'<option value="unclassified" {"selected" if topic=="unclassified" else ""}>尚待归类</option>'
    toggle=f'<nav class="pills" aria-label="提案浏览方式"><a class="pill {"active" if view=="topics" else ""}" href="{e(url(view="topics",page=1))}">按主题整理</a><a class="pill {"active" if view=="list" else ""}" href="{e(url(view="list",page=1))}">全部条目</a></nav>'
    if view=='topics':
        grouped={}
        for item in selected:
            group=item.get('topic') or {'id':'unclassified','title':'新内容与待归类记录','description':'尚未比对的新记录会留在这里，避免直接混入已有结论。'}
            grouped.setdefault(group['id'],{'topic':group,'items':[]})['items'].append(item)
        blocks=[]
        for key,group in sorted(grouped.items(),key=lambda pair:(pair[0]!='unclassified',-sum((p.get('editorial_review') or {}).get('disposition')=='conflict' for p in pair[1]['items']),-len(pair[1]['items']),pair[0])):
            items=group['items'];meta=group['topic'];ids={p['proposal_id'] for p in items}
            edges={r['id']:r for p in items for r in p.get('relationships',[])}
            duplicate=sum(r['relation']=='duplicate_of' for r in edges.values());conflict=sum(r['relation']=='conflicts_with' for r in edges.values())
            related_knowledge={r['other_id']:r['other'] for p in items for r in p.get('relationships',[]) if r['other_type']=='knowledge'}
            badges=f'<span class="tag">{len(items)} 条提案</span>'+ (f'<span class="tag purple">{duplicate} 条合并关系</span>' if duplicate else '')+(f'<span class="tag red">{conflict} 条冲突关系</span>' if conflict else '')+(f'<span class="tag green">关联 {len(related_knowledge)} 条已有经验</span>' if related_knowledge else '')
            knowledge_links=''.join(f'<a class="text-link" href="{e(entity_url("knowledge",nid))}">{e(title_for(n))} →</a><br>' for nid,n in related_knowledge.items())
            blocks.append(f'''<details class="topic-group" data-topic="{e(key)}" {'open' if topic or bucket or query.strip() or key=='unclassified' else ''}><summary><div class="topic-copy"><strong>{e(meta['title'])}</strong><p>{e(meta['description'])}</p></div><div class="topic-counts">{badges}</div></summary><div class="list">{''.join(_row(p) for p in items)}</div>{f'<div class="topic-desc"><p>已经入库的相关经验</p>{knowledge_links}</div>' if knowledge_links else ''}</details>''')
        content=''.join(blocks) or '<div class="empty">没有匹配的提案。</div>'
        pagination=f'<p class="muted">{len(selected)} 条提案 · {len(grouped)} 个主题组 · 展开主题查看具体条目</p>'
    else:
        total=len(selected);size=15;pages=max(1,(total+size-1)//size);page=min(max(page,1),pages)
        content='<div class="list">'+(''.join(_row(p) for p in selected[(page-1)*size:page*size]) or '<div class="empty">没有匹配的提案。</div>')+'</div>'
        pagination=f'<div class="pagination"><span>显示 {(page-1)*size+1 if total else 0}–{min(page*size,total)} / {total}</span><div>{f"<a class=btn href={e(url(page=page-1))}>上一页</a>" if page>1 else ""} {f"<a class=btn href={e(url(page=page+1))}>下一页</a>" if page<pages else ""}</div></div>'
    v2_html=''.join(f'<a class="queue-row" href="/proposals/{e(quote(str(p["id"]),safe=""))}"><div><strong class="record-title">{e(p.get("lesson") or "新版提案")}</strong><span class="record-desc">新版审批流程 · {e(p.get("workflow_state"))}</span></div></a>' for p in v2 or [])
    body=f'''<header class="page-head"><div><p class="eyebrow">把相关内容放在一起判断</p><h1>待整理</h1><p>按问题查看提案，分清重复、冲突和已有结论。</p></div><a class="btn" href="/proposals?tab=flow">处理历史</a></header><div class="mini-stats"><div><strong>{len(all_items)}</strong><span>条待处理</span></div><div><strong>{reviewed}</strong><span>条有初审</span></div><div><strong>{len(all_items)-reviewed}</strong><span>条等待初审</span></div><div><strong>{len(topics)}</strong><span>个已整理主题</span></div></div>{toggle}<form class="filters" action="/proposals" method="get"><div class="search"><input type="search" name="q" value="{e(query)}" aria-label="搜索待整理内容" placeholder="搜索问题、中文摘要或原文"><button>搜索</button></div><input type="hidden" name="view" value="{e(view)}"><input type="hidden" name="bucket" value="{e(bucket)}"><select class="filter-select" name="topic" aria-label="主题" onchange="this.form.submit()"><option value="">全部主题</option>{options}</select></form><nav class="pills" aria-label="按初审建议筛选">{''.join(pills)}</nav><p class="subtle-note">关系来自对具体内容的比对。同一主题可以保留不同结论；合并建议不会自动批准或删除记录。{f'有 {stale_relations} 条旧关系因内容变化等待复核。' if stale_relations else ''}</p>{content}{pagination}{f'<section class="panel"><h2>新版提案</h2>{v2_html}</section>' if v2_html else ''}'''
    return shell('待整理',body,active='proposals',pending=len(all_items))
