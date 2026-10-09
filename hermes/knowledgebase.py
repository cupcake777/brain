"""Isolated Knowledge graph/list/filter renderer for the Engram shell."""

from __future__ import annotations

import html
from collections import Counter
from urllib.parse import quote, urlencode

from .templates import _page

_STAGES = ("draft", "refined", "verified", "canonized", "deprecated")
_STAGE_LABELS = {
    "draft": "Draft",
    "refined": "Refined",
    "verified": "Verified",
    "canonized": "Canonized",
    "deprecated": "Deprecated",
}


def _e(value: object, *, attr: bool = False) -> str:
    return html.escape(str(value if value is not None else ""), quote=attr)


def _url(**params: object) -> str:
    clean = [(key, str(value)) for key, value in params.items() if value not in (None, "", "all")]
    query = urlencode(clean)
    return "/knowledge" + (f"?{query}" if query else "")


def _node_url(node_id: object) -> str:
    return "/knowledge/" + quote(str(node_id if node_id is not None else ""), safe="")


def knowledge_tree_page(
    *,
    nodes: list[dict],
    counts: dict[str, int],
    active_stage: str = "all",
    active_category: str = "",
    active_domain: str = "",
    domains: list[str] | None = None,
    query: str = "",
    view: str = "list",
) -> str:
    """Render the human-facing Knowledge index without proposal/detail actions."""
    domains = domains or []
    view = view if view in {"list", "graph"} else "list"
    categories = sorted({str(node.get("category") or "fact") for node in nodes})
    total = sum(int(value or 0) for value in counts.values())

    shared = {
        "stage": active_stage,
        "category": active_category,
        "domain": active_domain,
        "q": query,
    }
    list_url = _url(view="list", **shared)
    graph_url = _url(view="graph", **shared)

    stage_options = ['<option value="all">All stages</option>']
    for stage in _STAGES:
        selected = " selected" if stage == active_stage else ""
        stage_options.append(
            f'<option value="{stage}"{selected}>{_STAGE_LABELS[stage]} · {int(counts.get(stage, 0) or 0)}</option>'
        )

    category_options = ['<option value="">All categories</option>']
    for category in categories:
        selected = " selected" if category == active_category else ""
        category_options.append(
            f'<option value="{_e(category, attr=True)}"{selected}>{_e(category)}</option>'
        )

    domain_options = ['<option value="">All domains</option>']
    for domain in sorted({str(item) for item in domains if item}):
        selected = " selected" if domain == active_domain else ""
        domain_options.append(
            f'<option value="{_e(domain, attr=True)}"{selected}>{_e(domain)}</option>'
        )

    rows = "".join(_node_row(node) for node in nodes)
    if not rows:
        rows = (
            '<div class="knowledge-empty" role="status">'
            '<strong>No knowledge entries match this view.</strong>'
            '<span>Clear a filter or return when new evidence has been integrated.</span>'
            "</div>"
        )

    graph = _graph(nodes)
    content = rows if view == "list" else graph
    active_label = "List" if view == "list" else "Graph"

    body = f"""
<a class="knowledge-skip" href="#knowledge-results">Skip to knowledge results</a>
<main class="engram-knowledge" data-view="{view}">
  <header class="knowledge-head">
    <div>
      <p class="knowledge-kicker">ENGRAM / KNOWLEDGE</p>
      <h1>Knowledge ledger</h1>
      <p>Trace claims through lifecycle, domain and provenance without exposing operational surfaces.</p>
    </div>
    <div class="knowledge-total" aria-label="{total} total knowledge nodes"><strong>{total}</strong><span>total nodes</span></div>
  </header>

  <nav class="knowledge-views" aria-label="Knowledge views">
    <a href="{_e(list_url, attr=True)}" aria-current="{'page' if view == 'list' else 'false'}">List</a>
    <a href="{_e(graph_url, attr=True)}" aria-current="{'page' if view == 'graph' else 'false'}">Graph</a>
  </nav>

  <form id="knowledge-filter-form" class="knowledge-filters" method="get" action="/knowledge" aria-label="Filter knowledge">
    <input type="hidden" name="view" value="{view}">
    <label><span>Stage</span><select name="stage">{''.join(stage_options)}</select></label>
    <label><span>Category</span><select name="category">{''.join(category_options)}</select></label>
    <label><span>Domain</span><select name="domain">{''.join(domain_options)}</select></label>
    <label class="knowledge-query"><span>Search</span><input type="search" name="q" value="{_e(query, attr=True)}" placeholder="Search summary or content"></label>
    <button type="submit">Apply filters</button>
    <a href="/knowledge?view={view}">Clear</a>
  </form>

  <section class="knowledge-results-head" aria-live="polite">
    <h2>{active_label}</h2><span>{len(nodes)} shown</span>
  </section>
  <section id="knowledge-results" class="knowledge-results knowledge-{view}" aria-label="Knowledge {active_label.lower()} results">
    {content}
  </section>
</main>
<style>
.engram-knowledge{{--paper:var(--card);--ink:var(--ink);--muted:var(--ink-muted);--line:var(--border);--oxide:var(--primary);max-width:1180px;margin:0 auto;padding:28px 24px 64px;color:var(--ink)}}
.knowledge-skip{{position:fixed;left:12px;top:-60px;z-index:1000;background:#fff;color:#24231f;border:1px solid #24231f;padding:10px 14px}}.knowledge-skip:focus{{top:12px}}
.knowledge-head{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:24px;align-items:end;border-bottom:1px solid var(--line);padding-bottom:22px}}.knowledge-kicker{{font:700 .72rem/1.2 ui-monospace,monospace;letter-spacing:.14em;color:var(--oxide);margin:0 0 10px}}.knowledge-head h1{{font-size:clamp(1.8rem,4vw,3rem);letter-spacing:-.045em;margin:0}}.knowledge-head p:last-child{{max-width:670px;color:var(--muted);line-height:1.6;margin:10px 0 0}}.knowledge-total{{display:flex;flex-direction:column;align-items:flex-end}}.knowledge-total strong{{font:700 2rem/1 ui-monospace,monospace}}.knowledge-total span{{font-size:.75rem;color:var(--muted)}}
.knowledge-views{{display:flex;border-bottom:1px solid var(--line);margin-top:18px}}.knowledge-views a{{min-height:44px;display:flex;align-items:center;padding:0 18px;color:var(--muted);text-decoration:none;border-bottom:2px solid transparent}}.knowledge-views a[aria-current="page"]{{color:var(--ink);border-color:var(--oxide);font-weight:700}}
.knowledge-filters{{display:grid;grid-template-columns:repeat(3,minmax(130px,1fr)) minmax(220px,2fr) auto auto;gap:10px;align-items:end;padding:18px 0;border-bottom:1px solid var(--line)}}.knowledge-filters label{{display:grid;gap:5px}}.knowledge-filters label span{{font:700 .7rem/1.2 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}}.knowledge-filters select,.knowledge-filters input,.knowledge-filters button,.knowledge-filters>a{{box-sizing:border-box;min-height:44px;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:10px 12px;border-radius:var(--r-sm);font:inherit}}.knowledge-filters button{{background:var(--primary);color:var(--primary-fg);cursor:pointer}}.knowledge-filters>a{{display:flex;align-items:center;text-decoration:none}}
.knowledge-filters :focus-visible,.knowledge-views a:focus-visible,.knowledge-row:focus-visible{{outline:3px solid var(--oxide);outline-offset:3px}}
.knowledge-results-head{{display:flex;justify-content:space-between;align-items:center;padding:22px 0 10px}}.knowledge-results-head h2{{margin:0;font-size:1rem}}.knowledge-results-head span{{font:600 .75rem/1 ui-monospace,monospace;color:var(--muted)}}
.knowledge-list{{display:grid;border-top:1px solid var(--line)}}.knowledge-row{{display:grid;grid-template-columns:110px minmax(0,1fr) 150px 90px;gap:16px;padding:16px 6px;border-bottom:1px solid var(--line);text-decoration:none;color:inherit;min-width:0}}.knowledge-row:hover{{background:rgba(158,68,45,.045)}}.knowledge-stage{{font:700 .7rem/1.3 ui-monospace,monospace;text-transform:uppercase;color:var(--oxide)}}.knowledge-copy{{min-width:0}}.knowledge-copy strong{{display:block;overflow-wrap:anywhere}}.knowledge-copy span{{display:block;color:var(--muted);font-size:.82rem;line-height:1.5;margin-top:5px;overflow-wrap:anywhere}}.knowledge-meta{{font-size:.76rem;color:var(--muted);overflow-wrap:anywhere}}.knowledge-confidence{{font:700 .78rem/1.3 ui-monospace,monospace;text-align:right}}
.knowledge-empty{{display:grid;gap:7px;padding:52px 16px;text-align:center;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}.knowledge-empty span{{color:var(--muted)}}
.knowledge-graph{{overflow:auto;border:1px solid var(--line);background:var(--paper);min-height:420px}}.knowledge-graph svg{{display:block;width:100%;min-width:720px;height:auto}}.knowledge-graph text{{fill:var(--ink);font-family:ui-monospace,monospace}}.knowledge-graph .graph-edge{{stroke:#b9b0a0;stroke-width:1.5}}.knowledge-graph .graph-node{{fill:#fff;stroke:var(--oxide);stroke-width:2}}
@media(max-width:900px){{.knowledge-filters{{grid-template-columns:repeat(2,minmax(0,1fr))}}.knowledge-query{{grid-column:1/-1}}.knowledge-row{{grid-template-columns:90px minmax(0,1fr) 120px}}.knowledge-confidence{{display:none}}}}
@media(max-width:560px){{.engram-knowledge{{padding:20px 14px 48px}}.knowledge-head{{grid-template-columns:1fr}}.knowledge-total{{align-items:flex-start}}.knowledge-filters{{grid-template-columns:1fr}}.knowledge-query{{grid-column:auto}}.knowledge-row{{grid-template-columns:1fr;gap:6px;padding:16px 2px}}.knowledge-meta{{display:flex;gap:8px}}}}
@media(prefers-reduced-motion:reduce){{.engram-knowledge *{{scroll-behavior:auto!important;transition:none!important}}}}
</style>
"""
    return _page("Knowledge", body, nav_active="knowledge", nav_scope="product", show_welcome=False)


def _node_row(node: dict) -> str:
    node_id = str(node.get("id") or "")
    summary = str(node.get("summary") or "Untitled knowledge")
    content = str(node.get("content") or "")
    preview = content[:180] + ("…" if len(content) > 180 else "")
    stage = str(node.get("stage") or "draft")
    category = str(node.get("category") or "fact")
    domain = str(node.get("domain") or "general")
    try:
        confidence = max(0, min(100, round(float(node.get("confidence") or 0) * 100)))
    except (TypeError, ValueError):
        confidence = 0
    return (
        f'<a class="knowledge-row" href="{_e(_node_url(node_id), attr=True)}">'
        f'<span class="knowledge-stage">{_e(stage)}</span>'
        f'<span class="knowledge-copy"><strong>{_e(summary)}</strong><span>{_e(preview)}</span></span>'
        f'<span class="knowledge-meta">{_e(domain)} · {_e(category)}</span>'
        f'<span class="knowledge-confidence" aria-label="Confidence {confidence} percent">{confidence}%</span>'
        "</a>"
    )


def _graph(nodes: list[dict]) -> str:
    if not nodes:
        return '<div class="knowledge-empty" role="status"><strong>No graph to draw.</strong><span>Graph connections appear when filtered nodes are available.</span></div>'
    positions: dict[str, tuple[int, int]] = {}
    width = 960
    row_gap = 120
    col_gap = 220
    for index, node in enumerate(nodes):
        positions[str(node.get("id") or "")] = (90 + (index % 4) * col_gap, 70 + (index // 4) * row_gap)
    edges: list[tuple[str, str]] = []
    for node in nodes:
        target = str(node.get("id") or "")
        for key in ("parent_id", "supersedes"):
            source = str(node.get(key) or "")
            if source in positions and target in positions:
                edges.append((source, target))
    height = max(420, 140 + ((len(nodes) - 1) // 4) * row_gap)
    lines = "".join(
        f'<line class="graph-edge" x1="{positions[a][0]}" y1="{positions[a][1]}" x2="{positions[b][0]}" y2="{positions[b][1]}" />'
        for a, b in edges
    )
    marks = ""
    for node in nodes:
        node_id = str(node.get("id") or "")
        x, y = positions[node_id]
        label = str(node.get("summary") or node_id)
        if len(label) > 24:
            label = label[:23] + "…"
        marks += (
            f'<a href="{_e(_node_url(node_id), attr=True)}" aria-label="{_e(str(node.get("summary") or node_id), attr=True)}">'
            f'<circle class="graph-node" cx="{x}" cy="{y}" r="12"><title>{_e(str(node.get("summary") or node_id))}</title></circle>'
            f'<text x="{x + 20}" y="{y + 4}" font-size="12">{_e(label)}</text></a>'
        )
    stages = Counter(str(node.get("stage") or "draft") for node in nodes)
    legend = " · ".join(f"{_e(stage)} {count}" for stage, count in sorted(stages.items()))
    return (
        f'<div class="knowledge-graph" role="img" aria-label="Knowledge relationship graph. {len(nodes)} nodes, {len(edges)} connections. {legend}">'
        f'<svg viewBox="0 0 {width} {height}" aria-hidden="true">{lines}{marks}</svg></div>'
    )
