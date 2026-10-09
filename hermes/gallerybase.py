from __future__ import annotations

import html
from pathlib import PurePosixPath
from typing import Any, Iterable
from urllib.parse import quote

from hermes.templates import _page


_VISUAL_GRAMMAR_LABELS = {
    "scatter_rel": "Scatter",
    "distribution": "Distribution",
    "bar_rank": "Bar / Rank",
    "heatmap": "Heatmap",
    "line_trend": "Line / Trend",
    "network_flow": "Network / Flow",
    "set_overlap": "Set / Overlap",
    "special": "Special",
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


def gallery_page(*, charts: Iterable[dict[str, Any]] | None = None) -> str:
    """Render the local scientific-figure catalog without network-backed media."""
    records = [chart for chart in (charts or []) if isinstance(chart, dict)]
    cards: list[str] = []
    categories: set[str] = set()

    for chart in records:
        name = _text(chart.get("name")).strip()
        if not name:
            continue
        title = _text(chart.get("title"), name) or name
        description = _text(chart.get("description"))
        tier = _text(chart.get("tier"), "P2") or "P2"
        status = _text(chart.get("status"), "planned") or "planned"
        shape = _text(chart.get("data_type") or chart.get("input_shape"))
        grammar = _text(chart.get("visual_grammar"))
        category = _VISUAL_GRAMMAR_LABELS.get(grammar, grammar.replace("_", " ").title()) if grammar else ""
        if category:
            categories.add(category)
        tags = _items(chart.get("tags"))[:4]
        demo_url = _asset_url(chart.get("demo"), suffixes={".png", ".jpg", ".jpeg", ".webp", ".svg"})
        interactive_url = _asset_url(chart.get("interactive"), suffixes={".html", ".htm"})

        preview = (
            f'<img src="{html.escape(demo_url, quote=True)}" alt="Preview of {html.escape(title, quote=True)}" loading="lazy">'
            if demo_url
            else '<div class="gallery-empty-preview" aria-hidden="true"><span>FIG</span><i></i><i></i><i></i></div>'
        )
        signals = [_badge(tier, f"gallery-tier gallery-tier-{html.escape(tier, quote=True)}"), _badge(status, "gallery-status")]
        if interactive_url:
            signals.append(_badge("Interactive", "gallery-interactive"))
        tag_html = "".join(_badge(tag, "gallery-tag") for tag in ([shape] if shape else []) + tags)
        search_text = " ".join([title, description, shape, category, *tags]).lower()
        href = f"/gallery/{quote(name, safe='')}"
        cards.append(
            f'<article class="gallery-card" data-search="{html.escape(search_text, quote=True)}" '
            f'data-tier="{html.escape(tier, quote=True)}" data-category="{html.escape(category, quote=True)}">'
            f'<a class="gallery-card-link" href="{href}" aria-label="Open {html.escape(title, quote=True)}">'
            f'<div class="gallery-preview">{preview}<div class="gallery-signals">{"".join(signals)}</div></div>'
            f'<div class="gallery-card-body"><p class="gallery-kicker">{html.escape(category or "Scientific figure")}</p>'
            f'<h2>{html.escape(title)}</h2><p>{html.escape(description)}</p><div class="gallery-tags">{tag_html}</div></div>'
            '</a></article>'
        )

    category_options = "".join(
        f'<option value="{html.escape(category, quote=True)}">{html.escape(category)}</option>'
        for category in sorted(categories)
    )
    content = "".join(cards) if cards else (
        '<section class="gallery-empty" aria-labelledby="gallery-empty-title">'
        '<p class="gallery-kicker">Local catalog</p><h2 id="gallery-empty-title">No figure templates yet</h2>'
        '<p>Add a catalog entry and its UUID-backed local assets to begin the collection.</p></section>'
    )

    body = f"""
<style>
.gallery-shell{{--paper:var(--card);--paper-deep:var(--surface-strong);--gallery-ink:var(--ink);--gallery-muted:var(--ink-muted);--gallery-line:var(--border);--gallery-accent:var(--primary);max-width:1240px;margin:0 auto;padding:30px 24px 64px;color:var(--gallery-ink)}}
.gallery-masthead{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:28px;align-items:end;padding:8px 0 22px;border-bottom:1px solid var(--gallery-line)}}
.gallery-eyebrow,.gallery-kicker{{margin:0 0 6px;font:700 11px/1.2 var(--font-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--gallery-accent)}}
.gallery-masthead h1{{margin:0;font:650 clamp(30px,5vw,54px)/.98 Georgia,serif;letter-spacing:-.035em;color:var(--gallery-ink)}}
.gallery-masthead-copy{{max-width:510px;margin:10px 0 0;color:var(--gallery-muted);font-size:14px;line-height:1.55}}
.gallery-ledger{{display:grid;grid-template-columns:auto auto;gap:4px 18px;min-width:170px;padding:12px 0;font:12px/1.35 var(--font-mono);border-top:1px solid var(--gallery-line);border-bottom:1px solid var(--gallery-line)}}
.gallery-ledger strong{{font-size:18px;color:var(--gallery-ink)}}
.gallery-ledger span{{color:var(--gallery-muted)}}
.gallery-tools{{display:grid;grid-template-columns:minmax(220px,1fr) 180px 180px;gap:10px;padding:18px 0}}
.gallery-tools label{{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}}
.gallery-tools input,.gallery-tools select{{min-height:44px;width:100%;box-sizing:border-box;border:1px solid var(--gallery-line);border-radius:var(--r-sm);background:var(--card);color:var(--gallery-ink);padding:0 12px;font:13px var(--font);outline:none}}
.gallery-tools input:focus,.gallery-tools select:focus{{border-color:var(--gallery-accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--gallery-accent) 16%,transparent)}}
.gallery-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}
.gallery-card{{min-width:0;background:var(--card);border:1px solid var(--gallery-line);border-radius:var(--r-md);overflow:hidden;transition:transform .16s ease,border-color .16s ease}}
.gallery-card:hover{{transform:translateY(-2px);border-color:#b99e74}}
.gallery-card[hidden]{{display:none}}
.gallery-card-link{{display:block;height:100%;color:inherit;text-decoration:none}}
.gallery-preview{{position:relative;display:grid;place-items:center;aspect-ratio:16/10;background:var(--paper);border-bottom:1px solid var(--gallery-line);overflow:hidden}}
.gallery-preview img{{width:100%;height:100%;object-fit:contain}}
.gallery-signals{{position:absolute;inset:10px 10px auto;display:flex;gap:5px;align-items:center;flex-wrap:wrap}}
.gallery-signals span,.gallery-tag{{display:inline-flex;align-items:center;min-height:22px;padding:2px 7px;border:1px solid var(--gallery-line);border-radius:99px;background:rgba(255,253,248,.94);font:700 9px/1 var(--font-mono);letter-spacing:.04em;text-transform:uppercase;color:var(--gallery-muted)}}
.gallery-tier-P0{{color:#9f3f35!important}}.gallery-tier-P1{{color:#8a5a21!important}}.gallery-interactive{{margin-left:auto;color:#3b625b!important}}
.gallery-empty-preview{{display:grid;grid-template-columns:repeat(3,34px);gap:7px;align-items:end;color:#a38e6d}}
.gallery-empty-preview span{{grid-column:1/-1;text-align:center;font:700 12px var(--font-mono);letter-spacing:.2em}}
.gallery-empty-preview i{{display:block;height:42px;background:#ded2be}}.gallery-empty-preview i:nth-child(3){{height:68px;background:#c6ad84}}.gallery-empty-preview i:nth-child(4){{height:54px;background:#d5c4a8}}
.gallery-card-body{{padding:16px 17px 18px}}
.gallery-card-body h2{{margin:0 0 7px;font:650 19px/1.15 Georgia,serif;color:var(--gallery-ink)}}
.gallery-card-body>p:not(.gallery-kicker){{min-height:40px;margin:0 0 13px;color:var(--gallery-muted);font-size:12px;line-height:1.55;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}}
.gallery-tags{{display:flex;flex-wrap:wrap;gap:5px}}
.gallery-empty{{padding:64px 24px;text-align:center;border:1px dashed var(--gallery-line);background:var(--paper)}}
.gallery-empty h2{{margin:0 0 8px;font:650 26px Georgia,serif}}.gallery-empty p:last-child{{color:var(--gallery-muted)}}
.gallery-filter-status{{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:52px;padding:10px 14px;margin-top:14px;border:1px dashed var(--gallery-line);background:var(--paper)}}
.gallery-filter-status[hidden]{{display:none}}.gallery-filter-status p{{margin:0;color:var(--gallery-muted);font-size:13px}}.gallery-filter-status button{{min-height:44px;padding:0 14px;border:1px solid var(--gallery-line);border-radius:4px;background:#fffdf8;color:var(--gallery-ink);cursor:pointer}}
@media(max-width:900px){{.gallery-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:680px){{.gallery-shell{{padding:22px 14px 48px}}.gallery-masthead{{grid-template-columns:1fr}}.gallery-ledger{{width:100%;box-sizing:border-box}}.gallery-tools{{grid-template-columns:1fr}}.gallery-grid{{grid-template-columns:1fr}}}}
@media(prefers-reduced-motion:reduce){{.gallery-card{{transition:none}}}}
</style>
<main id="gallery-main" class="gallery-shell">
  <header class="gallery-masthead">
    <div><p class="gallery-eyebrow">Local figure library · Engram</p><h1>Scientific figure atlas</h1><p class="gallery-masthead-copy">Reusable plotting scripts and generated figures, kept local and organized by visual grammar.</p></div>
    <div class="gallery-ledger" aria-label="Catalog summary"><strong>{len(cards)}</strong><span>figures</span><strong id="gallery-visible-count">{len(cards)}</strong><span>visible</span></div>
  </header>
  <form class="gallery-tools" role="search">
    <label for="gallery-search">Search figures</label><input id="gallery-search" type="search" placeholder="Search title, data shape, or tag" autocomplete="off">
    <label for="gallery-tier">Priority</label><select id="gallery-tier"><option value="">All priorities</option><option>P0</option><option>P1</option><option>P2</option></select>
    <label for="gallery-category">Visual grammar</label><select id="gallery-category"><option value="">All grammars</option>{category_options}</select>
  </form>
  <section class="gallery-grid" aria-live="polite">{content}</section>
  <div id="gallery-no-results" class="gallery-filter-status" role="status" aria-live="polite" hidden><p>No figures match the current filters.</p><button id="gallery-clear-filters" type="button">Clear filters</button></div>
</main>
"""
    script = """
(function(){
  const search=document.getElementById('gallery-search');
  const tier=document.getElementById('gallery-tier');
  const category=document.getElementById('gallery-category');
  const count=document.getElementById('gallery-visible-count');
  const noResults=document.getElementById('gallery-no-results');
  const clear=document.getElementById('gallery-clear-filters');
  const cards=Array.from(document.querySelectorAll('.gallery-card'));
  function applyGalleryFilters(){
    const query=((search&&search.value)||'').trim().toLowerCase();
    let visible=0;
    cards.forEach(function(card){
      const matchQuery=!query||(card.dataset.search||'').includes(query);
      const matchTier=!tier||!tier.value||card.dataset.tier===tier.value;
      const matchCategory=!category||!category.value||card.dataset.category===category.value;
      card.hidden=!(matchQuery&&matchTier&&matchCategory);
      if(!card.hidden) visible+=1;
    });
    if(count) count.textContent=String(visible);
    if(noResults) noResults.hidden=visible!==0||cards.length===0;
  }
  [search,tier,category].forEach(function(control){if(control) control.addEventListener('input',applyGalleryFilters);});
  if(clear) clear.addEventListener('click',function(){if(search)search.value='';if(tier)tier.value='';if(category)category.value='';applyGalleryFilters();if(search)search.focus();});
})();
"""
    return _page("Scientific Figure Atlas", body, extra_js=script, nav_active="gallery", nav_scope="product", show_welcome=False)


def gallery_detail_page(*, chart: dict[str, Any] | None, chart_name: str = "") -> str:
    """Render one catalog record using only allowlisted local asset shapes."""
    if not isinstance(chart, dict):
        body = """
<main id="gallery-detail-main" class="gallery-missing">
  <p class="gallery-detail-kicker">Gallery ledger</p><h1>Figure not found</h1>
  <p>This catalog record is unavailable or has been retired.</p><a href="/gallery">Back to Gallery</a>
</main>
<style>.gallery-missing{max-width:640px;margin:70px auto;padding:40px 24px;border-top:1px solid var(--border);text-align:center}.gallery-missing h1{font:650 34px Georgia,serif}.gallery-missing p{color:var(--ink-muted)}.gallery-missing a{display:inline-flex;min-height:44px;align-items:center;color:var(--primary)}.gallery-detail-kicker{font:700 11px var(--font-mono);letter-spacing:.12em;text-transform:uppercase}</style>
"""
        return _page("Figure not found", body, nav_active="gallery", nav_scope="product", show_welcome=False)

    name = _text(chart.get("name") or chart_name).strip()
    title = _text(chart.get("title"), name) or name
    description = _text(chart.get("description"))
    tier = _text(chart.get("tier"), "P2") or "P2"
    status = _text(chart.get("status"), "planned") or "planned"
    data_type = _text(chart.get("data_type") or chart.get("input_shape"))
    tags = _items(chart.get("tags"))
    required = _items(chart.get("required_fields") or chart.get("required_columns") or chart.get("columns"))
    optional = _items(chart.get("optional_fields") or chart.get("optional_columns"))
    reusable = _items(chart.get("reusable_for") or chart.get("recommended_for"))
    encodings = chart.get("visual_encodings") if isinstance(chart.get("visual_encodings"), dict) else {}

    demo_url = _asset_url(chart.get("demo"), suffixes={".png", ".jpg", ".jpeg", ".webp", ".svg"})
    interactive_url = _asset_url(chart.get("interactive"), suffixes={".html", ".htm"})
    template_name = _template_name(chart)
    template_url = f"/api/gallery/template/{quote(template_name, safe='/')}" if template_name else None

    chips = lambda values, cls="detail-chip": "".join(_badge(value, cls) for value in values)
    demo = (
        f'<button class="detail-figure-button" type="button" aria-label="Open figure preview"><img src="{html.escape(demo_url, quote=True)}" alt="Preview of {html.escape(title, quote=True)}"></button>'
        if demo_url
        else '<div class="detail-no-figure"><span>Local figure unavailable</span><i aria-hidden="true"></i></div>'
    )
    interactive = (
        f'<section class="detail-panel detail-interactive"><div class="detail-panel-head"><p>Interactive artifact</p><span>Sandboxed</span></div><iframe src="{html.escape(interactive_url, quote=True)}" title="Interactive {html.escape(title, quote=True)}" sandbox="allow-scripts" loading="lazy"></iframe></section>'
        if interactive_url
        else ""
    )
    template = (
        f'<a class="detail-template-link" href="{template_url}"><span>{html.escape(template_name or "")}</span><small>Read local source</small></a>'
        if template_url
        else '<p class="detail-muted">No local script is linked to this record.</p>'
    )
    encoding_rows = "".join(
        f'<div><dt>{html.escape(_text(key))}</dt><dd>{html.escape(_text(value))}</dd></div>'
        for key, value in (encodings or {}).items()
    ) or '<div><dt>Encoding</dt><dd>Not specified</dd></div>'

    body = f"""
<style>
.detail-shell{{--sheet:#fffdf8;--sheet-warm:#f5efe3;--detail-ink:#27241f;--detail-muted:#716b61;--detail-line:#d9cebb;--detail-accent:#9b6729;max-width:1160px;margin:0 auto;padding:28px 24px 64px;color:var(--detail-ink)}}
.detail-back{{display:inline-flex;align-items:center;min-height:44px;color:var(--detail-accent);font:700 12px var(--font-mono);text-decoration:none}}
.detail-hero{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:24px;align-items:end;padding:8px 0 22px;border-bottom:1px solid var(--detail-line)}}
.detail-kicker{{margin:0 0 7px;font:700 11px var(--font-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--detail-accent)}}
.detail-hero h1{{margin:0;font:650 clamp(30px,5vw,52px)/1 Georgia,serif;letter-spacing:-.035em}}
.detail-summary{{max-width:680px;margin:11px 0 0;color:var(--detail-muted);font-size:14px;line-height:1.65}}
.detail-badges{{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}}.detail-badges span,.detail-chip{{display:inline-flex;align-items:center;min-height:26px;padding:2px 9px;border:1px solid var(--detail-line);border-radius:99px;background:var(--sheet);font:700 10px var(--font-mono);text-transform:uppercase;color:var(--detail-muted)}}
.detail-layout{{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(280px,.75fr);gap:18px;margin-top:18px;align-items:start}}
.detail-stack{{display:grid;gap:18px}}.detail-panel{{background:var(--sheet);border:1px solid var(--detail-line);border-radius:6px;overflow:hidden}}
.detail-panel-head{{display:flex;justify-content:space-between;gap:12px;align-items:center;min-height:43px;padding:0 15px;border-bottom:1px solid var(--detail-line);background:var(--sheet-warm)}}
.detail-panel-head p{{margin:0;font:700 11px var(--font-mono);letter-spacing:.09em;text-transform:uppercase}}.detail-panel-head span{{font:10px var(--font-mono);color:var(--detail-muted)}}
.detail-figure-button{{display:block;width:100%;padding:14px;border:0;background:#faf7f0;cursor:zoom-in}}.detail-figure-button:focus-visible{{outline:3px solid var(--detail-accent);outline-offset:-3px}}.detail-figure-button img{{display:block;width:100%;max-height:650px;object-fit:contain}}
.detail-no-figure{{display:grid;place-items:center;min-height:320px;color:var(--detail-muted);font:12px var(--font-mono)}}.detail-no-figure i{{display:block;width:42%;height:90px;border-bottom:1px solid #bda98b;background:linear-gradient(135deg,transparent 49%,#d9c9ad 50%,transparent 51%)}}
.detail-interactive iframe{{display:block;width:100%;height:520px;border:0;background:white}}
.detail-sheet{{padding:15px}}.detail-sheet h2{{margin:0 0 12px;font:650 18px Georgia,serif}}.detail-sheet h3{{margin:18px 0 7px;font:700 10px var(--font-mono);text-transform:uppercase;letter-spacing:.1em;color:var(--detail-accent)}}
.detail-chip-list{{display:flex;flex-wrap:wrap;gap:5px}}.detail-fields{{margin:0}}.detail-fields>div{{display:grid;grid-template-columns:minmax(90px,.45fr) 1fr;gap:12px;padding:9px 0;border-bottom:1px solid var(--detail-line)}}.detail-fields dt{{font:700 10px var(--font-mono);text-transform:uppercase;color:var(--detail-muted)}}.detail-fields dd{{margin:0;font-size:12px;overflow-wrap:anywhere}}
.detail-template-link{{display:flex;justify-content:space-between;align-items:center;min-height:48px;padding:0 12px;border:1px solid var(--detail-line);border-radius:4px;color:var(--detail-ink);text-decoration:none;font:12px var(--font-mono)}}.detail-template-link:hover{{border-color:var(--detail-accent)}}.detail-template-link small,.detail-muted{{color:var(--detail-muted)}}
.detail-dialog{{width:min(94vw,1100px);max-height:92vh;padding:14px;border:1px solid var(--detail-line);background:var(--sheet)}}.detail-dialog::backdrop{{background:rgba(31,28,23,.82)}}.detail-dialog img{{display:block;max-width:100%;max-height:82vh;margin:auto;object-fit:contain}}.detail-dialog button{{position:absolute;right:12px;top:12px;min-width:44px;min-height:44px;border:1px solid var(--detail-line);background:var(--sheet);font-size:22px;cursor:pointer}}
@media(max-width:820px){{.detail-layout{{grid-template-columns:1fr}}.detail-hero{{grid-template-columns:1fr}}.detail-badges{{justify-content:flex-start}}}}
@media(max-width:520px){{.detail-shell{{padding:20px 14px 48px}}.detail-fields>div{{grid-template-columns:1fr;gap:4px}}.detail-interactive iframe{{height:430px}}}}
</style>
<main id="gallery-detail-main" class="detail-shell">
  <a class="detail-back" href="/gallery">← Figure atlas</a>
  <header class="detail-hero"><div><p class="detail-kicker">Scientific figure · local artifact</p><h1>{html.escape(title)}</h1><p class="detail-summary">{html.escape(description)}</p></div><div class="detail-badges">{_badge(tier, 'detail-tier')}{_badge(status, 'detail-status')}</div></header>
  <div class="detail-layout">
    <div class="detail-stack"><section class="detail-panel"><div class="detail-panel-head"><p>Rendered figure</p><span>Local asset</span></div>{demo}</section>{interactive}</div>
    <aside class="detail-stack">
      <section class="detail-panel detail-sheet"><h2>Figure ledger</h2><dl class="detail-fields"><div><dt>Data shape</dt><dd>{html.escape(data_type or 'Not specified')}</dd></div>{encoding_rows}</dl><h3>Required fields</h3><div class="detail-chip-list">{chips(required) or '<span class="detail-muted">None specified</span>'}</div><h3>Optional fields</h3><div class="detail-chip-list">{chips(optional) or '<span class="detail-muted">None specified</span>'}</div><h3>Reusable for</h3><div class="detail-chip-list">{chips(reusable) or '<span class="detail-muted">General use</span>'}</div><h3>Tags</h3><div class="detail-chip-list">{chips(tags) or '<span class="detail-muted">Unlabelled</span>'}</div></section>
      <section class="detail-panel detail-sheet"><h2>Script record</h2>{template}</section>
    </aside>
  </div>
  <dialog class="detail-dialog" aria-label="Figure preview"><button type="button" aria-label="Close preview">×</button>{f'<img src="{html.escape(demo_url, quote=True)}" alt="Expanded preview of {html.escape(title, quote=True)}">' if demo_url else ''}</dialog>
</main>
"""
    script = """
(function(){
  const opener=document.querySelector('.detail-figure-button');
  const dialog=document.querySelector('.detail-dialog');
  const closer=dialog&&dialog.querySelector('button');
  if(!opener||!dialog||!closer) return;
  opener.addEventListener('click',function(){dialog.showModal();closer.focus();});
  closer.addEventListener('click',function(){dialog.close();});
  dialog.addEventListener('click',function(event){if(event.target===dialog) dialog.close();});
  dialog.addEventListener('close',function(){opener.focus();});
})();
"""
    return _page(f"{title} — Figure Atlas", body, extra_js=script, nav_active="gallery", nav_scope="product", show_welcome=False)
