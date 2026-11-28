"""Readable applicability inventory; origin never implies applicability."""
from __future__ import annotations
from urllib.parse import quote

from .workspace import e, shell, title_for

LABELS={'shared':'共享经验','__unresolved__':'待核实环境','auto-ingest':'导入来源待核实','auto-cron':'自动整理来源','brain-web':'网页提交来源','unknown':'未知来源'}


def page(report, *, query='', view='scope'):
    def text(item):return str(item.get('summary',''))+' '+title_for(item)+' '+str(item)
    def matches(item):return not query.strip() or query.strip().casefold() in text(item).casefold()
    def records(items,kind):
        rows=[]
        for item in items:
            if not matches(item):continue
            target='/review/' if kind=='proposal' else '/knowledge/'
            identity=item.get('proposal_id') if kind=='proposal' else item.get('id')
            context=item.get('project_root') or item.get('project_key') or '未限定项目'
            rows.append(f'<li><a href="{target}{e(quote(str(identity),safe=""))}">{e(title_for(item))}</a><small>{e(context)}</small></li>')
        return ''.join(rows)
    groups=report.get('applicability_groups',[]) if view=='scope' else report.get('groups',[])
    cards=[]
    for group in groups:
        proposals=[item for item in group.get('proposals',[]) if matches(item)]
        knowledge=[item for item in group.get('knowledge',[]) if matches(item)]
        # A server/directory query also matches all records in that bucket.
        group_match=query.strip() and query.strip().casefold() in (' '.join(str(group.get(k,'')) for k in ('server_id','user_root'))).casefold()
        if group_match:proposals=group.get('proposals',[]);knowledge=group.get('knowledge',[])
        if not proposals and not knowledge:continue
        server=group.get('server_id') or 'shared';label=LABELS.get(server,server)
        detail=[]
        for kind,items,label_text in [('knowledge',knowledge,'在用经验'),('proposal',proposals,'提案记录')]:
            if items:
                # Group-name matches should not filter the child titles again.
                current_query=query
                if group_match:query=''
                content=records(items,kind);query=current_query
                detail.append(f'<details><summary>{label_text} · {len(items)}</summary><ul>{content}</ul></details>')
        scope_notice='仅保留记录，环境核实前不用于跨环境检索。' if server=='__unresolved__' else '这组经验不限定服务器。' if server=='shared' and view=='scope' else '来源表示从哪里提交，适用范围另行记录。' if view=='origin' else '仅在记录的服务器及目录范围内适用。'
        cards.append(f'<section class="panel environment-card"><h2>{e(label)}</h2><p class="env-id">{e(group.get("user_root") or "用户目录未限定")}</p><p class="muted">{e(scope_notice)}</p><div class="record-meta" style="margin-top:14px"><span>{len(knowledge)} 条在用经验</span><span>{len(proposals)} 条提案</span></div>{"".join(detail)}</section>')
    query_url=quote(query,safe='')
    tabs=f'<nav class="pills" aria-label="环境视图"><a class="pill {"active" if view=="scope" else ""}" href="/environments?view=scope&q={query_url}">按适用范围</a><a class="pill {"active" if view=="origin" else ""}" href="/environments?view=origin&q={query_url}">按提交来源</a></nav>'
    body=f'''<header class="page-head"><div><p class="eyebrow">经验的上下文</p><h1>服务器与目录</h1><p>看清一条经验适用在哪里，也能追溯它从哪里提交。</p></div></header><form class="search environment-search" role="search" method="get"><input type="hidden" name="view" value="{e(view)}"><input type="search" name="q" value="{e(query)}" aria-label="搜索服务器与经验" placeholder="搜索服务器、目录或中文经验"><button>搜索</button></form>{tabs}<p class="subtle-note">适用范围决定何时使用；提交来源只用于追溯。没有确认归属的环境规则会单独列出。</p><div class="surface-grid">{"".join(cards) or '<div class="empty">没有匹配的服务器或经验。</div>'}</div>'''
    return shell('服务器与目录',body,active='environments')
