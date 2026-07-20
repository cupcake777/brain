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
  --void:#070807;--bezel:#0d0f0c;--shell:#12140f;--surface:#171a14;--surface-raised:#1c1f18;
  --screen:#0b0e0b;--paper:#ddd7c8;--paper-soft:#b6b2a5;--muted:#85877b;
  --line:#30342a;--line-strong:#4b5042;--signal:#df6b38;--signal-deep:#351c12;
  --phosphor:#aab783;--danger:#df6b58;--font-ui:Inter,"IBM Plex Sans",system-ui,-apple-system,sans-serif;
  --font-data:"IBM Plex Mono","SFMono-Regular",Consolas,"Liberation Mono",monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;background:var(--void)}
body{margin:0;min-width:320px;background:
  radial-gradient(circle at 1px 1px,rgba(221,215,200,.055) 1px,transparent 1.1px) 0 0/6px 6px,
  var(--void);color:var(--paper);font:13px/1.45 var(--font-ui)}
a{color:inherit;text-decoration:none}button{font:inherit}code{font-family:var(--font-data)}
:focus-visible{outline:2px solid var(--signal);outline-offset:2px}
.skip-link{position:fixed;left:16px;top:-60px;z-index:100;padding:10px 14px;background:var(--paper);color:var(--void)}
.skip-link:focus{top:16px}
.cassette-workbench{min-height:100vh;padding:20px}
.ops-desktop{display:grid;grid-template-columns:76px minmax(0,1fr);max-width:1280px;min-height:calc(100vh - 40px);margin:0 auto;border:1px solid var(--line-strong);background:var(--bezel);box-shadow:7px 7px 0 #000,inset 0 1px 0 rgba(221,215,200,.08)}
.tool-rail{position:relative;display:flex;flex-direction:column;border-right:1px solid var(--line);background:var(--shell)}
.tool-rail:before{content:"";position:absolute;inset:0 0 auto;height:3px;background:repeating-linear-gradient(90deg,var(--paper-soft) 0 2px,transparent 2px 4px);opacity:.45}
.rail-brand{display:grid;place-items:center;height:58px;border-bottom:1px solid var(--line)}
.pixel-mark{display:grid;place-items:center;width:28px;height:28px;border:1px solid var(--paper-soft);box-shadow:2px 2px 0 #000;color:var(--paper);font:700 10px/1 var(--font-data);letter-spacing:-.04em}
.tool-rail nav{display:flex;flex-direction:column;padding:8px 6px;gap:3px}
.tool-link{display:grid;place-items:center;gap:4px;min-height:52px;padding:6px 3px;border-left:2px solid transparent;color:var(--muted);font:500 9px/1 var(--font-data);text-transform:uppercase;letter-spacing:.04em;transition:color .15s,background .15s,border-color .15s}
.tool-link svg{width:17px;height:17px;stroke:currentColor;fill:none;stroke-width:1.5;shape-rendering:crispEdges}
.tool-link:hover,.tool-link:focus-visible{border-left-color:var(--paper-soft);background:var(--surface);color:var(--paper)}
.tool-link.active{border-left-color:var(--signal);color:var(--signal);background:var(--signal-deep)}
.rail-foot{margin-top:auto;padding:24px 8px 12px;border-top:1px solid var(--line);color:var(--muted);font:9px/1.5 var(--font-data);text-align:center}
.rail-foot:before{content:"";display:block;width:38px;height:10px;margin:-13px auto 8px;background:repeating-linear-gradient(0deg,#080908 0 1px,var(--line-strong) 1px 2px,#080908 2px 4px);box-shadow:inset 1px 0 0 #000,inset -1px 0 0 #000;opacity:.72}
.console-window{position:relative;min-width:0;background:var(--screen)}
.status-rail{position:absolute;z-index:6;left:0;top:0;bottom:0;width:3px;background:var(--muted);transition:background .15s}
.status-rail.nominal{background:var(--phosphor)}.status-rail.attention{background:var(--signal)}.status-rail.danger{background:var(--danger)}
.window-bar{min-height:52px;display:grid;grid-template-columns:minmax(200px,1fr) auto auto;align-items:center;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#171912 0,#10120e 100%);box-shadow:inset 0 1px 0 rgba(221,215,200,.045);padding:0 10px 0 17px}
.window-title{display:flex;min-width:0;align-items:center;gap:10px}
.window-glyph{display:grid;place-items:center;width:22px;height:22px;border:1px solid var(--line-strong);background:var(--screen);color:var(--paper-soft);font:700 9px/1 var(--font-data)}
.window-title b{display:block;font-size:13px;font-weight:650;letter-spacing:.01em}.window-title small{display:block;color:var(--muted);font:9px/1.3 var(--font-data);letter-spacing:.04em;text-transform:uppercase}
.live-state{display:flex;align-items:center;gap:8px;min-width:0;min-height:28px;padding:0 10px;border:1px solid #414739;background-color:#12170f;background-image:repeating-linear-gradient(0deg,transparent 0 2px,rgba(0,0,0,.16) 2px 3px),repeating-linear-gradient(90deg,transparent 0 3px,rgba(0,0,0,.1) 3px 4px);box-shadow:inset 0 0 10px rgba(0,0,0,.58),0 1px 0 rgba(221,215,200,.035);color:var(--phosphor);font:10px/1.25 var(--font-data);text-shadow:0 0 4px rgba(170,183,131,.2);white-space:nowrap}
.state-lamp{width:7px;height:7px;border:1px solid currentColor;background:var(--signal);box-shadow:inset 0 0 0 1px var(--shell)}
.window-tools{display:flex;align-items:center;gap:8px}
.deck-clock{color:var(--muted);font:10px/1 var(--font-data);font-variant-numeric:tabular-nums;white-space:nowrap}
.refresh{display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:34px;padding:0 11px;border:1px solid var(--line-strong);border-bottom-width:2px;border-radius:2px;background:linear-gradient(180deg,#252820,#171914);box-shadow:inset 0 1px 0 rgba(221,215,200,.07),0 1px 0 #000;color:var(--paper);cursor:pointer;font:600 10px/1 var(--font-data);letter-spacing:.02em;transition:background .15s,border-color .15s,color .15s,transform .08s}
.refresh svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:1.7}.refresh:hover{border-color:var(--signal);color:var(--signal)}.refresh:active{transform:translateY(1px);border-bottom-width:1px}.refresh:disabled{cursor:wait;opacity:.62}
.deck-main{min-width:0;padding:12px 14px 20px}
.brief-strip{display:grid;grid-template-columns:82px minmax(180px,.6fr) minmax(280px,1fr) auto;align-items:center;min-height:34px;border:1px solid var(--line);background:var(--surface);box-shadow:inset 0 1px 0 rgba(221,215,200,.025);padding:0 10px}
.micro-label{color:var(--signal);font:600 10px/1.2 var(--font-data);letter-spacing:.07em;text-transform:uppercase}
.brief-strip b{font-size:14px;font-weight:600}.brief-strip p{margin:0;color:var(--muted);font-size:11px}.brief-meta{color:var(--paper-soft);font:10px/1.2 var(--font-data);white-space:nowrap}
.next-action{display:grid;grid-template-columns:82px minmax(0,1fr) auto;align-items:center;gap:10px;min-height:58px;margin-top:6px;border:1px solid var(--line-strong);border-left:2px solid var(--signal);background:var(--surface-raised);box-shadow:inset 0 1px 0 rgba(221,215,200,.04);padding:7px 10px 7px 8px}
.next-action-copy{min-width:0}.next-action h1{display:-webkit-box;overflow:hidden;margin:0;font-size:14px;line-height:1.3;font-weight:600;letter-spacing:0;-webkit-box-orient:vertical;-webkit-line-clamp:2}.next-action p{overflow:hidden;margin:3px 0 0;color:var(--muted);font:9px/1.3 var(--font-data);text-overflow:ellipsis;white-space:nowrap}
.action-button{display:inline-flex;min-height:34px;align-items:center;justify-content:center;gap:12px;padding:0 10px;border:1px solid #6e412e;border-bottom-width:2px;border-radius:2px;background:linear-gradient(180deg,#42261b,#2d1a13);box-shadow:inset 0 1px 0 rgba(240,176,146,.11),0 1px 0 #000;color:#efaa8c;font:600 10px/1 var(--font-data);letter-spacing:.02em;white-space:nowrap;transition:background .15s,color .15s,transform .08s}
.action-button:hover{background:var(--signal);color:var(--void)}.action-button:active{transform:translateY(1px);border-bottom-width:1px}.action-button svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.5}
.deck-section{margin-top:10px;border:1px solid var(--line-strong);background:linear-gradient(180deg,rgba(221,215,200,.012),transparent 54px),var(--surface);box-shadow:inset 0 0 0 1px #0a0b09,inset 0 1px 0 rgba(221,215,200,.04)}
.section-head{display:flex;min-height:34px;align-items:center;gap:9px;padding:0 10px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#171912,#10120e);box-shadow:inset 0 1px 0 rgba(221,215,200,.035)}
.section-index{color:var(--muted);font:10px/1 var(--font-data)}.section-head h2{margin:0;font-size:13px;font-weight:650}.section-note{margin-left:4px;color:var(--muted);font-size:10px}.section-head>a{margin-left:auto;color:var(--paper-soft);font:10px/1 var(--font-data)}.section-head>a:hover{color:var(--signal)}
.fleet-head,.telemetry-row{display:grid;grid-template-columns:minmax(190px,1.35fr) minmax(100px,.72fr) minmax(70px,.5fr) minmax(110px,.7fr) minmax(90px,.58fr);align-items:center;column-gap:12px}
.fleet-head{min-height:27px;padding:0 12px;background:var(--screen);color:var(--muted);font:9px/1 var(--font-data);text-transform:uppercase;letter-spacing:.06em}
.telemetry-row{min-height:47px;padding:7px 12px;border-top:1px solid #252920;transition:background .15s}.telemetry-row:first-child{border-top:0}.telemetry-row:hover{background:#1b1e18}
.row-copy{min-width:0}.row-copy b,.row-copy small{display:block}.row-copy b{overflow:hidden;color:var(--paper);font-size:12px;font-weight:600;text-overflow:ellipsis;white-space:nowrap}.row-copy small{overflow:hidden;margin-top:2px;color:var(--muted);font:9px/1.25 var(--font-data);text-overflow:ellipsis;white-space:nowrap}
.telemetry-row code{overflow:hidden;color:var(--paper-soft);font-size:10px;text-overflow:ellipsis;white-space:nowrap}.metric{color:var(--phosphor);font:10px/1.2 var(--font-data);font-variant-numeric:tabular-nums;text-shadow:0 0 4px rgba(170,183,131,.12)}.metric small{color:var(--muted);font-size:8px;text-shadow:none;text-transform:uppercase}
.storage{display:flex;align-items:center;gap:8px}.meter{display:block;width:54px;height:3px;background:#30342b}.meter i{display:block;height:100%;background:var(--phosphor)}.telemetry-row.warn .meter i,.telemetry-row.offline .meter i{background:var(--danger)}
.status-cell{display:flex;justify-content:flex-end;align-items:center;gap:6px;color:var(--phosphor);font:600 9px/1 var(--font-data);text-transform:uppercase;white-space:nowrap}.status-dot{width:6px;height:6px;border:1px solid currentColor;background:currentColor}.telemetry-row.warn .status-cell,.telemetry-row.offline .status-cell{color:var(--danger)}
.dual-panel{display:grid;grid-template-columns:1fr 1fr}.subpanel+.subpanel{border-left:1px solid var(--line)}.subhead{min-height:30px;display:flex;align-items:center;padding:0 12px;border-bottom:1px solid #252920;background:var(--screen);color:var(--muted);font:9px/1 var(--font-data);letter-spacing:.05em;text-transform:uppercase}
.trace-row,.service-row{display:grid;grid-template-columns:12px minmax(0,1fr) auto;align-items:center;min-height:46px;padding:6px 12px;border-top:1px solid #252920}.trace-row:first-of-type,.service-row:first-of-type{border-top:0}.trace-mark{width:6px;height:6px;border:1px solid var(--paper-soft);background:transparent}.trace-kind{color:var(--muted);font:9px/1 var(--font-data);text-transform:uppercase}.service-status{color:var(--phosphor);font:600 9px/1 var(--font-data);text-transform:uppercase}.service-row.offline .service-status{color:var(--danger)}
.empty-channel{display:flex;min-height:58px;align-items:center;gap:10px;padding:10px 12px;color:var(--muted)}.empty-channel.compact{min-height:54px}.empty-mark{color:var(--signal);font:16px/1 var(--font-data)}.empty-channel b,.empty-channel small{display:block}.empty-channel b{color:var(--paper-soft);font-size:11px;font-weight:550}.empty-channel small{margin-top:2px;color:var(--muted);font-size:9px}
.project-row,.signal-row{display:grid;align-items:center;min-height:46px;padding:6px 12px;border-top:1px solid #252920;transition:background .15s,color .15s}.project-row:first-child,.signal-row:first-child{border-top:0}.project-row:hover,.signal-row:hover{background:#1c2019}.project-row{grid-template-columns:44px minmax(0,1fr) auto;gap:10px}.project-row code,.signal-row code{color:var(--muted);font-size:9px}.row-state{color:var(--phosphor);font:600 9px/1 var(--font-data);text-transform:uppercase}.row-state.attention{color:var(--signal)}
.signal-row{grid-template-columns:44px minmax(0,1fr) 110px;gap:10px}.signal-row b{overflow:hidden;font-size:11px;font-weight:550;text-overflow:ellipsis;white-space:nowrap}.signal-row>span{justify-self:end;color:var(--muted);font:9px/1 var(--font-data);white-space:nowrap}
.deck-footer{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:34px;margin-top:12px;padding:0 4px;color:var(--muted);font:9px/1.35 var(--font-data)}.deck-footer nav{display:flex;gap:14px}.deck-footer a:hover{color:var(--paper)}
@media(max-width:900px){
  .cassette-workbench{padding:0}.ops-desktop{display:flex;min-height:100vh;flex-direction:column;border:0;box-shadow:none}.tool-rail{position:static;z-index:auto;order:0;height:56px;border:0;border-bottom:1px solid var(--line-strong)}.tool-rail:before,.rail-brand,.rail-foot{display:none}.tool-rail nav{height:100%;display:grid;grid-template-columns:repeat(5,1fr);padding:0;gap:0}.tool-link{min-height:56px;border:0;border-bottom:2px solid transparent}.tool-link:hover,.tool-link:focus-visible{border-left:0;border-bottom-color:var(--paper-soft)}.tool-link.active{border-left:0;border-bottom-color:var(--signal)}.console-window{order:1;flex:1}
  .window-bar{grid-template-columns:minmax(170px,1fr) auto}.live-state{display:none}.deck-main{padding:10px 10px 18px}.brief-strip{grid-template-columns:72px minmax(170px,.7fr) minmax(220px,1fr)}.brief-meta{display:none}
}
@media(max-width:720px){
  .window-bar{min-height:50px;padding-left:12px}.window-title small{display:none}.deck-clock{display:none}.refresh{width:38px;padding:0}.refresh span{display:none}
  .brief-strip{grid-template-columns:68px 1fr;min-height:44px;padding:5px 9px}.brief-strip p{grid-column:2}.next-action{grid-template-columns:68px minmax(0,1fr) auto;gap:6px 8px;padding:7px}.next-action h1{font-size:13px}.action-button{min-height:32px}
  .section-note{display:none}.fleet-head,.telemetry-row{grid-template-columns:minmax(135px,1fr) minmax(82px,.55fr) minmax(78px,.5fr)}.fleet-spec,.fleet-mem{display:none}.telemetry-row{min-height:48px}.dual-panel{grid-template-columns:1fr}.subpanel+.subpanel{border-left:0;border-top:1px solid var(--line)}
}
@media(max-width:480px){
  .deck-main{padding-inline:7px}.window-title b{font-size:12px}.brief-strip{grid-template-columns:1fr}.brief-strip .micro-label{margin-bottom:2px}.brief-strip p{grid-column:1}.next-action{grid-template-columns:minmax(0,1fr) auto;gap:4px 8px}.next-action .micro-label{grid-column:1}.next-action-copy{grid-column:1/-1}.next-action .action-button{grid-column:2;grid-row:1;justify-self:end}.next-action p{display:none}.section-head{padding-inline:9px}.section-head>a{font-size:0}.section-head>a:after{content:"↗";font-size:12px}.fleet-head,.telemetry-row{grid-template-columns:minmax(120px,1fr) 64px 68px;column-gap:7px;padding-inline:9px}.meter{width:34px}.signal-row{grid-template-columns:34px minmax(0,1fr)}.signal-row>span{display:none}.project-row{grid-template-columns:34px minmax(0,1fr)}.project-row>.row-state{display:none}.deck-footer>span{display:none}.deck-footer{justify-content:flex-end;padding-inline:4px}
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
  <meta name="theme-color" content="#0d0f0c">
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
      <div class="rail-foot">B-02<br>LOCAL</div>
    </aside>

    <div class="console-window">
      <i class="status-rail {rail_state}" id="statusRail" aria-hidden="true"></i>
      <header class="window-bar">
        <a class="window-title" href="/design/cassette"><span class="window-glyph">HB</span><span><b>Command Deck</b><small>Personal operations / candidate B-02</small></span></a>
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

        <footer class="deck-footer"><span>Candidate B-02 · real data where connected · no automatic actions</span><nav aria-label="Utility navigation"><a href="/">Current home</a><a href="/settings">Settings</a><a href="/logout">Log out</a></nav></footer>
      </main>
    </div>
  </div>
  <script>{script}</script>
</body>
</html>"""
