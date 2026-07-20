from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse


def _e(value: object, *, quote: bool = False) -> str:
    return html.escape(str(value), quote=quote)


def _safe_href(value: object, fallback: str = "/linuxdo") -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return raw
    if not parsed.scheme and raw.startswith("/") and not raw.startswith("//"):
        return raw
    return fallback


def _safe_review_href(value: object) -> str:
    proposal_id = str(value or "").strip()
    if not proposal_id:
        return "/proposals"
    return f"/review/{quote(proposal_id, safe='')}"


def _summary(value: object, limit: int = 164) -> str:
    text = " ".join(str(value or "Untitled record").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _short_date(value: object) -> str:
    raw = str(value or "")
    return raw[:10] if raw else "not recorded"


def _project_rows(proposals: list[dict]) -> str:
    projects: dict[str, dict[str, Any]] = {}
    for proposal in proposals:
        key = str(proposal.get("project_key") or "global").strip()
        if not key or key == "global":
            continue
        row = projects.setdefault(
            key,
            {"count": 0, "pending": 0, "latest": proposal.get("created_at") or ""},
        )
        row["count"] = int(row["count"]) + 1
        created_at = str(proposal.get("created_at") or "")
        if created_at > str(row["latest"]):
            row["latest"] = created_at
        if str(proposal.get("state") or "") == "pending":
            row["pending"] = int(row["pending"]) + 1

    if not projects:
        return """<div class="empty-channel">
          <span class="empty-mark" aria-hidden="true">—</span>
          <span><b>Project channel not connected</b><small>No project activity is recorded in Brain, so no project state is inferred.</small></span>
        </div>"""

    rows = []
    for index, (key, data) in enumerate(list(projects.items())[:5], start=1):
        name = key.replace("_", " ").replace("-", " ").title()
        pending = int(data["pending"])
        state = f"{pending} to review" if pending else "clear"
        rows.append(
            f"""<a class="project-row" href="/proposals">
              <code>P{index:02d}</code>
              <span class="row-copy"><b>{_e(name)}</b><small>{int(data['count'])} Brain records · latest {_e(_short_date(data['latest']))}</small></span>
              <span class="row-state {'attention' if pending else ''}">{_e(state)}</span>
            </a>"""
        )
    return "".join(rows)


def _agent_rows(proposals: list[dict]) -> str:
    labels = {
        "hermes": "Hermes",
        "codex": "Codex",
        "claude": "Claude Code",
        "gemini": "Gemini",
        "grok": "Grok",
    }
    latest_by_agent: dict[str, str] = {}
    for proposal in proposals:
        key = str(proposal.get("source_agent") or "").strip().lower()
        if key not in labels:
            continue
        created_at = str(proposal.get("created_at") or "")
        if created_at > latest_by_agent.get(key, ""):
            latest_by_agent[key] = created_at

    rows = []
    for key, created_at in sorted(latest_by_agent.items(), key=lambda item: item[1], reverse=True)[:4]:
        rows.append(
            f"""<div class="trace-row">
              <span class="trace-mark" aria-hidden="true"></span>
              <span class="row-copy"><b>{_e(labels[key])}</b><small>Last Brain submission {_e(_short_date(created_at))}</small></span>
              <span class="trace-kind">activity</span>
            </div>"""
        )
    if rows:
        return "".join(rows)
    return """<div class="empty-channel compact">
      <span class="empty-mark" aria-hidden="true">—</span>
      <span><b>Agent trace channel not connected</b><small>Submission history is not runtime health. Live services are reported separately.</small></span>
    </div>"""


def _signal_rows(board: dict) -> str:
    items = board.get("items") or []
    rows = []
    for index, item in enumerate(items[:5], start=1):
        title = _summary(item.get("title") or item.get("summary"), 150)
        source = str(item.get("source") or "Linux.do")
        href = _safe_href(item.get("url") or item.get("link"))
        rows.append(
            f"""<a class="signal-row" href="{_e(href, quote=True)}" target="_blank" rel="noopener">
              <code>S{index:02d}</code><b>{_e(title)}</b><span>{_e(source)}</span>
            </a>"""
        )
    if rows:
        return "".join(rows)
    detail = "Signal fetch failed" if board.get("fetch_errors") else "No curated signals waiting"
    return f"""<a class="signal-row empty" href="/linuxdo">
      <code>S00</code><b>{_e(detail)}</b><span>Open board</span>
    </a>"""


def cassette_page(
    *,
    node_counts: dict[str, int],
    proposal_counts: dict[str, int],
    knowledge_health: dict,
    lifecycle_overview: dict,
    pending_proposals: list[dict],
    all_proposals: list[dict],
    linuxdo_board: dict,
) -> str:
    """Render the isolated used-future operations workbench candidate."""
    pending_count = int(proposal_counts.get("pending", 0) or 0)
    conflicts = int(knowledge_health.get("conflict_count", 0) or 0)
    dirty = int(knowledge_health.get("dirty_nodes", 0) or 0)
    quarantined = int(knowledge_health.get("quarantined", 0) or 0)
    sync = lifecycle_overview.get("proposal_sync") or {}
    sync_missing = int(sync.get("missing", 0) or 0) if isinstance(sync, dict) else 0
    pending_attention = max(pending_count, len(pending_proposals))
    brain_issues = pending_attention + conflicts + dirty + quarantined + sync_missing
    signal_count = len(linuxdo_board.get("items") or [])
    board_updated = str(linuxdo_board.get("updated_at") or "not checked")[:16].replace("T", " ")

    if pending_proposals:
        proposal = pending_proposals[0]
        proposal_id = str(proposal.get("proposal_id") or "")
        next_title = _summary(
            proposal.get("summary") or proposal.get("observation") or proposal.get("suggested_memory")
        )
        next_meta = f"Brain proposal · {proposal.get('risk_level') or 'review'} risk"
        next_href = _safe_review_href(proposal_id)
        next_action = "Review decision"
    elif pending_count:
        next_title = f"{pending_count} pending Brain proposal{'s' if pending_count != 1 else ''} need review."
        next_meta = "Queue count is available; open the queue to select a decision."
        next_href = "/proposals"
        next_action = "Open proposals"
        proposal_id = "QUEUE"
    elif conflicts or dirty or quarantined or sync_missing:
        next_title = "Inspect Brain records that need maintenance."
        next_meta = (
            f"{conflicts} conflicts · {dirty} dirty · {quarantined} quarantined · "
            f"{sync_missing} unlinked"
        )
        next_href = "/knowledge"
        next_action = "Open knowledge"
        proposal_id = "BRAIN-MAINT"
    elif signal_count:
        next_title = _summary((linuxdo_board.get("items") or [{}])[0].get("title"), 164)
        next_meta = "Top item from the current signal board"
        next_href = "/linuxdo"
        next_action = "Read signal"
        proposal_id = "SIGNAL-01"
    else:
        next_title = "No manual decision is queued."
        next_meta = "The workbench is quiet; live telemetry remains available below."
        next_href = "/fleet"
        next_action = "Open fleet"
        proposal_id = "STANDBY"

    if brain_issues:
        brief_title = f"{brain_issues} item{'s' if brain_issues != 1 else ''} need a look."
        brief_copy = "Start with the next decision; background systems remain unchanged."
        initial_state = f"{brain_issues} queued"
        rail_state = "attention"
    else:
        brief_title = "Nothing asks for you right now."
        brief_copy = "Live fleet and service channels will surface exceptions without taking action."
        initial_state = "Standby"
        rail_state = "nominal"

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    projects_html = _project_rows(all_proposals)
    agents_html = _agent_rows(all_proposals)
    signals_html = _signal_rows(linuxdo_board)

    css = """
:root{
  --desktop:#657d80;--desktop-deep:#425d60;--bezel:#a99a7c;--shell:#d7cbb2;
  --surface:#f3ecd9;--surface-raised:#fff9e9;--screen:#243b32;--ink:#292c27;
  --ink-soft:#50554d;--muted:#676b61;--line:#918a73;--line-soft:#c7bea5;
  --signal:#c85f34;--signal-soft:#f1d1b9;--blue:#4f7889;--blue-soft:#d7e6e7;
  --green:#587451;--green-soft:#dce6d4;--ochre:#9b712f;--ochre-soft:#eee0ba;
  --phosphor:#d7e8a3;--nominal:#45694a;--danger:#a64036;
  --font-ui:Inter,"IBM Plex Sans",system-ui,-apple-system,sans-serif;
  --font-data:"IBM Plex Mono","SFMono-Regular",Consolas,"Liberation Mono",monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;background:var(--desktop-deep)}
body{margin:0;min-width:320px;background:
  radial-gradient(circle at 1px 1px,rgba(255,255,255,.14) 1px,transparent 1.15px) 0 0/7px 7px,
  linear-gradient(135deg,var(--desktop),var(--desktop-deep));color:var(--ink);font:16px/1.5 var(--font-ui)}
a{color:inherit;text-decoration:none}button{font:inherit}code{font-family:var(--font-data)}
:focus-visible{outline:3px solid var(--signal);outline-offset:2px}
.skip-link{position:fixed;left:16px;top:-70px;z-index:100;padding:11px 16px;background:var(--surface-raised);color:var(--ink);border:2px solid var(--ink)}
.skip-link:focus{top:16px}
.cassette-workbench{min-height:100vh;padding:22px}
.ops-desktop{display:grid;grid-template-columns:98px minmax(0,1fr);max-width:1320px;min-height:calc(100vh - 44px);margin:0 auto;border:2px solid #665e4c;border-radius:6px;background:var(--bezel);box-shadow:8px 9px 0 rgba(31,40,39,.62),inset 1px 1px 0 #eee1c6,inset -1px -1px 0 #746a56;overflow:hidden}
.tool-rail{position:relative;display:flex;flex-direction:column;border-right:2px solid #827862;background:linear-gradient(90deg,#d5c9b0,#c8b99d)}
.tool-rail:before{content:"";position:absolute;inset:0 0 auto;height:5px;background:repeating-linear-gradient(90deg,#70664f 0 3px,transparent 3px 6px);opacity:.55}
.rail-brand{display:grid;place-items:center;height:70px;border-bottom:1px solid #9c927b}
.pixel-mark{display:grid;place-items:center;width:38px;height:38px;border:2px solid #5e594b;border-radius:3px;background:#efe4cc;box-shadow:2px 2px 0 #756b55;color:var(--signal);font:700 14px/1 var(--font-data);letter-spacing:-.04em}
.tool-rail nav{display:flex;flex-direction:column;padding:10px 7px;gap:5px}
.tool-link{display:grid;place-items:center;gap:5px;min-height:62px;padding:7px 4px;border:1px solid transparent;border-left:4px solid transparent;border-radius:3px;color:#595d55;font:650 14px/1 var(--font-data);text-transform:uppercase;letter-spacing:.02em;transition:color .15s,background .15s,border-color .15s,transform .08s}
.tool-link svg{width:21px;height:21px;stroke:currentColor;fill:none;stroke-width:1.7;shape-rendering:geometricPrecision}
.tool-link:hover,.tool-link:focus-visible{border-color:#9f957d;border-left-color:var(--blue);background:#eee4cf;color:var(--ink)}
.tool-link:active{transform:translateY(1px)}.tool-link.active{border-color:#b68a70;border-left-color:var(--signal);color:#873c20;background:#f3dac4}
.rail-foot{margin-top:auto;padding:28px 8px 15px;border-top:1px solid #9c927b;color:#62655d;font:13px/1.5 var(--font-data);text-align:center}
.rail-foot:before{content:"";display:block;width:48px;height:12px;margin:-17px auto 10px;background:repeating-linear-gradient(0deg,#756c58 0 1px,#b3a68c 1px 3px,#756c58 3px 4px);box-shadow:inset 1px 0 0 #665e4c,inset -1px 0 0 #e6d9bc;opacity:.8}
.console-window{position:relative;min-width:0;background:#ded4bd}
.status-rail{position:absolute;z-index:6;left:0;top:0;bottom:0;width:5px;background:var(--muted);transition:background .15s}
.status-rail.nominal{background:var(--nominal)}.status-rail.attention{background:var(--signal)}.status-rail.danger{background:var(--danger)}
.window-bar{min-height:64px;display:grid;grid-template-columns:minmax(220px,1fr) auto auto;align-items:center;border-bottom:2px solid #81765f;background:linear-gradient(180deg,#ded3ba,#c7b99c);box-shadow:inset 0 1px 0 #f5ead2;padding:0 14px 0 21px}
.window-title{display:flex;min-width:0;align-items:center;gap:12px}
.window-glyph{display:grid;place-items:center;width:30px;height:30px;border:2px solid #5e594b;border-radius:2px;background:var(--screen);color:var(--phosphor);font:700 13px/1 var(--font-data);box-shadow:inset 0 0 7px #101d18}
.window-title b{display:block;font-size:17px;line-height:1.2;font-weight:700;letter-spacing:.005em}.window-title small{display:block;margin-top:2px;color:var(--muted);font:13px/1.35 var(--font-data);letter-spacing:.02em;text-transform:uppercase}
.live-state{display:flex;align-items:center;gap:9px;min-width:0;min-height:38px;padding:0 12px;border:2px solid #5d6654;border-radius:2px;background-color:var(--screen);background-image:repeating-linear-gradient(0deg,transparent 0 3px,rgba(0,0,0,.12) 3px 4px);box-shadow:inset 0 0 12px rgba(0,0,0,.48),1px 1px 0 #efe3c8;color:var(--phosphor);font:14px/1.3 var(--font-data);text-shadow:0 0 4px rgba(215,232,163,.22);white-space:nowrap}
.state-lamp{width:9px;height:9px;border:1px solid currentColor;background:var(--signal);box-shadow:inset 0 0 0 1px var(--screen)}
.window-tools{display:flex;align-items:center;gap:10px}
.deck-clock{color:#565b53;font:13px/1 var(--font-data);font-variant-numeric:tabular-nums;white-space:nowrap}
.refresh{display:inline-flex;min-width:84px;min-height:44px;align-items:center;justify-content:center;gap:8px;padding:0 13px;border:1px solid #746a56;border-bottom-width:3px;border-radius:4px;background:linear-gradient(180deg,#f3e8d0,#c9b99b);box-shadow:inset 0 1px 0 #fff7e6,0 1px 0 #766b55;color:var(--ink);cursor:pointer;font:650 14px/1 var(--font-data);transition:background .15s,border-color .15s,color .15s,transform .08s}
.refresh svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8}.refresh:hover{border-color:var(--signal);color:#8c3c1e;background:#f6dcc8}.refresh:active{transform:translateY(2px);border-bottom-width:1px}.refresh:disabled{cursor:wait;opacity:.65}
.deck-main{min-width:0;padding:16px 18px 24px}
.brief-strip{display:grid;grid-template-columns:112px minmax(210px,.65fr) minmax(280px,1fr) auto;align-items:center;min-height:52px;border:1px solid #9e9278;border-radius:3px;background:#fff8e7;box-shadow:inset 0 1px 0 #fff;padding:6px 14px}
.micro-label{color:#9b4827;font:700 14px/1.25 var(--font-data);letter-spacing:.04em;text-transform:uppercase}
.brief-strip b{font-size:16px;line-height:1.4;font-weight:700}.brief-strip p{margin:0;color:var(--ink-soft);font-size:14px;line-height:1.45}.brief-meta{color:var(--muted);font:13px/1.3 var(--font-data);white-space:nowrap}
.next-action{display:grid;grid-template-columns:112px minmax(0,1fr) auto;align-items:center;gap:12px;min-height:76px;margin-top:9px;border:1px solid #bc7758;border-left:7px solid var(--signal);border-radius:3px;background:linear-gradient(100deg,#faead9,#f4d8c2);box-shadow:inset 0 1px 0 #fff8ec;padding:10px 13px 10px 10px}
.next-action-copy{min-width:0}.next-action h1{display:-webkit-box;overflow:hidden;margin:0;font-size:18px;line-height:1.35;font-weight:700;letter-spacing:0;-webkit-box-orient:vertical;-webkit-line-clamp:2}.next-action p{overflow:hidden;margin:4px 0 0;color:#655b50;font:14px/1.4 var(--font-data);text-overflow:ellipsis;white-space:nowrap}
.action-button{display:inline-flex;min-height:44px;align-items:center;justify-content:center;gap:10px;padding:0 15px;border:1px solid #8d4125;border-bottom-width:3px;border-radius:4px;background:linear-gradient(180deg,#d87347,#b64f29);box-shadow:inset 0 1px 0 #efa585,0 1px 0 #75402d;color:#fff9ed;font:700 14px/1 var(--font-data);white-space:nowrap;transition:background .15s,color .15s,transform .08s}
.action-button:hover{background:#963f21}.action-button:active{transform:translateY(2px);border-bottom-width:1px}.action-button svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.7}
.deck-section{margin-top:14px;border:1px solid #8e866e;border-radius:4px;background:var(--surface);box-shadow:2px 2px 0 rgba(99,87,64,.28),inset 0 1px 0 #fff;overflow:hidden}
.section-head{display:flex;min-height:48px;align-items:center;gap:11px;padding:0 14px;border-bottom:1px solid #a99f86;background:#e5dcc7}
#deck-fleet .section-head{border-left:7px solid var(--blue);background:var(--blue-soft)}
#deck-agents .section-head{border-left:7px solid var(--green);background:var(--green-soft)}
#deck-projects .section-head{border-left:7px solid var(--ochre);background:var(--ochre-soft)}
#deck-signals .section-head{border-left:7px solid var(--signal);background:var(--signal-soft)}
.section-index{color:var(--muted);font:14px/1 var(--font-data)}.section-head h2{margin:0;font-size:18px;line-height:1.2;font-weight:750}.section-note{margin-left:5px;color:var(--ink-soft);font-size:14px;line-height:1.35}.section-head>a{margin-left:auto;color:#424a46;font:650 14px/1 var(--font-data)}.section-head>a:hover{color:#8b3d20;text-decoration:underline}
.fleet-head,.telemetry-row{display:grid;grid-template-columns:minmax(200px,1.35fr) minmax(110px,.72fr) minmax(80px,.5fr) minmax(120px,.7fr) minmax(100px,.58fr);align-items:center;column-gap:14px}
.fleet-head{min-height:40px;padding:0 15px;background:#334f55;color:#f1f1df;font:700 14px/1 var(--font-data);text-transform:uppercase;letter-spacing:.035em}
.telemetry-row{min-height:66px;padding:10px 15px;border-top:1px solid #d2c8b1;background:#fffaf0;transition:background .15s}.telemetry-row:nth-child(even){background:#f5eedf}.telemetry-row:first-child{border-top:0}.telemetry-row:hover{background:#e7f0ec}
.row-copy{min-width:0}.row-copy b,.row-copy small{display:block}.row-copy b{overflow:hidden;color:var(--ink);font-size:16px;line-height:1.4;font-weight:700;text-overflow:ellipsis;white-space:nowrap}.row-copy small{overflow:hidden;margin-top:3px;color:var(--muted);font:14px/1.4 var(--font-data);text-overflow:ellipsis;white-space:nowrap}
.telemetry-row code{overflow:hidden;color:#414c4d;font-size:15px;text-overflow:ellipsis;white-space:nowrap}.metric{color:#355c4a;font:700 15px/1.35 var(--font-data);font-variant-numeric:tabular-nums}.metric small{color:var(--muted);font-size:13px;font-weight:650;text-transform:uppercase}
.storage{display:flex;align-items:center;gap:9px}.meter{display:block;width:58px;height:7px;border:1px solid #918a73;background:#d6ccb5}.meter i{display:block;height:100%;background:var(--nominal)}.telemetry-row.warn .meter i,.telemetry-row.offline .meter i{background:var(--danger)}
.status-cell{display:flex;justify-content:flex-end;align-items:center;gap:8px;color:var(--nominal);font:750 14px/1 var(--font-data);text-transform:uppercase;white-space:nowrap}.status-dot{width:9px;height:9px;border:1px solid currentColor;background:currentColor}.telemetry-row.warn .status-cell,.telemetry-row.offline .status-cell{color:var(--danger)}
.dual-panel{display:grid;grid-template-columns:1fr 1fr}.subpanel+.subpanel{border-left:1px solid #aaa087}.subhead{min-height:40px;display:flex;align-items:center;padding:0 14px;border-bottom:1px solid #aaa087;background:#edf0e6;color:#51594f;font:700 13px/1.3 var(--font-data);letter-spacing:.025em;text-transform:uppercase}
.subpanel:first-child .subhead{background:#e5ecd9}.subpanel:last-child .subhead{background:#dce9e7}
.trace-row,.service-row{display:grid;grid-template-columns:16px minmax(0,1fr) auto;align-items:center;min-height:64px;padding:9px 14px;border-top:1px solid #d2c8b1;background:#fffaf0}.trace-row:nth-child(odd),.service-row:nth-child(even){background:#f5eedf}.trace-row:first-of-type,.service-row:first-of-type{border-top:0}.trace-mark{width:9px;height:9px;border:2px solid var(--green);background:#dce6d4}.trace-kind{color:var(--muted);font:700 13px/1 var(--font-data);text-transform:uppercase}.service-status{color:var(--nominal);font:750 14px/1 var(--font-data);text-transform:uppercase}.service-row.offline .service-status{color:var(--danger)}
.empty-channel{display:flex;min-height:72px;align-items:center;gap:12px;padding:12px 14px;color:var(--muted);background:#fffaf0}.empty-channel.compact{min-height:66px}.empty-mark{color:var(--signal);font:18px/1 var(--font-data)}.empty-channel b,.empty-channel small{display:block}.empty-channel b{color:var(--ink-soft);font-size:16px;line-height:1.4;font-weight:650}.empty-channel small{margin-top:3px;color:var(--muted);font-size:14px;line-height:1.4}
.project-row,.signal-row{display:grid;align-items:center;min-height:64px;padding:9px 14px;border-top:1px solid #d2c8b1;background:#fffaf0;transition:background .15s,color .15s}.project-row:nth-child(even),.signal-row:nth-child(even){background:#f5eedf}.project-row:first-child,.signal-row:first-child{border-top:0}.project-row:hover{background:#f5e8c4}.signal-row:hover{background:#f5dfd1}.project-row{grid-template-columns:52px minmax(0,1fr) auto;gap:12px}.project-row code,.signal-row code{color:var(--muted);font-size:14px}.row-state{color:var(--nominal);font:750 14px/1 var(--font-data);text-transform:uppercase}.row-state.attention{color:#a24927}
.signal-row{grid-template-columns:52px minmax(0,1fr) 130px;gap:12px}.signal-row b{overflow:hidden;font-size:16px;line-height:1.4;font-weight:650;text-overflow:ellipsis;white-space:nowrap}.signal-row>span{justify-self:end;color:var(--muted);font:14px/1 var(--font-data);white-space:nowrap}
.deck-footer{display:flex;align-items:center;justify-content:space-between;gap:14px;min-height:46px;margin-top:14px;padding:0 5px;color:#565b53;font:13px/1.4 var(--font-data)}.deck-footer nav{display:flex;gap:18px}.deck-footer a:hover{color:#8b3d20;text-decoration:underline}
@media(max-width:900px){
  .cassette-workbench{padding:0}.ops-desktop{display:flex;min-height:100vh;flex-direction:column;border:0;border-radius:0;box-shadow:none}.tool-rail{position:static;z-index:auto;order:0;height:68px;border:0;border-bottom:2px solid #827862}.tool-rail:before,.rail-brand,.rail-foot{display:none}.tool-rail nav{height:100%;display:grid;grid-template-columns:repeat(5,1fr);padding:0;gap:0}.tool-link{min-height:68px;border:0;border-bottom:4px solid transparent;border-radius:0}.tool-link:hover,.tool-link:focus-visible{border-left:0;border-bottom-color:var(--blue)}.tool-link.active{border-left:0;border-bottom-color:var(--signal)}.console-window{order:1;flex:1}
  .window-bar{grid-template-columns:minmax(190px,1fr) auto}.live-state{display:none}.deck-main{padding:14px 12px 22px}.brief-strip{grid-template-columns:104px minmax(180px,.7fr) minmax(210px,1fr)}.brief-meta{display:none}
}
@media(max-width:720px){
  body{font-size:16px}.window-bar{min-height:60px;padding-left:14px}.window-title small{display:none}.deck-clock{display:none}.refresh{min-width:44px;width:44px;padding:0}.refresh span{display:none}
  .brief-strip{grid-template-columns:100px 1fr;min-height:78px;padding:9px 12px}.brief-strip p{grid-column:2}.next-action{grid-template-columns:100px minmax(0,1fr) auto;gap:8px 10px;padding:11px}.next-action h1{font-size:17px}.action-button{min-height:44px}
  .section-note{display:none}.fleet-head,.telemetry-row{grid-template-columns:minmax(150px,1fr) minmax(88px,.55fr) minmax(92px,.55fr)}.fleet-spec,.fleet-mem{display:none}.telemetry-row{min-height:68px}.dual-panel{grid-template-columns:1fr}.subpanel+.subpanel{border-left:0;border-top:1px solid #aaa087}
}
@media(max-width:480px){
  .deck-main{padding-inline:9px}.window-title b{font-size:16px}.tool-link{font-size:13px}.tool-link svg{width:20px;height:20px}.brief-strip{grid-template-columns:1fr}.brief-strip .micro-label{margin-bottom:3px}.brief-strip p{grid-column:1;margin-top:2px}.next-action{grid-template-columns:minmax(0,1fr) auto;gap:6px 10px}.next-action .micro-label{grid-column:1}.next-action-copy{grid-column:1/-1}.next-action .action-button{grid-column:2;grid-row:1;justify-self:end}.next-action p{white-space:normal}.section-head{padding-inline:11px}.section-head>a{font-size:0}.section-head>a:after{content:"↗";font-size:18px}.fleet-head,.telemetry-row{grid-template-columns:minmax(135px,1fr) 72px 88px;column-gap:8px;padding-inline:11px}.meter{width:32px}.status-cell{font-size:13px}.signal-row{grid-template-columns:40px minmax(0,1fr)}.signal-row>span{display:none}.project-row{grid-template-columns:40px minmax(0,1fr)}.project-row>.row-state{display:none}.deck-footer>span{display:none}.deck-footer{justify-content:flex-end;padding-inline:4px}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
"""

    script = """
(() => {
  const esc = value => { const node = document.createElement('span'); node.textContent = String(value ?? ''); return node.innerHTML; };
  const frame = document.getElementById('opsFrame');
  const rail = document.getElementById('statusRail');
  const fleetRows = document.getElementById('fleetRows');
  const serviceRows = document.getElementById('serviceRows');
  const refresh = document.getElementById('deckRefresh');
  const refreshLabel = document.getElementById('refreshLabel');
  const state = document.getElementById('deckState');
  const stateLamp = document.getElementById('stateLamp');
  const fleetCount = document.getElementById('fleetCount');
  const clock = document.getElementById('deckClock');
  const brainIssues = Number(frame.dataset.brainIssues || 0);

  function tick() {
    clock.textContent = new Date().toLocaleTimeString('en-GB', {hour12:false}) + ' local';
  }
  tick();
  setInterval(tick, 1000);

  async function loadFleet() {
    const response = await fetch('/api/vps/fleet', {credentials:'same-origin', cache:'no-store'});
    if (!response.ok) throw new Error(`Fleet HTTP ${response.status}`);
    const data = await response.json();
    const items = Array.isArray(data.items) ? data.items : [];
    const total = Number(data.summary?.total ?? items.length);
    const online = Number(data.summary?.online ?? items.filter(item => item.ok).length);
    fleetCount.textContent = `${online}/${total} linked`;
    fleetRows.innerHTML = items.map(item => {
      const memTotal = Number(item.mem_total_mb || 0);
      const memUsed = Number(item.mem_used_mb || 0);
      const memPct = memTotal ? Math.min(Math.max(Math.round(memUsed / memTotal * 100), 0), 100) : 0;
      const diskPct = Number(item.disk_used_percent || 0);
      const klass = !item.ok ? 'offline' : diskPct >= 85 ? 'warn' : '';
      const status = !item.ok ? 'No link' : diskPct >= 85 ? 'Disk warn' : 'Nominal';
      return `<div class="telemetry-row ${klass}" role="row"><span class="row-copy" role="cell"><b>${esc(item.name || 'Unknown')}</b><small>${esc(item.region || item.hostname || 'unlabelled')}</small></span><code class="fleet-spec" role="cell">${esc(item.spec || '—')}</code><span class="metric fleet-mem" role="cell"><small>mem</small> ${memPct}%</span><span class="metric storage" role="cell"><span class="meter"><i style="width:${Math.min(Math.max(diskPct,0),100)}%"></i></span>${diskPct}%</span><span class="status-cell" role="cell"><i class="status-dot"></i>${status}</span></div>`;
    }).join('') || '<div class="empty-channel"><span class="empty-mark">—</span><span><b>No fleet records</b><small>The live endpoint returned an empty set.</small></span></div>';
    return {total, online};
  }

  async function loadServices() {
    const response = await fetch('/api/dashboard/health', {credentials:'same-origin', cache:'no-store'});
    if (!response.ok) throw new Error(`Service HTTP ${response.status}`);
    const data = await response.json();
    const items = Array.isArray(data.services) ? data.services : [];
    serviceRows.innerHTML = items.map(item => `<div class="service-row ${item.alive ? '' : 'offline'}"><i class="status-dot"></i><span class="row-copy"><b>${esc(item.name || 'Service')}</b><small>${esc(item.location || 'unknown')} · ${Number(item.latency_ms || 0)} ms</small></span><span class="service-status">${item.alive ? 'Responding' : 'No response'}</span></div>`).join('') || '<div class="empty-channel compact"><span class="empty-mark">—</span><span><b>Service channel not connected</b><small>No health checks are configured.</small></span></div>';
    return {total:items.length, online:items.filter(item => item.alive).length};
  }

  async function scan(showBusy = false) {
    if (showBusy) {
      refresh.disabled = true;
      refresh.setAttribute('aria-busy', 'true');
      refreshLabel.textContent = 'Scanning';
    }
    const results = await Promise.allSettled([loadFleet(), loadServices()]);
    const fleet = results[0].status === 'fulfilled' ? results[0].value : null;
    const services = results[1].status === 'fulfilled' ? results[1].value : null;
    const failures = (fleet ? fleet.total - fleet.online : 0) + (services ? services.total - services.online : 0);
    const channelGaps = (!fleet || fleet.total === 0 ? 1 : 0) + (!services || services.total === 0 ? 1 : 0);
    if (failures > 0) {
      state.textContent = `${failures} live exception${failures === 1 ? '' : 's'}`;
      rail.className = 'status-rail danger';
      stateLamp.style.background = 'var(--danger)';
    } else if (channelGaps > 0) {
      state.textContent = `${channelGaps} live channel${channelGaps === 1 ? '' : 's'} not connected`;
      rail.className = 'status-rail attention';
      stateLamp.style.background = 'var(--signal)';
    } else if (brainIssues > 0) {
      state.textContent = `${brainIssues} queued · live nominal`;
      rail.className = 'status-rail attention';
      stateLamp.style.background = 'var(--signal)';
    } else {
      state.textContent = 'All live channels responding';
      rail.className = 'status-rail nominal';
      stateLamp.style.background = 'var(--phosphor)';
    }
    if (!fleet) fleetRows.innerHTML = '<div class="empty-channel"><span class="empty-mark">—</span><span><b>Fleet channel not connected</b><small>No status was inferred. Retry when ready.</small></span></div>';
    if (!services) serviceRows.innerHTML = '<div class="empty-channel compact"><span class="empty-mark">—</span><span><b>Service channel not connected</b><small>No runtime status was inferred.</small></span></div>';
    if (showBusy) {
      refresh.disabled = false;
      refresh.removeAttribute('aria-busy');
      refreshLabel.textContent = 'Scan';
    }
  }

  refresh.addEventListener('click', () => scan(true));
  scan(false);
})();
"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#657d80">
  <title>Command Deck · Brain</title>
  <style>{css}</style>
</head>
<body class="cassette-workbench">
  <a class="skip-link" href="#deck-brief">Skip to workbench</a>
  <div class="ops-desktop" id="opsFrame" data-brain-issues="{brain_issues}">
    <aside class="tool-rail" aria-label="Workbench navigation">
      <a class="rail-brand" href="/design/cassette" aria-label="Command Deck"><span class="pixel-mark">HB</span></a>
      <nav>
        <a class="tool-link active" href="#deck-brief" aria-label="Brief">
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3.5 3.5h13v13h-13zM6 7h8M6 10h8M6 13h5"/></svg><span>Brief</span>
        </a>
        <a class="tool-link" href="#deck-fleet" aria-label="Fleet">
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 5h12v4H4zM4 11h12v4H4zM7 7h.1M7 13h.1"/></svg><span>Fleet</span>
        </a>
        <a class="tool-link" href="#deck-agents" aria-label="Agents and services">
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3v3M5 8h10v7H5zM3 11h2M15 11h2M8 11h.1M12 11h.1"/></svg><span>Agents</span>
        </a>
        <a class="tool-link" href="#deck-projects" aria-label="Projects">
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3.5 5.5h5l1.5 2h6.5v8h-13z"/></svg><span>Projects</span>
        </a>
        <a class="tool-link" href="#deck-signals" aria-label="Signals">
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 15.5v-5M7 15.5h6M6.5 9a5 5 0 1 1 7 0M8.5 11a2.3 2.3 0 1 1 3 0"/></svg><span>Signals</span>
        </a>
      </nav>
      <div class="rail-foot">B-03<br>LOCAL</div>
    </aside>

    <div class="console-window">
      <i class="status-rail {rail_state}" id="statusRail" aria-hidden="true"></i>
      <header class="window-bar">
        <a class="window-title" href="/design/cassette"><span class="window-glyph">HB</span><span><b>Command Deck</b><small>Personal operations / candidate B-03</small></span></a>
        <div class="live-state"><i class="state-lamp" id="stateLamp"></i><span id="deckState">{_e(initial_state)}</span></div>
        <div class="window-tools"><time class="deck-clock" id="deckClock">--:--:-- local</time><button class="refresh" id="deckRefresh" type="button" aria-label="Rescan live channels"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M15.5 7A6 6 0 1 0 16 12M15.5 3v4h-4"/></svg><span id="refreshLabel">Scan</span></button></div>
      </header>

      <main class="deck-main">
        <section class="brief-strip" id="deck-brief" aria-labelledby="brief-label">
          <span class="micro-label" id="brief-label">Shift brief</span><b>{_e(brief_title)}</b><p>{_e(brief_copy)}</p><span class="brief-meta">{_e(now_utc)}</span>
        </section>

        <section class="next-action" id="deck-next" aria-labelledby="next-label">
          <span class="micro-label" id="next-label">Next action</span>
          <div class="next-action-copy"><h1>{_e(next_title)}</h1><p>{_e(next_meta)} · ref {_e(proposal_id)}</p></div>
          <a class="action-button" href="{_e(next_href, quote=True)}"><span>{_e(next_action)}</span><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h11M11 6l4 4-4 4"/></svg></a>
        </section>

        <section class="deck-section" id="deck-fleet" aria-labelledby="fleet-title">
          <header class="section-head"><span class="section-index">01</span><h2 id="fleet-title">Fleet</h2><span class="section-note" id="fleetCount">Live scan starting</span><a href="/fleet">Open fleet ↗</a></header>
          <div class="fleet-head" role="row"><span>Node / region</span><span class="fleet-spec">Spec</span><span class="fleet-mem">Memory</span><span>Storage</span><span style="text-align:right">State</span></div>
          <div id="fleetRows" role="table" aria-label="Live fleet telemetry"><div class="empty-channel"><span class="empty-mark">—</span><span><b>Scanning fleet channel</b><small>No machine state is assumed until the endpoint responds.</small></span></div></div>
        </section>

        <section class="deck-section" id="deck-agents" aria-labelledby="agents-title">
          <header class="section-head"><span class="section-index">02</span><h2 id="agents-title">Agents / Services</h2><span class="section-note">Activity traces are not runtime health</span></header>
          <div class="dual-panel">
            <div class="subpanel"><div class="subhead">Known agent activity · Brain records</div>{agents_html}</div>
            <div class="subpanel"><div class="subhead">Runtime services · live responses</div><div id="serviceRows"><div class="empty-channel compact"><span class="empty-mark">—</span><span><b>Scanning service channel</b><small>Waiting for the live health endpoint.</small></span></div></div></div>
          </div>
        </section>

        <section class="deck-section" id="deck-projects" aria-labelledby="projects-title">
          <header class="section-head"><span class="section-index">03</span><h2 id="projects-title">Projects</h2><span class="section-note">Only real Brain traces are shown</span><a href="/hub">Open modules ↗</a></header>
          <div>{projects_html}</div>
        </section>

        <section class="deck-section" id="deck-signals" aria-labelledby="signals-title">
          <header class="section-head"><span class="section-index">04</span><h2 id="signals-title">Signals</h2><span class="section-note">{signal_count} curated · updated {_e(board_updated)}</span><a href="/linuxdo">Open board ↗</a></header>
          <div>{signals_html}</div>
        </section>

        <footer class="deck-footer"><span>Candidate B-03 · real data where connected · no automatic actions</span><nav aria-label="Utility navigation"><a href="/">Current home</a><a href="/settings">Settings</a><a href="/logout">Log out</a></nav></footer>
      </main>
    </div>
  </div>
  <script>{script}</script>
</body>
</html>"""
