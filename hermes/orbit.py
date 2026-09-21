from __future__ import annotations

"""Orbit visual system, wired to real Brain data.

This reuses the void/daybreak visual language from the standalone
hermes-workspace-prototype (commit 4c49162, never deployed) but replaces
every fabricated data point (8 fake agent nodes, a fake 24h stability wave,
a JS setInterval that invents a new trace line every 5.2s, a fake 12/126
signal spectrum) with values read from the real Brain repository and the
real linuxdo signal board. Anything with no real source is shown as an
honest empty state instead of being invented.

Follows the same server-renders-a-string-of-HTML/CSS/JS pattern as
hermes/cassette.py: no client-side mock arrays, only `fetch()` calls
against endpoints that already exist and are already authenticated via the
same-origin session cookie.
"""

import html
import json
from datetime import datetime, timezone
from typing import Any


def _e(value: object, *, quote: bool = False) -> str:
    return html.escape(str(value), quote=quote)


def _summary(value: object, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


AGENT_LABELS = {
    "hermes": "Hermes",
    "codex": "Codex",
    "claude": "Claude Code",
    "gemini": "Gemini",
    "grok": "Grok",
    "bare-markdown": "Auto-ingest",
}

# Fixed field-stage layout slots (x%, y%, size px). Real agents are placed
# into these slots in order of real proposal volume; unused slots are
# simply not rendered (no filler nodes).
_FIELD_SLOTS = [
    (47, 44, 25), (26, 31, 15), (70, 25, 13), (64, 54, 17),
    (34, 69, 13), (59, 73, 12), (15, 55, 10), (86, 37, 10),
]


def _build_agent_nodes(proposals: list[dict], fleet_summary: dict) -> list[dict]:
    """Rank real source_agent activity from Brain proposals into node slots."""
    counts: dict[str, dict[str, Any]] = {}
    for p in proposals:
        key = str(p.get("source_agent") or "").strip().lower()
        label = AGENT_LABELS.get(key)
        if not label:
            continue
        row = counts.setdefault(key, {"label": label, "count": 0, "latest": ""})
        row["count"] += 1
        created = str(p.get("created_at") or "")
        if created > row["latest"]:
            row["latest"] = created

    ranked = sorted(counts.items(), key=lambda kv: kv[1]["count"], reverse=True)
    online = int(fleet_summary.get("online", 0) or 0)
    total = int(fleet_summary.get("total", 0) or 0)

    nodes = []
    for index, (key, data) in enumerate(ranked[: len(_FIELD_SLOTS)]):
        x, y, size = _FIELD_SLOTS[index]
        nodes.append({
            "id": key,
            "name": data["label"],
            "x": x, "y": y, "size": size,
            "state": "ready",
            "index": f"AGENT / {index + 1:02d}",
            "task": f"{data['count']} Brain submissions on record.",
            "progress": min(100, data["count"]),
            "model": f"last active {_summary(data['latest'][:10] or 'unknown', 20)}",
        })
    # One more slot for fleet, if room: represents real VPS online/total, not an agent.
    if total and len(nodes) < len(_FIELD_SLOTS):
        x, y, size = _FIELD_SLOTS[len(nodes)]
        nodes.append({
            "id": "fleet",
            "name": "Fleet",
            "x": x, "y": y, "size": size,
            "state": "ready" if online == total else "waiting",
            "index": f"OPS / {len(nodes) + 1:02d}",
            "task": f"{online}/{total} VPS nodes responding to live probe.",
            "progress": int(online / total * 100) if total else 0,
            "model": "live · ssh probe",
        })
    return nodes


def _trace_rows(thought_chains: list[dict]) -> str:
    rows = []
    for item in thought_chains[:6]:
        action = str(item.get("action") or "event")
        summary = _summary(item.get("summary") or item.get("decision") or "", 70)
        ts = str(item.get("created_at") or "")[11:19] or "--:--:--"
        rows.append(
            f"""<div><time>{_e(ts)}</time><span class="trace-agent">{_e(action.upper())}</span>"""
            f"""<p>{_e(summary)}</p><b>{_e(str(item.get('stage') or '').upper() or 'LOGGED')}</b></div>"""
        )
    if rows:
        return "".join(rows)
    return """<div class="trace-empty"><time>--:--:--</time><span class="trace-agent">—</span>
      <p>No thought-chain activity recorded yet</p><b>IDLE</b></div>"""


def _decision_rows(pending_proposals: list[dict], linuxdo_board: dict) -> tuple[str, int]:
    """Real attention queue: pending Brain proposals first, then top signal."""
    items = []
    for p in pending_proposals[:2]:
        pid = str(p.get("proposal_id") or "")
        title = _summary(p.get("summary") or p.get("observation") or "Untitled proposal", 90)
        risk = str(p.get("risk_level") or "unknown")
        created = str(p.get("created_at") or "")[:10]
        items.append(f"""<article class="decision{' active' if not items else ''}" tabindex="0" data-title="{_e(title, quote=True)}">
          <div class="decision-meta"><span><i></i>BRAIN PROPOSAL</span><time>{_e(created)}</time></div>
          <h2>{_e(title)}</h2>
          <p>{_e(risk)} risk · source {_e(p.get('source_agent') or 'unknown')}</p>
          <div class="decision-actions"><a class="approve" href="/review/{_e(pid, quote=True)}"><span>Review</span></a><a class="later" href="/proposals"><span>Queue</span></a></div>
        </article>""")
    if len(items) < 2:
        board_items = linuxdo_board.get("items") or []
        top = next((i for i in board_items if i.get("tier") == "must_read"), None)
        if top:
            title = _summary(top.get("title"), 90)
            items.append(f"""<article class="decision" tabindex="0" data-title="{_e(title, quote=True)}">
              <div class="decision-meta"><span><i></i>SIGNAL</span><time>today</time></div>
              <h2>{_e(title)}</h2>
              <p>{_e(top.get('category') or 'Linux.do')} · score {_e(top.get('score') or '—')}</p>
              <div class="decision-actions"><a class="approve" href="{_e(top.get('url') or '/linuxdo', quote=True)}" target="_blank" rel="noopener"><span>Open</span></a><a class="later" href="/linuxdo"><span>Board</span></a></div>
            </article>""")
    return "".join(items), len(items)


def _trend_bars(daily_counts: list[dict]) -> str:
    """Real last-8-days proposal volume as a bar spectrum (replaces fake wave svg)."""
    if not daily_counts:
        return '<span class="trend-empty">No proposal history yet</span>'
    ordered = list(reversed(daily_counts))  # oldest -> newest
    peak = max(int(d.get("c", 0) or 0) for d in ordered) or 1
    bars = []
    for d in ordered:
        pct = max(6, round(int(d.get("c", 0) or 0) / peak * 100))
        bars.append(f'<i style="--v:{pct}%" title="{_e(d.get("d"))}: {_e(d.get("c"))} proposals"></i>')
    return "".join(bars)


def orbit_page(
    *,
    theme: str,
    node_counts: dict[str, int],
    knowledge_health: dict,
    pending_proposals: list[dict],
    all_proposals: list[dict],
    thought_chains: list[dict],
    daily_proposal_counts: list[dict],
    fleet_summary: dict,
    linuxdo_board: dict,
) -> str:
    theme = theme if theme in {"void", "daybreak"} else "void"
    canonized = int(node_counts.get("canonized", 0) or 0)
    deprecated = int(node_counts.get("deprecated", 0) or 0)
    total_nodes = canonized + deprecated + int(node_counts.get("draft", 0) or 0) + int(node_counts.get("refined", 0) or 0) + int(node_counts.get("verified", 0) or 0)
    pending_count = len(pending_proposals)
    signal_items = linuxdo_board.get("items") or []
    must_read = sum(1 for i in signal_items if i.get("tier") == "must_read")
    total_seen = int(linuxdo_board.get("total_seen_today", 0) or 0)
    noise_removed = round((1 - len(signal_items) / total_seen) * 100, 1) if total_seen else 0.0

    agent_nodes = _build_agent_nodes(all_proposals, fleet_summary)
    working_count = sum(1 for n in agent_nodes if n["state"] == "working")
    avg_confidence = float(knowledge_health.get("avg_confidence", 0) or 0)
    stability_score = round(avg_confidence * 100) if avg_confidence else 0

    decision_html, decision_count = _decision_rows(pending_proposals, linuxdo_board)
    if not decision_html:
        decision_html = """<div class="decision-empty">
          <p>No pending proposals or must-read signals right now.</p>
        </div>"""

    palette_rows = []
    for p in pending_proposals[:5]:
        pid = str(p.get("proposal_id") or "")
        title = _summary(p.get("summary") or p.get("observation") or "Untitled proposal", 70)
        palette_rows.append(
            f'<a class="command-item" href="/review/{_e(pid, quote=True)}">'
            f'<span><b>{_e(title)}</b><small>pending proposal · {_e(str(p.get("risk_level") or "unknown"))} risk</small></span>'
            f'<kbd>&#8629;</kbd></a>'
        )
    palette_queue_html = ""
    if palette_rows:
        palette_queue_html = '      <p>PENDING PROPOSALS</p>\n      ' + "\n      ".join(palette_rows) + "\n"

    trace_html = _trace_rows(thought_chains)
    trend_html = _trend_bars(daily_proposal_counts)
    now_utc = datetime.now(timezone.utc).strftime("%a · %d %b · %H:%M UTC")

    nodes_json = json.dumps(agent_nodes, ensure_ascii=False)

    css = """
:root{
  color-scheme:dark;
  --void:oklch(11% .012 178);--void-deep:oklch(7.5% .01 190);--plate:oklch(14.5% .014 178);
  --plate-raised:oklch(17.5% .016 174);--plate-hover:oklch(20% .018 174);
  --edge:oklch(88% .025 158 / .105);--edge-strong:oklch(88% .035 158 / .19);
  --ink:oklch(95% .018 154);--ink-soft:oklch(74% .025 157);--ink-dim:oklch(58% .022 160);
  --phosphor:oklch(83% .175 152);--phosphor-hot:oklch(89% .205 151);--phosphor-wash:oklch(83% .175 152 / .09);
  --amber:oklch(78% .13 76);--danger:oklch(69% .16 28);
  --radius-sm:7px;--radius-md:11px;--radius-lg:16px;--rail:84px;--topbar:64px;
  --ease:cubic-bezier(.25,1,.5,1);--fast:150ms;--normal:240ms;
}
html[data-theme="daybreak"]{
  color-scheme:light;
  --void:oklch(96.5% .014 155);--void-deep:oklch(93.5% .018 157);--plate:oklch(99% .008 155);
  --plate-raised:oklch(100% 0 0);--plate-hover:oklch(94.5% .025 152);
  --edge:oklch(25% .025 165 / .12);--edge-strong:oklch(25% .03 165 / .22);
  --ink:oklch(19% .025 164);--ink-soft:oklch(40% .025 165);--ink-dim:oklch(53% .02 165);
  --phosphor:oklch(55% .16 151);--phosphor-hot:oklch(48% .17 151);--phosphor-wash:oklch(55% .16 151 / .09);
  --amber:oklch(52% .15 71);
}
*{box-sizing:border-box}
html{min-width:320px;background:var(--void);scroll-behavior:smooth}
body{min-height:100dvh;margin:0;overflow-x:hidden;background:var(--void);color:var(--ink);font:500 14px/1.5 Manrope,system-ui,-apple-system,sans-serif;letter-spacing:-.01em}
button,input{font:inherit}button{color:inherit}button,a{touch-action:manipulation}
button:focus-visible,a:focus-visible,input:focus-visible{outline:2px solid var(--phosphor);outline-offset:3px}
svg{display:block;width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
a{color:inherit;text-decoration:none}
.icon-sprite{position:absolute;width:0;height:0;overflow:hidden}
.sr-only{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.skip-link{position:fixed;left:100px;top:-60px;z-index:200;padding:10px 14px;border-radius:var(--radius-sm);background:var(--phosphor);color:var(--void-deep);text-decoration:none;transition:top var(--fast)}
.skip-link:focus{top:12px}
.ambient{position:fixed;inset:0;z-index:-1;overflow:hidden;pointer-events:none;background-image:linear-gradient(var(--edge) 1px,transparent 1px),linear-gradient(90deg,var(--edge) 1px,transparent 1px);background-size:80px 80px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.28),transparent 62%)}
.ambient i{position:absolute;width:46vw;aspect-ratio:1;border-radius:50%;filter:blur(120px);opacity:.055;background:var(--phosphor)}
.ambient i:first-child{left:10%;top:-28%}.ambient i:last-child{right:-20%;bottom:-35%}
.rail{position:fixed;inset:0 auto 0 0;z-index:50;width:var(--rail);display:flex;flex-direction:column;align-items:center;border-right:1px solid var(--edge);background:color-mix(in oklch,var(--void-deep),transparent 5%);backdrop-filter:blur(18px)}
.logo{display:grid;place-items:center;gap:3px;width:100%;height:var(--topbar);border-bottom:1px solid var(--edge);color:var(--ink);text-decoration:none}
.logo svg{width:25px;height:25px;color:var(--phosphor);stroke-width:1.35}.logo span{font:500 8px/1 IBM Plex Mono,monospace;letter-spacing:.18em}
.rail nav{display:grid;width:100%;padding:18px 10px;gap:8px}
.rail-link{position:relative;display:grid;place-items:center;gap:4px;min-height:54px;padding:5px;border:0;border-radius:var(--radius-sm);background:transparent;color:var(--ink-dim);cursor:pointer;transition:color var(--fast),background var(--fast)}
.rail-link svg{width:19px;height:19px}.rail-link span{font:500 9px/1 IBM Plex Mono,monospace;letter-spacing:.04em}.rail-link b{position:absolute;top:5px;right:9px;min-width:16px;height:16px;padding:0 4px;border-radius:8px;background:var(--phosphor);color:var(--void-deep);font:500 8px/16px IBM Plex Mono;text-align:center}
.rail-link:hover{color:var(--ink);background:var(--phosphor-wash)}
.rail-link.active{color:var(--phosphor);background:var(--phosphor-wash)}
.rail-link.active:before{content:"";position:absolute;left:-10px;width:2px;height:24px;background:var(--phosphor);box-shadow:0 0 12px var(--phosphor)}
.rail-foot{display:grid;width:100%;gap:5px;margin-top:auto;padding:12px 10px 16px;border-top:1px solid var(--edge)}
.identity{position:relative;display:grid;place-items:center;width:34px;height:34px;margin:10px auto 0;border:1px solid var(--edge-strong);border-radius:50%;background:var(--plate-raised);font:600 10px IBM Plex Mono,monospace}
.identity i{position:absolute;right:-1px;bottom:1px;width:7px;height:7px;border:2px solid var(--void-deep);border-radius:50%;background:var(--phosphor)}
.workspace{min-height:100vh;margin-left:var(--rail)}
.topbar{position:sticky;top:0;z-index:40;height:var(--topbar);display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:0 clamp(20px,2.6vw,44px);border-bottom:1px solid var(--edge);background:color-mix(in oklch,var(--void),transparent 11%);backdrop-filter:blur(20px) saturate(1.2)}
.location,.top-actions,.sync,.command-trigger{display:flex;align-items:center}
.location{gap:10px;color:var(--ink-dim);font:500 9px IBM Plex Mono,monospace;letter-spacing:.12em}.location i{width:20px;height:1px;background:var(--edge-strong)}.location b{color:var(--ink-soft);font-weight:500}
.top-actions{justify-content:flex-end;gap:18px}.sync{gap:7px;color:var(--ink-dim);font:500 9px IBM Plex Mono,monospace}.sync i,.live-dot{width:6px;height:6px;border-radius:50%;background:var(--phosphor);box-shadow:0 0 0 4px var(--phosphor-wash),0 0 12px color-mix(in oklch,var(--phosphor),transparent 30%)}.sync b{color:var(--ink-soft);font-weight:500}
.command-trigger{gap:8px;min-width:150px;height:36px;padding:0 9px;border:1px solid var(--edge);border-radius:var(--radius-sm);background:var(--plate);color:var(--ink-dim);cursor:pointer}
.theme-toggle{display:flex;align-items:center;gap:6px;height:32px;padding:0 10px;border:1px solid var(--edge);border-radius:var(--radius-sm);background:var(--plate);color:var(--ink-dim);font:500 9px IBM Plex Mono,monospace;letter-spacing:.06em;cursor:pointer}
.briefing{display:grid;grid-template-columns:minmax(330px,1.2fr) minmax(250px,.7fr) auto;gap:clamp(28px,5vw,86px);align-items:end;padding:clamp(36px,5vw,72px) clamp(20px,3.6vw,58px) clamp(30px,4vw,54px)}
.overline{margin:0 0 11px;color:var(--ink-dim);font:500 9px IBM Plex Mono,monospace;letter-spacing:.14em}
.briefing h1{margin:0;font-size:clamp(33px,4.2vw,58px);font-weight:500;line-height:1.04;letter-spacing:-.05em}.briefing h1 span{color:var(--ink-dim)}
.brief-copy{max-width:410px;margin:0;color:var(--ink-dim);font-size:13px;line-height:1.75}.brief-copy b{color:var(--ink-soft);font-weight:600}
.field-layout{display:grid;grid-template-columns:minmax(560px,1.62fr) minmax(340px,.88fr);min-height:520px;margin:0 clamp(20px,3.6vw,58px);border:1px solid var(--edge);border-radius:var(--radius-lg);overflow:hidden;background:var(--plate)}
.neural-panel,.attention-panel{min-width:0}.neural-panel{border-right:1px solid var(--edge)}
.panel-header{height:67px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;border-bottom:1px solid var(--edge);background:color-mix(in oklch,var(--plate),var(--void) 18%)}
.panel-header>div:first-child{display:flex;align-items:center;gap:11px}.panel-header p{margin:0}.panel-header p b,.panel-header p small{display:block}.panel-header p b{color:var(--ink-soft);font:500 9px IBM Plex Mono,monospace;letter-spacing:.13em}.panel-header p small{margin-top:4px;color:var(--ink-dim);font-size:11px}
.field-stats{display:flex;gap:24px}.field-stats span{color:var(--ink-dim);font:500 8px IBM Plex Mono,monospace;letter-spacing:.08em}.field-stats b{margin-left:5px;color:var(--ink-soft);font-weight:500}
.field-stage{position:relative;height:452px;overflow:hidden;background:radial-gradient(circle at 48% 49%,var(--phosphor-wash),transparent 24%),linear-gradient(var(--edge) 1px,transparent 1px),linear-gradient(90deg,var(--edge) 1px,transparent 1px);background-size:auto,40px 40px,40px 40px}
#fieldCanvas,.node-layer{position:absolute;inset:0;width:100%;height:100%}.node-layer{z-index:3;pointer-events:none}
.agent-node{--node-size:12px;position:absolute;left:var(--x);top:var(--y);display:grid;place-items:center;width:max(46px,var(--node-size));height:max(46px,var(--node-size));padding:0;border:0;border-radius:50%;background:transparent;transform:translate(-50%,-50%);pointer-events:auto;cursor:pointer;transition:filter var(--fast),transform var(--fast)}
.agent-node:before{content:"";position:absolute;width:var(--node-size);height:var(--node-size);border:1px solid var(--node-color,var(--ink-dim));border-radius:50%;background:color-mix(in oklch,var(--node-color,var(--ink-dim)),var(--plate) 74%);box-shadow:0 0 0 5px color-mix(in oklch,var(--node-color,var(--ink-dim)),transparent 90%),0 0 20px color-mix(in oklch,var(--node-color,var(--ink-dim)),transparent 62%);transition:transform var(--fast),background var(--fast)}
.agent-node:after{content:"";position:absolute;width:4px;height:4px;border-radius:50%;background:var(--node-color,var(--ink-dim))}
.agent-node span{position:absolute;top:calc(50% + var(--node-size)/2 + 7px);width:max-content;color:var(--ink-dim);font:500 8px IBM Plex Mono,monospace;letter-spacing:.09em;text-transform:uppercase;transition:color var(--fast)}
.agent-node:hover,.agent-node.active{filter:brightness(1.18);transform:translate(-50%,-50%) scale(1.07)}.agent-node:hover:before,.agent-node.active:before{background:var(--node-color);transform:scale(1.12)}.agent-node.active span,.agent-node:hover span{color:var(--ink)}
.agent-node.working{--node-color:var(--phosphor)}.agent-node.ready{--node-color:var(--ink-soft)}.agent-node.waiting{--node-color:var(--amber)}
.field-axis{position:absolute;z-index:4;color:var(--ink-dim);font:500 7px IBM Plex Mono,monospace;letter-spacing:.13em;pointer-events:none}.axis-x{right:17px;bottom:14px}.axis-y{left:12px;top:18px;writing-mode:vertical-rl;transform:rotate(180deg)}
.field-legend{position:absolute;left:20px;bottom:15px;z-index:4;display:flex;gap:14px;color:var(--ink-dim);font:500 7px IBM Plex Mono,monospace;text-transform:uppercase}.field-legend span{display:flex;align-items:center;gap:5px}.field-legend i,.detail-top i{width:6px;height:6px;border-radius:50%}.field-legend .ready,.detail-top .ready{background:var(--ink-soft)}.field-legend .working,.detail-top .working{background:var(--phosphor)}.field-legend .waiting,.detail-top .waiting{background:var(--amber)}
.node-detail{position:absolute;right:22px;bottom:42px;z-index:5;width:220px;padding:15px;border:1px solid var(--edge-strong);border-radius:var(--radius-md);background:color-mix(in oklch,var(--plate-raised),transparent 5%);backdrop-filter:blur(16px);box-shadow:0 18px 44px oklch(0% 0 0 / .22),0 2px 10px oklch(0% 0 0 / .12)}.detail-top{display:flex;align-items:center;justify-content:space-between;color:var(--ink-dim);font:500 8px IBM Plex Mono,monospace;letter-spacing:.08em}.node-detail h2{margin:10px 0 3px;font-size:17px;font-weight:600;letter-spacing:-.025em}.node-detail>p{min-height:34px;margin:0;color:var(--ink-dim);font-size:10px;line-height:1.55}.detail-meter{display:flex;align-items:center;gap:9px;margin:14px 0}.detail-meter>span{height:3px;flex:1;overflow:hidden;border-radius:2px;background:var(--edge)}.detail-meter i{display:block;height:100%;background:var(--phosphor);transition:width var(--normal)}.detail-meter b{color:var(--ink-soft);font:500 8px IBM Plex Mono,monospace}.node-detail footer{display:flex;align-items:center;justify-content:space-between;padding-top:10px;border-top:1px solid var(--edge)}.node-detail footer>span{color:var(--ink-dim);font:500 7px IBM Plex Mono,monospace}
.field-empty{position:absolute;inset:0;display:grid;place-items:center;color:var(--ink-dim);font:500 11px IBM Plex Mono,monospace;text-align:center;padding:20px}
.attention-panel{display:flex;flex-direction:column;background:var(--plate-raised)}.attention-head{flex:0 0 67px}.queue-count{display:grid;place-items:center;width:28px;height:28px;border:1px solid var(--edge-strong);border-radius:50%;color:var(--phosphor);font:500 9px IBM Plex Mono,monospace}.decision-list{display:grid;flex:1}.decision{display:flex;flex-direction:column;padding:22px;border-bottom:1px solid var(--edge);background:transparent;transition:background var(--fast)}.decision:hover,.decision.active{background:var(--phosphor-wash)}.decision-meta{display:flex;align-items:center;justify-content:space-between;color:var(--ink-dim);font:500 8px IBM Plex Mono,monospace;letter-spacing:.09em}.decision-meta span{display:flex;align-items:center;gap:6px}.decision-meta i{width:5px;height:5px;border-radius:50%;background:var(--amber)}.decision h2{margin:16px 0 7px;font-size:16px;font-weight:550;line-height:1.35;letter-spacing:-.025em}.decision p{margin:0 0 18px;color:var(--ink-dim);font-size:11px;line-height:1.6}.decision-actions{display:flex;gap:8px;margin-top:auto}.decision-actions a{display:flex;align-items:center;justify-content:center;height:32px;border-radius:6px;font:500 8px IBM Plex Mono,monospace;cursor:pointer}.approve{flex:1;border:0;background:var(--phosphor);color:var(--void-deep)}.later{padding:0 12px;border:1px solid var(--edge);background:transparent;color:var(--ink-dim)}.approve:hover{background:var(--phosphor-hot)}.later:hover{background:var(--plate-hover);color:var(--ink)}
.decision-empty{padding:22px;color:var(--ink-dim);font-size:12px;line-height:1.6}
.lower-deck{display:grid;grid-template-columns:1.35fr 1fr .62fr;gap:0;margin:18px clamp(20px,3.6vw,58px) 54px;border:1px solid var(--edge);border-radius:var(--radius-lg);overflow:hidden;background:var(--plate)}
.lower-deck>article{min-width:0;min-height:235px;padding:20px;border-right:1px solid var(--edge)}.lower-deck>article:last-child{border-right:0}
.trajectory header,.live-trace header,.signal-lens header{display:flex;align-items:flex-start;justify-content:space-between}.trajectory h2{margin:0;font-size:18px;font-weight:500;letter-spacing:-.025em}.trajectory-score{display:flex;align-items:center;gap:6px}.trajectory-score>b{font:500 30px/1 IBM Plex Mono,monospace}.trajectory-score>span{color:var(--ink-dim);font:500 7px/1.4 IBM Plex Mono,monospace}
.trend-wrap{height:70px;display:flex;align-items:flex-end;gap:5px;margin-top:26px;padding-bottom:6px;border-bottom:1px solid var(--edge)}.trend-wrap i{flex:1;height:var(--v);min-height:4px;background:color-mix(in oklch,var(--phosphor),transparent 30%);border-radius:2px 2px 0 0}.trend-empty{color:var(--ink-dim);font-size:11px}
.live-trace{background:var(--plate-raised)}.live-trace header>div{display:flex;align-items:center;gap:10px}.live-trace header p{margin:0}.live-trace header b,.live-trace header small{display:block}.live-trace header b{color:var(--ink-soft);font:500 9px IBM Plex Mono,monospace;letter-spacing:.1em}.live-trace header small{margin-top:3px;color:var(--ink-dim);font-size:10px}
.trace-list{margin-top:17px}.trace-list>div{display:grid;grid-template-columns:55px 80px minmax(0,1fr) auto;gap:8px;align-items:center;min-height:31px;border-top:1px solid var(--edge);font:500 8px IBM Plex Mono,monospace}.trace-list time{color:var(--ink-dim)}.trace-agent{color:var(--ink-soft)}.trace-list p{margin:0;overflow:hidden;color:var(--ink-dim);text-overflow:ellipsis;white-space:nowrap}.trace-list b{color:var(--ink-soft);font-weight:500}
.signal-lens p{display:flex;align-items:flex-end;gap:11px;margin:23px 0 18px}.signal-lens p strong{font:500 44px/1 IBM Plex Mono,monospace;letter-spacing:-.07em}.signal-lens p span{color:var(--ink-dim);font-size:9px;line-height:1.5}.lens-spectrum{height:47px;display:flex;align-items:flex-end;gap:3px;padding:6px 0;border-bottom:1px solid var(--edge)}.lens-spectrum i{flex:1;height:var(--v);min-height:3px;background:color-mix(in oklch,var(--phosphor),transparent 35%)}.signal-lens footer{display:flex;justify-content:space-between;margin-top:14px;color:var(--ink-dim);font:500 7px IBM Plex Mono,monospace;letter-spacing:.08em}.signal-lens footer b{color:var(--ink-soft);font-weight:500}
.toast{position:fixed;left:50%;bottom:28px;z-index:100;display:flex;align-items:center;gap:9px;max-width:calc(100vw - 30px);padding:10px 14px;border:1px solid var(--edge-strong);border-radius:8px;background:var(--plate-raised);color:var(--ink-soft);font-size:11px;opacity:0;pointer-events:none;transform:translate(-50%,16px);transition:opacity var(--fast),transform var(--normal) var(--ease);box-shadow:0 14px 40px oklch(0% 0 0 / .25)}.toast.show{opacity:1;transform:translate(-50%,0)}
.palette-backdrop{position:fixed;inset:0;z-index:80;background:oklch(3% .01 180 / .68);opacity:0;pointer-events:none;transition:opacity var(--fast);backdrop-filter:blur(4px)}.palette-backdrop.open{opacity:1;pointer-events:auto}
.command-palette{position:fixed;left:50%;top:16vh;z-index:81;width:min(640px,calc(100vw - 30px));max-height:70vh;display:flex;flex-direction:column;overflow:hidden;border:1px solid var(--edge-strong);border-radius:var(--radius-lg);background:color-mix(in oklch,var(--plate-raised),transparent 2%);box-shadow:0 28px 90px oklch(0% 0 0 / .48);opacity:0;pointer-events:none;transform:translate(-50%,-12px) scale(.985);transition:opacity var(--fast),transform var(--normal) var(--ease)}.command-palette.open{opacity:1;pointer-events:auto;transform:translate(-50%,0) scale(1)}
.command-input{display:flex;align-items:center;gap:12px;height:56px;flex:0 0 auto;padding:0 18px;border-bottom:1px solid var(--edge)}.command-input input{flex:1;border:0;outline:0;background:transparent;color:var(--ink);font-size:15px}.command-input input::placeholder{color:var(--ink-dim)}
.command-results{padding:10px;overflow-y:auto}.command-results>p{margin:5px 9px 8px;color:var(--ink-dim);font:500 7px IBM Plex Mono,monospace;letter-spacing:.12em}.command-item{display:grid;grid-template-columns:1fr auto;gap:11px;align-items:center;width:100%;padding:10px;border:0;border-radius:8px;background:transparent;text-align:left;cursor:pointer;text-decoration:none;color:inherit}.command-item:hover,.command-item.selected{background:var(--phosphor-wash)}.command-item.hidden{display:none}.command-item b,.command-item small{display:block}.command-item b{font-size:12px;font-weight:600;color:var(--ink)}.command-item small{margin-top:2px;color:var(--ink-dim);font-size:10px}.command-palette>footer{display:flex;gap:15px;align-items:center;height:43px;flex:0 0 auto;padding:0 16px;border-top:1px solid var(--edge);background:var(--void-deep);color:var(--ink-dim);font:500 7px IBM Plex Mono,monospace}.command-palette>footer span{display:flex;align-items:center;gap:5px}.command-palette>footer b{margin-left:auto;color:var(--phosphor);font-weight:500;letter-spacing:.08em}
.no-results{padding:22px 10px;color:var(--ink-dim);font-size:12px;text-align:center}
html[data-theme="daybreak"] .node-detail{background:var(--plate-raised);box-shadow:0 20px 48px oklch(35% .03 165 / .18),0 3px 14px oklch(35% .03 165 / .12)}
html[data-theme="daybreak"] .lens-spectrum i{background:color-mix(in oklch,var(--phosphor),transparent 8%)}
html[data-theme="daybreak"] .trend-wrap i{background:color-mix(in oklch,var(--phosphor),transparent 8%)}
html[data-theme="daybreak"] .agent-node:before{box-shadow:0 0 0 5px color-mix(in oklch,var(--node-color,var(--ink-dim)),transparent 78%),0 0 14px color-mix(in oklch,var(--node-color,var(--ink-dim)),transparent 50%)}
@keyframes breathe{50%{opacity:.52;transform:scale(.92)}}.live-dot{animation:breathe 2.4s ease-in-out infinite}
@media(max-width:1180px){.briefing{grid-template-columns:1fr .78fr auto;gap:28px}.briefing h1{font-size:40px}.field-layout{grid-template-columns:minmax(490px,1.4fr) minmax(320px,.9fr)}.lower-deck{grid-template-columns:1.25fr 1fr}.signal-lens{display:none}.lower-deck>article:nth-child(2){border-right:0}}
@media(max-width:900px){:root{--rail:68px}.topbar{grid-template-columns:1fr auto}.command-trigger{display:none}.briefing{grid-template-columns:1fr auto}.brief-copy{display:none}.field-layout{grid-template-columns:1fr}.neural-panel{border-right:0;border-bottom:1px solid var(--edge)}.lower-deck{grid-template-columns:1fr}.lower-deck>article{border-right:0;border-bottom:1px solid var(--edge)}.lower-deck>article:last-child{border-bottom:0}.signal-lens{display:block}.field-stage{height:420px}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation-duration:.01ms!important;transition-duration:.01ms!important}}
"""

    script = """
(() => {
  const $ = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => [...r.querySelectorAll(s)];
  const NODES = window.__ORBIT_NODES__ || [];
  const nodeLayer = $('#nodeLayer');
  NODES.forEach((node, index) => {
    const button = document.createElement('button');
    button.className = `agent-node ${node.state}${index === 0 ? ' active' : ''}`;
    button.style.setProperty('--x', `${node.x}%`);
    button.style.setProperty('--y', `${node.y}%`);
    button.style.setProperty('--node-size', `${node.size}px`);
    button.dataset.node = node.id;
    button.setAttribute('aria-label', `${node.name}: ${node.task}`);
    button.innerHTML = `<span>${node.name}</span>`;
    nodeLayer.append(button);
  });
  function selectNode(id) {
    const node = NODES.find(n => n.id === id);
    if (!node) return;
    $$('.agent-node').forEach(b => b.classList.toggle('active', b.dataset.node === id));
    $('#detailIndex').textContent = node.index;
    $('#detailName').textContent = node.name;
    $('#detailTask').textContent = node.task;
    $('#detailProgress').textContent = `${node.progress}%`;
    $('#detailMeter').style.width = `${node.progress}%`;
    $('#detailModel').textContent = node.model;
    const dot = $('.detail-top i');
    if (dot) dot.className = node.state;
  }
  nodeLayer.addEventListener('click', e => {
    const b = e.target.closest('.agent-node');
    if (b) selectNode(b.dataset.node);
  });
  if (NODES.length) selectNode(NODES[0].id);

  const themeToggle = $('#themeToggle');
  themeToggle?.addEventListener('click', () => {
    const current = document.documentElement.dataset.theme === 'daybreak' ? 'void' : 'daybreak';
    window.location.href = current === 'daybreak' ? '/design/orbit?theme=daybreak' : '/design/orbit';
  });

  const toast = $('#toast');
  let toastTimer;
  function notify(message) {
    $('span', toast).textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
  }
  $$('.later').forEach(b => b.addEventListener('click', () => notify('Not wired to a write action in this candidate — real endpoints only.')));

  const palette = $('#commandPalette');
  const paletteBackdrop = $('#paletteBackdrop');
  const commandInput = $('#commandInput');
  const commandResults = $('#commandResults');
  let previousFocus;
  function visibleItems() { return $$('.command-item', commandResults).filter(el => !el.classList.contains('hidden')); }
  function markSelected(index) {
    const items = visibleItems();
    items.forEach(el => el.classList.remove('selected'));
    if (!items.length) return;
    const clamped = Math.max(0, Math.min(index, items.length - 1));
    items[clamped].classList.add('selected');
    items[clamped].scrollIntoView({ block: 'nearest' });
  }
  function openPalette() {
    previousFocus = document.activeElement;
    palette.classList.add('open');
    paletteBackdrop.classList.add('open');
    palette.setAttribute('aria-hidden', 'false');
    commandInput.value = '';
    $$('.command-item', commandResults).forEach(el => el.classList.remove('hidden'));
    $$('.command-results>p', commandResults).forEach(el => el.classList.remove('hidden'));
    markSelected(0);
    setTimeout(() => commandInput.focus(), 60);
  }
  function closePalette() {
    palette.classList.remove('open');
    paletteBackdrop.classList.remove('open');
    palette.setAttribute('aria-hidden', 'true');
    previousFocus?.focus();
  }
  $('#commandTrigger')?.addEventListener('click', openPalette);
  paletteBackdrop.addEventListener('click', closePalette);
  commandInput.addEventListener('input', () => {
    const query = commandInput.value.toLowerCase().trim();
    let anyVisible = false;
    $$('.command-item', commandResults).forEach(el => {
      const match = el.textContent.toLowerCase().includes(query);
      el.classList.toggle('hidden', !match);
      if (match) anyVisible = true;
    });
    $$('.command-results>p', commandResults).forEach(heading => {
      let sib = heading.nextElementSibling;
      let groupHasVisible = false;
      while (sib && sib.tagName !== 'P') {
        if (sib.classList.contains('command-item') && !sib.classList.contains('hidden')) groupHasVisible = true;
        sib = sib.nextElementSibling;
      }
      heading.classList.toggle('hidden', !groupHasVisible);
    });
    let noResults = $('.no-results', commandResults);
    if (!anyVisible) {
      if (!noResults) {
        noResults = document.createElement('div');
        noResults.className = 'no-results';
        noResults.textContent = 'No matching page or proposal.';
        commandResults.append(noResults);
      }
    } else {
      noResults?.remove();
    }
    markSelected(0);
  });
  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      palette.classList.contains('open') ? closePalette() : openPalette();
      return;
    }
    if (!palette.classList.contains('open')) return;
    if (event.key === 'Escape') { event.preventDefault(); closePalette(); return; }
    const items = visibleItems();
    const current = items.findIndex(el => el.classList.contains('selected'));
    if (event.key === 'ArrowDown') { event.preventDefault(); markSelected(current + 1); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); markSelected(Math.max(0, current - 1)); }
    else if (event.key === 'Enter') { event.preventDefault(); items[Math.max(0, current)]?.click(); }
  });
})();
"""

    theme_label = "Light" if theme == "void" else "Void"
    now_label_class = "" if theme == "void" else ""

    return f"""<!doctype html>
<html lang="en" data-theme="{_e(theme)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#080b0c">
  <title>Orbit · Brain — real data candidate</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>{css}</style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to workspace</a>
  <div class="ambient" aria-hidden="true"><i></i><i></i></div>

  <aside class="rail" aria-label="Primary navigation">
    <a class="logo" href="/design/orbit" aria-label="Orbit home"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><ellipse cx="12" cy="12" rx="10" ry="4.5"/><ellipse cx="12" cy="12" rx="4.5" ry="10" transform="rotate(42 12 12)"/></svg><span>ORBIT</span></a>
    <nav>
      <button class="rail-link active" aria-current="page"><svg viewBox="0 0 24 24"><path d="M4 10.5 12 4l8 6.5v8a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5z"/></svg><span>Now</span></button>
      <a class="rail-link" href="/proposals"><svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="2.5"/><circle cx="18.5" cy="6" r="2.5"/><circle cx="18.5" cy="18" r="2.5"/></svg><span>Proposals</span>{f'<b>{pending_count}</b>' if pending_count else ''}</a>
      <a class="rail-link" href="/linuxdo"><svg viewBox="0 0 24 24"><path d="M3 12h4l2.2-6 4.2 12L16 10l1.5 2H21"/></svg><span>Signals</span>{f'<b>{must_read}</b>' if must_read else ''}</a>
      <a class="rail-link" href="/knowledge"><svg viewBox="0 0 24 24"><path d="M4 8h16v12H4zM3 4h18v4H3z"/></svg><span>Memory</span></a>
    </nav>
    <div class="rail-foot">
      <button class="rail-link" id="themeToggle"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/></svg><span>{_e(theme_label)}</span></button>
      <div class="identity" title="Local operator"><span>CK</span><i></i></div>
    </div>
  </aside>

  <main id="main" class="workspace">
    <header class="topbar">
      <div class="location"><span>BRAIN WORKBENCH</span><i></i><b>NOW</b></div>
      <div></div>
      <div class="top-actions">
        <span class="sync"><i></i>Real data · {_e(now_utc)}</span>
        <button class="command-trigger" id="commandTrigger" aria-label="Open command palette"><span>Jump to&#8230;</span><kbd>&#8984; K</kbd></button>
      </div>
    </header>

    <section class="briefing" aria-labelledby="briefing-title">
      <div>
        <p class="overline">{_e(now_utc)}</p>
        <h1>{pending_count} proposal{'s' if pending_count != 1 else ''} pending.<br><span>{total_nodes} nodes in the knowledge graph.</span></h1>
      </div>
      <p class="brief-copy"><b>{must_read} must-read signal{'s' if must_read != 1 else ''}</b> today from {_e(total_seen)} scanned on Linux.do. Noise removed <b>{_e(noise_removed)}%</b>.</p>
    </section>

    <section class="field-layout" aria-label="Live intelligence workspace">
      <article class="neural-panel">
        <header class="panel-header">
          <div><span class="live-dot"></span><p><b>COGNITIVE FIELD</b><small>{len(agent_nodes)} real agent{'s' if len(agent_nodes) != 1 else ''} · ranked by Brain submission volume</small></p></div>
          <div class="field-stats"><span>NODES <b>{total_nodes}</b></span><span>CANONIZED <b>{canonized}</b></span></div>
        </header>
        <div class="field-stage" id="fieldStage">
          <div class="node-layer" id="nodeLayer"></div>
          {'<div class="field-empty">No agent activity recorded in Brain proposals yet.</div>' if not agent_nodes else ''}
          <div class="field-axis axis-x"><span>PROPOSAL VOLUME</span></div>
          <div class="field-axis axis-y"><span>RECENCY</span></div>
          <div class="field-legend"><span><i class="ready"></i>Ready</span><span><i class="working"></i>Working</span><span><i class="waiting"></i>Waiting</span></div>
          <div class="node-detail" id="nodeDetail" aria-live="polite">
            <div class="detail-top"><span id="detailIndex">—</span><i class="ready"></i></div>
            <h2 id="detailName">—</h2>
            <p id="detailTask">Select a node.</p>
            <div class="detail-meter"><span><i id="detailMeter" style="width:0%"></i></span><b id="detailProgress">0%</b></div>
            <footer><span id="detailModel">—</span></footer>
          </div>
        </div>
      </article>

      <aside class="attention-panel" aria-labelledby="attention-title">
        <header class="panel-header attention-head"><div><p><b id="attention-title">ATTENTION QUEUE</b><small>Real pending proposals + top signal</small></p></div><span class="queue-count">{decision_count:02d}</span></header>
        <div class="decision-list">{decision_html}</div>
      </aside>
    </section>

    <section class="lower-deck">
      <article class="trajectory" aria-labelledby="trajectory-title">
        <header><div><span class="overline">KNOWLEDGE CONFIDENCE</span><h2 id="trajectory-title">Avg. confidence across canonized nodes</h2></div><div class="trajectory-score"><b>{stability_score}</b><span>/100<br>{_e(knowledge_health.get('status', 'unknown').upper())}</span></div></header>
        <div class="trend-wrap" aria-label="Proposal volume, last 8 days">{trend_html}</div>
      </article>

      <article class="live-trace" aria-labelledby="trace-title">
        <header><div><span class="live-dot"></span><p><b id="trace-title">THOUGHT CHAIN</b><small>Most recent Brain curator decisions</small></p></div></header>
        <div class="trace-list" id="traceList">{trace_html}</div>
      </article>

      <article class="signal-lens" aria-labelledby="lens-title">
        <header><span class="overline">SIGNAL LENS</span><a href="/linuxdo" aria-label="Open signals"><svg viewBox="0 0 24 24"><path d="M5 12h14M14 7l5 5-5 5"/></svg></a></header>
        <p><strong>{must_read}</strong><span>must-read signals<br>from {_e(total_seen)} scanned</span></p>
        <div class="lens-spectrum" aria-hidden="true">{''.join(f'<i style="--v:{min(100, int(i.get("score",0) or 0)*10)}%"></i>' for i in signal_items[:12])}</div>
        <footer><span>NOISE REMOVED</span><b>{_e(noise_removed)}%</b></footer>
      </article>
    </section>
  </main>

  <div class="palette-backdrop" id="paletteBackdrop"></div>
  <section class="command-palette" id="commandPalette" role="dialog" aria-modal="true" aria-labelledby="command-title" aria-hidden="true">
    <h2 class="sr-only" id="command-title">Jump to</h2>
    <div class="command-input"><input id="commandInput" type="search" autocomplete="off" placeholder="Jump to a real page or item&#8230;" aria-label="Command search"><kbd>ESC</kbd></div>
    <div class="command-results" id="commandResults">
      <p>PAGES</p>
      <a class="command-item" href="/proposals"><span><b>Proposals</b><small>{pending_count} pending in the review queue</small></span><kbd>&#8629;</kbd></a>
      <a class="command-item" href="/linuxdo"><span><b>Signals</b><small>{must_read} must-read from Linux.do today</small></span><kbd>&#8629;</kbd></a>
      <a class="command-item" href="/knowledge"><span><b>Knowledge</b><small>{total_nodes} nodes in the graph</small></span><kbd>&#8629;</kbd></a>
{palette_queue_html}    </div>
    <footer><span><kbd>&#8593;&#8595;</kbd> Navigate</span><span><kbd>&#8629;</kbd> Open</span><span><kbd>ESC</kbd> Close</span><b>REAL LINKS ONLY</b></footer>
  </section>

  <div class="toast" id="toast" role="status" aria-live="polite"><span></span></div>
  <script>window.__ORBIT_NODES__ = {nodes_json};</script>
  <script>{script}</script>
</body>
</html>"""
