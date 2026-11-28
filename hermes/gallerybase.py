from __future__ import annotations

import html
from pathlib import PurePosixPath
from typing import Any, Iterable
from urllib.parse import quote

from hermes.workspace import e, icon, shell


_VISUAL_GRAMMAR_LABELS = {
    "scatter_rel": "散点关系",
    "distribution": "分布",
    "bar_rank": "柱图与排序",
    "heatmap": "热图",
    "line_trend": "曲线与趋势",
    "network_flow": "网络与流向",
    "set_overlap": "集合与交集",
    "special": "其他图型",
}


def _text(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _items(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [_text(item) for item in value if _text(item)]


def _local_path(value: object, *, suffixes: set[str] | None = None) -> str | None:
    """Accept one normalized catalog-relative path and reject URL/traversal forms."""
    raw = _text(value).strip()
    if not raw or "\\" in raw or "\x00" in raw or "://" in raw or raw.startswith(("/", "//")):
        return None
    path = PurePosixPath(raw)
    if any(part in ("", ".", "..") for part in path.parts):
        return None
    if suffixes is not None and path.suffix.lower() not in suffixes:
        return None
    return path.as_posix()


def _asset_url(value: object, *, suffixes: set[str]) -> str | None:
    path = _local_path(value, suffixes=suffixes)
    return f"/gallery/static/{quote(path, safe='/')}" if path else None


def _template_name(chart: dict[str, Any]) -> str | None:
    template = _local_path(chart.get("template"), suffixes={".py", ".r"})
    if template:
        return template
    name = _text(chart.get("name")).strip()
    if name and "/" not in name and "\\" not in name:
        return f"{name}.py"
    return None


def _badge(value: object, class_name: str) -> str:
    return f'<span class="{class_name}">{html.escape(_text(value))}</span>'


_STATUS={'done':'可使用','active':'可使用','ready':'可使用','planned':'规划中','draft':'草稿','review':'待检查'}
_STYLE='''<style>
.gallery-tools{display:grid;grid-template-columns:minmax(0,1fr) 150px 170px;gap:12px;margin:24px 0}.gallery-tools .search{margin:0;width:100%}.gallery-tools select{width:100%;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px}.gallery-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.gallery-grid>.empty{grid-column:1/-1;min-height:240px;display:grid;align-content:center;gap:8px}.gallery-card{border:1px solid var(--line);border-radius:11px;background:var(--panel);overflow:hidden;min-width:0}.gallery-card[hidden]{display:none}.gallery-card-link{display:block;height:100%}.gallery-preview{aspect-ratio:16/10;background:var(--bg);border-bottom:1px solid var(--line);display:grid;place-items:center;overflow:hidden}.gallery-preview img{width:100%;height:100%;object-fit:contain}.gallery-empty-preview{color:var(--muted);display:grid;place-items:center;gap:10px;font-size:12px}.gallery-card-body{padding:18px}.gallery-card-body h2{font-size:15px;margin:11px 0 8px;overflow-wrap:anywhere}.gallery-card-body p{font-size:12px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:40px}.gallery-tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}.gallery-filter-status{padding:25px;text-align:center}.gallery-filter-status[hidden]{display:none}.gallery-detail-grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:22px;align-items:start}.gallery-detail-grid>*{min-width:0}.detail-figure-button{display:block;width:100%;border:0;background:var(--bg);padding:15px;border-radius:8px;cursor:zoom-in}.detail-figure-button img{width:100%;max-height:650px;object-fit:contain}.detail-no-figure{min-height:250px;display:grid;place-items:center;color:var(--muted);background:var(--bg);border-radius:8px}.detail-interactive iframe{width:100%;height:480px;background:white;border:1px solid var(--line);border-radius:8px}.detail-fields{margin:0}.detail-fields>div{padding:10px 0;border-bottom:1px solid var(--line);display:grid;grid-template-columns:95px minmax(0,1fr);gap:10px}.detail-fields dt{color:var(--muted);font-size:12px}.detail-fields dd{margin:0;overflow-wrap:anywhere}.detail-dialog{width:min(94vw,1100px);max-height:92vh;padding:16px;background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:12px}.detail-dialog::backdrop{background:#10131bbd}.detail-dialog img{max-width:100%;max-height:80vh;object-fit:contain;display:block;margin:auto}.detail-dialog button{position:absolute;right:12px;top:12px;min-width:44px;min-height:44px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink)}.template-source{max-height:500px;overflow:auto;font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;background:var(--bg);padding:16px;border-radius:8px;margin-top:16px}.template-source[hidden]{display:none}
@media(max-width:1100px){.gallery-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.gallery-detail-grid{grid-template-columns:minmax(0,1fr)}}@media(max-width:600px){.gallery-grid{grid-template-columns:minmax(0,1fr)}.gallery-tools{grid-template-columns:1fr 1fr}.gallery-tools .search{grid-column:1/-1}.detail-interactive iframe{height:360px}}
</style>'''


def gallery_page(*, charts: Iterable[dict[str, Any]] | None = None) -> str:
    cards=[];categories=set()
    for chart in charts or []:
        if not isinstance(chart,dict) or not _text(chart.get('name')).strip():continue
        name=_text(chart.get('name'));title=_text(chart.get('title')) or name
        grammar=_text(chart.get('visual_grammar'));category=_VISUAL_GRAMMAR_LABELS.get(grammar,grammar) or '其他图型'
        categories.add(category)
        shape=_text(chart.get('data_type') or chart.get('input_shape'));tags=_items(chart.get('tags'))[:4]
        tier=_text(chart.get('tier')) or 'P2';status=_text(chart.get('status')) or 'planned'
        image=_asset_url(chart.get('demo'),suffixes={'.png','.jpg','.jpeg','.webp','.svg'})
        preview=f'<img src="{e(image)}" alt="{e(title)}预览" loading="lazy">' if image else f'<div class="gallery-empty-preview">{icon("file",30)}<span>暂无预览图</span></div>'
        description=_text(chart.get('description'))
        search=' '.join([name,title,description,shape,category,*tags]).casefold()
        cards.append(f'''<article class="gallery-card" data-search="{e(search)}" data-tier="{e(tier)}" data-category="{e(category)}"><a class="gallery-card-link" href="/gallery/{e(quote(name,safe=''))}" aria-label="查看{e(title)}"><div class="gallery-preview">{preview}</div><div class="gallery-card-body"><span class="tag">{e(category)}</span><h2>{e(title)}</h2><p>{e(description or '查看输入字段、图形预览和本地脚本。')}</p><div class="gallery-tags"><span class="tag">{e(_STATUS.get(status,status))}</span><span class="tag">{e(tier)}</span>{''.join(_badge(tag,'tag') for tag in tags)}</div></div></a></article>''')
    options=''.join(f'<option value="{e(category)}">{e(category)}</option>' for category in sorted(categories))
    body=_STYLE+f'''<div id="gallery-main"><header class="page-head"><div><p class="eyebrow">可复用的绘图资产</p><h1>图表模板</h1><p>按图型和数据结构找模板，查看预览与实际脚本。</p></div><span class="tag"><span id="gallery-visible-count">{len(cards)}</span> / {len(cards)} 个模板</span></header><form class="gallery-tools" role="search"><div class="search"><input id="gallery-search" type="search" aria-label="搜索图表模板" placeholder="搜索标题、数据结构或标签" autocomplete="off"><button>搜索</button></div><select id="gallery-tier" aria-label="优先级"><option value="">全部优先级</option><option>P0</option><option>P1</option><option>P2</option></select><select id="gallery-category" aria-label="图型"><option value="">全部图型</option>{options}</select></form><section class="gallery-grid" aria-live="polite">{''.join(cards) or '<div class="empty"><h2>还没有图表模板</h2><p>当前工作空间尚未收录图表模板。接入模板后，可在这里检索、预览和读取脚本。</p></div>'}</section><div id="gallery-no-results" class="gallery-filter-status" role="status" aria-live="polite" hidden><p>没有符合当前条件的模板。</p><button class="btn" id="gallery-clear-filters" type="button">清除筛选</button></div></div>'''
    script='''(()=>{const search=document.getElementById('gallery-search'),tier=document.getElementById('gallery-tier'),category=document.getElementById('gallery-category'),count=document.getElementById('gallery-visible-count'),empty=document.getElementById('gallery-no-results');const cards=[...document.querySelectorAll('.gallery-card')];function apply(){const query=search.value.trim().toLowerCase();let visible=0;cards.forEach(card=>{card.hidden=!((!query||card.dataset.search.includes(query))&&(!tier.value||card.dataset.tier===tier.value)&&(!category.value||card.dataset.category===category.value));if(!card.hidden)visible++});count.textContent=String(visible);empty.hidden=visible!==0||cards.length===0}search.form.addEventListener('submit',event=>{event.preventDefault();apply()});[search,tier,category].forEach(control=>control.addEventListener('input',apply));document.getElementById('gallery-clear-filters').addEventListener('click',()=>{search.value='';tier.value='';category.value='';apply();search.focus()})})();'''
    return shell('图表模板',body,active='gallery',extra_js=script)


def gallery_detail_page(*, chart: dict[str, Any] | None, chart_name: str = '') -> str:
    if not isinstance(chart,dict):
        return shell('图表模板', '<div id="gallery-detail-main" class="empty"><h1>模板不存在</h1><p>这条记录已移除或尚未收录。</p><a class="btn" href="/gallery">返回图表模板</a></div>',active='gallery')
    name=_text(chart.get('name') or chart_name);title=_text(chart.get('title')) or name
    image=_asset_url(chart.get('demo'),suffixes={'.png','.jpg','.jpeg','.webp','.svg'})
    interactive_url=_asset_url(chart.get('interactive'),suffixes={'.html','.htm'})
    template=_template_name(chart)
    template_url=f'/api/gallery/template/{quote(template,safe="/")}' if template else None
    required=_items(chart.get('required_fields') or chart.get('required_columns') or chart.get('columns'))
    optional=_items(chart.get('optional_fields') or chart.get('optional_columns'))
    reusable=_items(chart.get('reusable_for') or chart.get('recommended_for'))
    encodings=chart.get('visual_encodings') if isinstance(chart.get('visual_encodings'),dict) else {}
    encoding=''.join(f'<div><dt>{e(key)}</dt><dd>{e(value)}</dd></div>' for key,value in encodings.items())
    def chips(values):return ''.join(_badge(v,'tag') for v in values) or '<span class="muted">未指定</span>'
    preview=f'<button class="detail-figure-button" type="button" aria-label="放大图形预览"><img src="{e(image)}" alt="{e(title)}预览"></button>' if image else '<div class="detail-no-figure">本地预览图尚未生成</div>'
    interactive=f'<section class="panel detail-interactive"><h2>交互预览</h2><iframe src="{e(interactive_url)}" title="{e(title)}交互预览" sandbox="allow-scripts" loading="lazy"></iframe></section>' if interactive_url else ''
    source=f'<p class="muted">{e(template)}</p><a class="text-link" href="{e(template_url)}" id="template-load" data-source="{e(template_url)}">查看脚本 →</a><p id="template-status" role="status" class="form-status"></p><pre id="template-source" class="template-source" hidden></pre>' if template_url else '<p class="muted">当前记录未关联本地脚本。</p>'
    body=_STYLE+f'''<div id="gallery-detail-main"><a class="text-link" href="/gallery">← 返回图表模板</a><header class="page-head" style="margin-top:20px"><div><h1>{e(title)}</h1><p>{e(chart.get('description') or '')}</p></div><span class="tag">{e(_STATUS.get(_text(chart.get('status')),_text(chart.get('status'))))}</span></header><div class="gallery-detail-grid"><div><section class="panel"><h2>图形预览</h2>{preview}</section>{interactive}<section class="panel"><h2>本地绘图脚本</h2>{source}</section></div><aside><section class="panel"><h2>输入与映射</h2><dl class="detail-fields"><div><dt>数据结构</dt><dd>{e(chart.get('data_type') or chart.get('input_shape') or '未指定')}</dd></div>{encoding}</dl><h3 style="margin-top:20px">必要字段</h3><div class="gallery-tags">{chips(required)}</div><h3 style="margin-top:20px">可选字段</h3><div class="gallery-tags">{chips(optional)}</div><h3 style="margin-top:20px">适合用途</h3><div class="gallery-tags">{chips(reusable)}</div><h3 style="margin-top:20px">标签</h3><div class="gallery-tags">{chips(_items(chart.get('tags')))}</div></section></aside></div><dialog class="detail-dialog" aria-label="图形预览"><button type="button" aria-label="关闭预览">×</button>{f'<img src="{e(image)}" alt="{e(title)}放大预览">' if image else ''}</dialog></div>'''
    script='''(()=>{const opener=document.querySelector('.detail-figure-button'),dialog=document.querySelector('.detail-dialog');if(opener&&dialog){opener.addEventListener('click',()=>dialog.showModal());dialog.querySelector('button').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()});dialog.addEventListener('close',()=>opener.focus())}const load=document.getElementById('template-load');if(load)load.addEventListener('click',async event=>{event.preventDefault();const message=document.getElementById('template-status'),source=document.getElementById('template-source');message.textContent='正在读取脚本…';try{const response=await fetch(load.dataset.source,{credentials:'same-origin'});if(!response.ok)throw Error('脚本暂未找到');const data=await response.json();if(!data.ok)throw Error('脚本暂未找到');source.textContent=data.content||'';source.hidden=false;message.textContent='已读取本地脚本。'}catch(error){message.textContent=error.message}})})();'''
    return shell('图表模板详情',body,active='gallery',extra_js=script)
