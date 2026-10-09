from __future__ import annotations

import html
from datetime import datetime, timezone
from urllib.parse import quote

from .templates import _DARK_CSS


def _e(value: object, *, attr: bool = False) -> str:
    return html.escape(str(value), quote=attr)


def _proposal_rows(proposals: list[dict]) -> str:
    if not proposals:
        return '''<div class="ledger-empty">
          <span class="ledger-check" aria-hidden="true">✓</span>
          <div><strong>No decisions waiting</strong><p>The proposal ledger is clear.</p></div>
          <a href="/knowledge">Browse knowledge</a>
        </div>'''
    rows: list[str] = []
    for proposal in proposals[:4]:
        proposal_id = str(proposal.get("proposal_id") or "").strip()
        summary = " ".join(str(proposal.get("summary") or proposal.get("observation") or proposal.get("suggested_memory") or "Untitled proposal").split())
        if len(summary) > 180:
            summary = summary[:177].rstrip() + "…"
        risk = str(proposal.get("risk_level") or "review")
        href = f"/review/{quote(proposal_id, safe='')}" if proposal_id else "/proposals"
        rows.append(f'''<a class="ledger-row" href="{_e(href, attr=True)}">
          <i aria-hidden="true"></i><span><strong>{_e(summary)}</strong><small>Proposal · {_e(risk)} risk</small></span>
          <code>{_e(proposal_id)}</code><em>Review →</em></a>''')
    return "".join(rows)


def _recent_rows(nodes: list[dict]) -> str:
    if not nodes:
        return '<div class="recent-empty">No knowledge entries yet. The ledger is ready for its first record.</div>'
    rows: list[str] = []
    for node in nodes[:5]:
        node_id = str(node.get("id") or "")
        summary = " ".join(str(node.get("summary") or "Untitled knowledge").split())
        if len(summary) > 140:
            summary = summary[:137].rstrip() + "…"
        stage = str(node.get("stage") or "draft")
        category = str(node.get("category") or "knowledge")
        created = str(node.get("created_at") or "")[:10] or "undated"
        href = f"/knowledge/{quote(node_id, safe='')}" if node_id else "/knowledge"
        rows.append(f'''<a class="recent-row" href="{_e(href, attr=True)}">
          <span class="stage-stamp stage-{_e(stage, attr=True)}">{_e(stage)}</span>
          <span><strong>{_e(summary)}</strong><small>{_e(category)} · {_e(created)}</small></span><b aria-hidden="true">→</b></a>''')
    return "".join(rows)


def home_page(
    *,
    node_counts: dict[str, int],
    chart_count: int,
    health_summary: dict,
    recent_nodes: list | None = None,
    proposal_counts: dict | None = None,
    knowledge_health: dict | None = None,
    lifecycle_overview: dict | None = None,
    pending_proposals: list | None = None,
) -> str:
    """Render the Engram home: a quiet entry to Knowledge and Gallery."""
    proposal_counts = proposal_counts or {}
    knowledge_health = knowledge_health or health_summary or {}
    lifecycle_overview = lifecycle_overview or {}
    recent_nodes = recent_nodes or []
    pending_proposals = pending_proposals or []

    stages = ("draft", "refined", "verified", "canonized", "deprecated")
    counts = {stage: int(node_counts.get(stage, 0) or 0) for stage in stages}
    total_nodes = sum(counts.values())
    maintained = counts["verified"] + counts["canonized"]
    pending_count = max(int(proposal_counts.get("pending", 0) or 0), len(pending_proposals))
    proposal_sync = lifecycle_overview.get("proposal_sync", {})
    if not isinstance(proposal_sync, dict):
        proposal_sync = {}
    maintenance_count = sum(int(knowledge_health.get(key, 0) or 0) for key in ("dirty_nodes", "conflict_count", "quarantined")) + int(proposal_sync.get("missing", 0) or 0)
    max_count = max(counts.values()) or 1
    stage_cells = "".join(f'''<div class="stage-cell"><div class="stage-bar" aria-hidden="true"><i style="height:{max(4, round(counts[stage] / max_count * 100))}%"></i></div><strong>{counts[stage]}</strong><span>{stage}</span></div>''' for stage in stages)
    rendered_at = datetime.now(timezone.utc).strftime("%Y-%m-%d · %H:%M UTC")

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#ffffff"><title>Engram · Brain</title>
<style>{_DARK_CSS}
:root{{--column:1120px;--paper:var(--card);--ink-soft:var(--ink-muted);--hairline:var(--border);--hairline-dark:var(--border-hover);--oxide:var(--primary);--oxide-soft:var(--primary-muted);--moss:var(--success);--moss-soft:var(--success-muted);--gold:var(--warning);--gold-soft:var(--warning-muted)}}
*{{box-sizing:border-box}}html{{background:var(--bg);color:var(--ink);font-family:var(--font)}}body{{margin:0;min-height:100vh;background:var(--bg)}}a{{color:inherit}}a:focus-visible{{outline:3px solid var(--border-focus);outline-offset:3px}}.skip-link{{position:fixed;left:16px;top:8px;z-index:40;padding:10px 14px;background:var(--card);border:1px solid var(--border-focus);transform:translateY(-150%);text-decoration:none}}.skip-link:focus{{transform:translateY(0)}}.engram-home{{min-height:100vh}}
.engram-topbar{{height:68px;border-bottom:1px solid var(--border);background:var(--card);display:flex;align-items:center;justify-content:space-between;padding:0 max(24px,calc((100vw - var(--column))/2));position:sticky;top:0;z-index:20}}.engram-brand{{display:flex;align-items:center;gap:12px;text-decoration:none}}.brand-glyph{{width:30px;height:30px;border:1px solid var(--border-hover);display:grid;place-items:center;font:600 16px Georgia,serif;background:var(--surface)}}.engram-brand strong{{display:block;font:600 14px Georgia,serif;letter-spacing:.08em}}.engram-brand small{{display:block;color:var(--ink-muted);font-size:9px;letter-spacing:.14em;margin-top:2px}}.engram-nav{{display:flex;align-items:center;gap:6px}}.engram-nav a{{min-height:38px;padding:9px 13px;text-decoration:none;color:var(--ink-muted);font-size:13px;border-bottom:1px solid transparent}}.engram-nav a:hover{{color:var(--ink);border-color:var(--ink)}}.engram-nav a:focus-visible{{color:var(--ink);border-color:var(--ink);outline:3px solid var(--border-focus);outline-offset:2px}}.engram-nav .utility{{font-size:12px;margin-left:12px}}.opening-link{{display:inline-flex;align-items:center;gap:7px}}.opening-link:before{{content:"";width:6px;height:6px;border-radius:50%;background:var(--ink)}}
.engram-main{{max-width:var(--column);margin:0 auto;padding:48px 24px 80px}}.ledger-intro{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:32px;align-items:end;padding-bottom:26px;border-bottom:1px solid var(--hairline)}}.ledger-kicker{{margin:0 0 10px;color:var(--oxide);font-size:10px;font-weight:700;letter-spacing:.18em;text-transform:uppercase}}.ledger-intro h1{{margin:0;font:500 clamp(30px,4vw,46px)/1.06 Georgia,"Times New Roman",serif;letter-spacing:-.035em}}.ledger-intro h1 em{{font-weight:400;color:var(--ink-soft)}}.ledger-intro .lede{{max-width:590px;margin:14px 0 0;color:var(--ink-soft);font-size:14px;line-height:1.7}}.ledger-date{{text-align:right;color:var(--ink-soft);font-size:11px;letter-spacing:.04em}}.ledger-date strong{{display:block;color:var(--ink);font:500 20px Georgia,serif;margin-bottom:5px}}
.ledger-grid{{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(280px,.75fr);gap:22px;margin-top:22px}}.ledger-panel{{border:1px solid var(--hairline);background:var(--card)}}.panel-head{{min-height:54px;padding:13px 16px;border-bottom:1px solid var(--hairline);display:flex;align-items:center;justify-content:space-between;gap:16px}}.panel-head h2{{margin:0;font:600 14px Georgia,serif;letter-spacing:.02em}}.panel-head p{{margin:2px 0 0;color:var(--ink-soft);font-size:11px}}.panel-head a{{color:var(--oxide);font-size:12px;text-decoration:none;white-space:nowrap}}.panel-head a:hover{{text-decoration:underline}}
.ledger-list{{padding:0 16px}}.ledger-row{{display:grid;grid-template-columns:8px minmax(0,1fr) auto 68px;gap:12px;align-items:center;min-height:66px;border-bottom:1px solid var(--hairline);text-decoration:none}}.ledger-row:last-child{{border-bottom:0}}.ledger-row:hover strong{{color:var(--oxide)}}.ledger-row i{{width:6px;height:6px;border-radius:50%;background:var(--oxide);box-shadow:0 0 0 4px var(--oxide-soft)}}.ledger-row span strong,.ledger-row span small{{display:block}}.ledger-row span strong{{font-size:13px;line-height:1.4}}.ledger-row span small{{margin-top:4px;color:var(--ink-soft);font-size:11px}}.ledger-row code{{max-width:110px;overflow:hidden;text-overflow:ellipsis;color:var(--ink-soft);font-size:10px}}.ledger-row em{{color:var(--oxide);font-size:11px;font-style:normal;text-align:right}}.ledger-empty{{min-height:130px;display:grid;grid-template-columns:34px 1fr auto;align-items:center;gap:14px;padding:20px}}.ledger-check{{width:30px;height:30px;display:grid;place-items:center;border:1px solid var(--border);color:var(--moss);background:var(--moss-soft)}}.ledger-empty strong{{font:600 14px Georgia,serif}}.ledger-empty p{{margin:4px 0 0;color:var(--ink-soft);font-size:12px}}.ledger-empty a{{color:var(--oxide);font-size:12px}}
.lifecycle{{padding:18px 17px 16px}}.lifecycle-summary{{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:16px}}.lifecycle-summary strong{{font:500 32px Georgia,serif}}.lifecycle-summary span{{color:var(--ink-soft);font-size:11px}}.stage-track{{height:140px;display:grid;grid-template-columns:repeat(5,1fr);gap:9px;border-bottom:1px solid var(--hairline)}}.stage-cell{{display:grid;grid-template-rows:1fr auto auto;min-width:0;text-align:center}}.stage-bar{{align-self:end;height:80px;display:flex;align-items:end;justify-content:center;border-left:1px solid var(--border)}}.stage-cell:first-child .stage-bar{{border-left:0}}.stage-bar i{{display:block;width:8px;min-height:4px;background:var(--gold)}}.stage-cell strong{{font:500 17px Georgia,serif;margin-top:7px}}.stage-cell span{{overflow:hidden;text-overflow:ellipsis;color:var(--ink-soft);font-size:9px;text-transform:uppercase;letter-spacing:.06em}}.maintenance-note{{margin:16px 0 0;padding-top:12px;border-top:1px solid var(--hairline);color:var(--ink-soft);font-size:11px}}.maintenance-note strong{{color:var(--ink)}}
.module-grid{{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:22px}}.module-card{{position:relative;min-height:210px;padding:22px;border:1px solid var(--hairline);background:var(--paper);text-decoration:none;overflow:hidden}}.module-card:before{{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--gold)}}.module-card.gallery:before{{background:var(--oxide)}}.module-index{{display:flex;align-items:center;justify-content:space-between;color:var(--ink-soft);font-size:10px;letter-spacing:.12em;text-transform:uppercase}}.module-index b{{font:400 34px Georgia,serif;color:var(--hairline-dark)}}.module-card h2{{margin:27px 0 7px;font:500 24px Georgia,serif}}.module-card p{{max-width:430px;margin:0;color:var(--ink-soft);font-size:13px;line-height:1.65}}.module-facts{{position:absolute;left:22px;right:22px;bottom:19px;display:flex;gap:19px;padding-top:12px;border-top:1px solid var(--hairline);color:var(--ink-soft);font-size:11px}}.module-facts strong{{color:var(--ink);font-weight:600}}.module-arrow{{margin-left:auto;color:var(--oxide)}}.module-card:hover{{border-color:var(--hairline-dark);background:var(--surface)}}.module-card:focus-visible{{outline:3px solid var(--oxide);outline-offset:3px;border-color:var(--oxide);background:var(--surface)}}
.recent-panel{{margin-top:22px}}.recent-list{{padding:0 16px}}.recent-row{{display:grid;grid-template-columns:88px minmax(0,1fr) 20px;gap:14px;align-items:center;min-height:62px;border-bottom:1px solid var(--hairline);text-decoration:none}}.recent-row:last-child{{border-bottom:0}}.recent-row strong,.recent-row small{{display:block}}.recent-row strong{{font-size:13px}}.recent-row small{{margin-top:3px;color:var(--ink-soft);font-size:11px}}.recent-row:hover strong{{color:var(--oxide)}}.stage-stamp{{display:inline-flex;width:max-content;max-width:88px;padding:3px 7px;border:1px solid var(--hairline-dark);color:var(--ink-soft);font-size:9px;text-transform:uppercase;letter-spacing:.07em}}.stage-canonized,.stage-verified{{border-color:var(--border);color:var(--moss);background:var(--moss-soft)}}.stage-draft{{border-color:var(--border);color:var(--warning);background:var(--gold-soft)}}.recent-empty{{padding:28px 16px;color:var(--ink-soft);font-size:12px}}.engram-foot{{display:flex;justify-content:space-between;gap:20px;margin-top:30px;padding-top:17px;border-top:1px solid var(--hairline);color:var(--ink-soft);font-size:10px}}.engram-foot span:last-child{{text-align:right}}
@media(max-width:760px){{.engram-topbar{{height:auto;min-height:62px;padding:10px 16px}}.engram-brand small{{display:none}}.engram-nav{{gap:0}}.engram-nav a{{min-height:44px;padding:11px 8px}}.engram-nav .utility{{margin-left:0}}.engram-main{{padding:32px 16px 60px}}.ledger-intro{{grid-template-columns:1fr}}.ledger-date{{display:none}}.ledger-grid,.module-grid{{grid-template-columns:1fr}}.ledger-row{{grid-template-columns:8px minmax(0,1fr) 58px}}.ledger-row code{{display:none}}.ledger-empty{{grid-template-columns:34px 1fr}}.ledger-empty>a{{grid-column:2}}.module-card{{min-height:225px}}.panel-head a,.ledger-empty a{{display:inline-flex;align-items:center;min-height:44px;padding-block:8px}}.engram-foot{{display:block}}.engram-foot span{{display:block;margin-top:5px;text-align:left!important}}}}
@media(max-width:380px){{.engram-topbar{{flex-wrap:wrap;align-items:flex-start;gap:4px;padding:8px 12px}}.engram-brand{{min-height:44px}}.engram-nav{{width:100%;display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}}.engram-nav a{{flex:1;justify-content:center;text-align:center;padding-inline:3px;font-size:12px}}.engram-main{{padding-inline:12px}}.ledger-row,.recent-row{{min-width:0}}.ledger-row>span,.recent-row>span{{min-width:0;overflow:hidden}}.ledger-row strong,.ledger-row small,.recent-row strong,.recent-row small{{overflow-wrap:anywhere;word-break:break-word}}.ledger-row em{{white-space:normal}}.stage-stamp{{min-width:0;max-width:88px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}}}
</style><script>(function(){{var t=localStorage.getItem('hermes_theme');if(t==='light'||t==='modern-dark')document.documentElement.setAttribute('data-theme',t);}})();document.addEventListener('DOMContentLoaded',function(){{var b=document.getElementById('home-theme-toggle');if(b)b.addEventListener('click',function(){{var h=document.documentElement;var t=h.getAttribute('data-theme')==='modern-dark'?'light':'modern-dark';h.setAttribute('data-theme',t);localStorage.setItem('hermes_theme',t);}});}});</script></head><body><div class="engram-home">
<a class="skip-link" href="#main-content">Skip to main content</a><header class="engram-topbar"><a class="engram-brand" href="/" aria-current="page" aria-label="Engram home"><span class="brand-glyph" aria-hidden="true">E</span><span><strong>ENGRAM</strong><small>EXPERIENCE LEDGER</small></span></a><nav class="engram-nav" aria-label="Primary navigation"><a href="/knowledge">Knowledge</a><a href="/gallery">Gallery</a><a class="opening-link" href="/opening/">Opening</a><button class="theme-toggle" type="button" id="home-theme-toggle" aria-label="Toggle theme">◐</button><form method="post" action="/logout"><button class="utility" type="submit">Log out</button></form></nav></header>
<main class="engram-main" id="main-content" tabindex="-1"><section class="ledger-intro" id="engram-ledger"><div><p class="ledger-kicker">Brain · Experience ledger</p><h1>Trace what was learned.<br><em>Keep what holds.</em></h1><p class="lede">A quiet index of maintained knowledge, pending decisions, and reusable scientific visual forms.</p></div><div class="ledger-date"><strong>{total_nodes:02d}</strong>knowledge records<br>{_e(rendered_at)}</div></section>
<section class="module-grid" aria-label="Brain modules"><a class="module-card knowledge" id="engram-knowledge" href="/knowledge"><div class="module-index"><span>Module 01 · Maintained corpus</span><b aria-hidden="true">K</b></div><h2>Knowledge</h2><p>Browse the graph, trace provenance, review proposals, and follow each record through its explicit lifecycle.</p><div class="module-facts"><span><strong>{total_nodes}</strong> records</span><span><strong>{pending_count}</strong> pending</span><span class="module-arrow">Enter →</span></div></a>
<a class="module-card gallery" id="engram-gallery" href="/gallery"><div class="module-index"><span>Module 02 · Visual methods</span><b aria-hidden="true">G</b></div><h2>Gallery</h2><p>Reuse verified scientific figure patterns captured from prior work, with their method and provenance intact.</p><div class="module-facts"><span><strong>{chart_count}</strong> catalogued forms</span><span class="module-arrow">Enter →</span></div></a></section>
<div class="ledger-grid"><section class="ledger-panel" aria-labelledby="decision-title"><div class="panel-head"><div><h2 id="decision-title">Decision ledger</h2><p>Knowledge proposals that need an explicit review.</p></div><a href="/proposals">Open queue · {pending_count}</a></div><div class="ledger-list">{_proposal_rows(pending_proposals)}</div></section>
<section class="ledger-panel" aria-labelledby="lifecycle-title"><div class="panel-head"><div><h2 id="lifecycle-title">Lifecycle index</h2><p>Current state of the maintained corpus.</p></div><a href="/knowledge">Inspect</a></div><div class="lifecycle"><div class="lifecycle-summary"><strong>{maintained}</strong><span>verified or canonized</span></div><div class="stage-track">{stage_cells}</div><p class="maintenance-note"><strong>{maintenance_count}</strong> maintenance signal{'s' if maintenance_count != 1 else ''} across metadata, conflicts, quarantine, and proposal links.</p></div></section></div>
<section class="ledger-panel recent-panel" aria-labelledby="recent-title"><div class="panel-head"><div><h2 id="recent-title">Recent ledger entries</h2><p>The latest records available to the knowledge system.</p></div><a href="/knowledge">View all</a></div><div class="recent-list">{_recent_rows(recent_nodes)}</div></section>
<footer class="engram-foot"><span>Engram keeps product scope to Home, Knowledge, and Gallery.</span><span>Explicit review · durable provenance · no remote poster fetch</span></footer></main></div></body></html>'''