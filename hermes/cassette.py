from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


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
        if str(proposal.get("state") or "") == "pending":
            row["pending"] = int(row["pending"]) + 1

    if not projects:
        return """<div class="empty-channel">
          <b>PROJECT CHANNEL NOT CONNECTED</b>
          <span>No project activity is currently recorded in Brain. This deck will not invent it.</span>
        </div>"""

    rows = []
    for index, (key, data) in enumerate(list(projects.items())[:5], start=1):
        name = key.replace("_", " ").replace("-", " ").title()
        pending = int(data["pending"])
        state = f"{pending} awaiting review" if pending else "no decision queued"
        rows.append(
            f"""<a class="project-line" href="/proposals">
              <code>P-{index:02d}</code>
              <span><b>{_e(name)}</b><small>{int(data['count'])} Brain records · last trace {_e(_short_date(data['latest']))}</small></span>
              <em class="{'warn' if pending else ''}">{_e(state)}</em>
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
    seen: set[str] = set()
    rows = []
    for proposal in proposals:
        key = str(proposal.get("source_agent") or "").strip().lower()
        if key not in labels or key in seen:
            continue
        seen.add(key)
        rows.append(
            f"""<div class="agent-line">
              <i aria-hidden="true"></i>
              <span><b>{_e(labels[key])}</b><small>last Brain submission {_e(_short_date(proposal.get('created_at')))}</small></span>
              <em>ACTIVITY TRACE</em>
            </div>"""
        )
        if len(rows) == 4:
            break
    if rows:
        return "".join(rows)
    return """<div class="empty-channel compact">
      <b>NO DIRECT AGENT TRACE</b>
      <span>Runtime health appears below when the service channel responds.</span>
    </div>"""


def _signal_rows(board: dict) -> str:
    items = board.get("items") or []
    rows = []
    for index, item in enumerate(items[:5], start=1):
        title = _summary(item.get("title") or item.get("summary"), 150)
        source = str(item.get("source") or "Linux.do")
        href = _safe_href(item.get("url") or item.get("link"))
        rows.append(
            f"""<a class="signal-line" href="{_e(href, quote=True)}" target="_blank" rel="noopener">
              <code>S-{index:02d}</code><b>{_e(title)}</b><span>{_e(source)}</span>
            </a>"""
        )
    if rows:
        return "".join(rows)
    detail = "Collector reported an error." if board.get("fetch_errors") else "No curated signal is waiting."
    return f"""<a class="signal-line empty" href="/linuxdo">
      <code>S-00</code><b>{_e(detail)}</b><span>OPEN BOARD</span>
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
    """Render the isolated cassette-futurism workbench candidate."""
    pending_count = int(proposal_counts.get("pending", 0) or 0)
    conflicts = int(knowledge_health.get("conflict_count", 0) or 0)
    dirty = int(knowledge_health.get("dirty_nodes", 0) or 0)
    quarantined = int(knowledge_health.get("quarantined", 0) or 0)
    sync = lifecycle_overview.get("proposal_sync") or {}
    sync_missing = int(sync.get("missing", 0) or 0) if isinstance(sync, dict) else 0
    brain_issues = pending_count + conflicts + dirty + quarantined + sync_missing
    total_nodes = sum(int(value or 0) for value in node_counts.values())
    signal_count = len(linuxdo_board.get("items") or [])
    board_updated = str(linuxdo_board.get("updated_at") or "not checked")[:16].replace("T", " ")

    if pending_proposals:
        proposal = pending_proposals[0]
        proposal_id = str(proposal.get("proposal_id") or "")
        next_title = _summary(
            proposal.get("summary") or proposal.get("observation") or proposal.get("suggested_memory")
        )
        next_meta = f"Brain proposal · {proposal.get('risk_level') or 'review'} risk"
        next_href = f"/review/{_e(proposal_id, quote=True)}"
        next_action = "REVIEW DECISION"
    elif conflicts or dirty or quarantined or sync_missing:
        next_title = "Inspect the Brain records that need maintenance."
        next_meta = f"{conflicts} conflicts · {dirty} dirty · {sync_missing} unlinked"
        next_href = "/knowledge"
        next_action = "OPEN KNOWLEDGE"
        proposal_id = "BRAIN-MAINT"
    elif signal_count:
        next_title = _summary((linuxdo_board.get("items") or [{}])[0].get("title"), 164)
        next_meta = "Top item from the current signal board"
        next_href = "/linuxdo"
        next_action = "READ SIGNAL"
        proposal_id = "SIGNAL-01"
    else:
        next_title = "No manual decision is queued. Check the live fleet when you are ready."
        next_meta = "The deck is quiet; asynchronous telemetry is still checked below."
        next_href = "/fleet"
        next_action = "OPEN FLEET"
        proposal_id = "STANDBY"

    if brain_issues:
        brief_title = f"{brain_issues} thing{'s' if brain_issues != 1 else ''} need a look."
        brief_copy = "Start with one decision. Everything else can stay in the background."
        initial_state = "ATTENTION"
    else:
        brief_title = "Nothing asks for you yet."
        brief_copy = "Live fleet and service telemetry will report exceptions below."
        initial_state = "STANDBY"

    now_utc = datetime.now(timezone.utc).strftime("%Y.%m.%d / %H:%M UTC")
    projects_html = _project_rows(all_proposals)
    agents_html = _agent_rows(all_proposals)
    signals_html = _signal_rows(linuxdo_board)

    css = """
:root{--coal:#0c0e0c;--coal-2:#151712;--coal-3:#202219;--paper:#d8c9a7;--paper-dim:#9d947e;--orange:#ed5b2b;--orange-soft:#a74020;--green:#9ca66a;--red:#d44b37;--line:#514d3f;--mono:"Courier New",ui-monospace,monospace;--display:"Arial Narrow","Roboto Condensed",Impact,sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--coal);color:var(--paper);font-family:var(--mono);font-size:14px;line-height:1.45}body:before{content:"";position:fixed;inset:0;pointer-events:none;z-index:20;opacity:.09;background:repeating-linear-gradient(0deg,transparent 0 3px,#fff 4px),radial-gradient(circle at 20% 10%,#e95b2b33,transparent 25%)}a{color:inherit;text-decoration:none}button{font:inherit}.cassette-workbench{min-height:100vh;background:linear-gradient(90deg,#090a08 0 28px,var(--coal) 28px calc(100% - 28px),#090a08 calc(100% - 28px));padding:18px 42px 56px}.deck-frame{max-width:1460px;margin:0 auto;border-left:1px solid var(--line);border-right:1px solid var(--line)}
.deck-header{display:grid;grid-template-columns:1.25fr 1fr auto;min-height:108px;border-top:8px solid var(--orange);border-bottom:1px solid var(--line);background:var(--coal-2)}.deck-id{display:flex;align-items:center;gap:18px;padding:18px 24px;border-right:1px solid var(--line)}.deck-mark{display:grid;place-items:center;width:58px;height:58px;border:2px solid var(--paper);font:900 25px var(--display);letter-spacing:-.08em}.deck-id b{display:block;font:900 clamp(23px,3vw,39px)/.9 var(--display);letter-spacing:.03em;text-transform:uppercase}.deck-id small,.deck-clock small{display:block;margin-top:8px;color:var(--paper-dim);font-size:9px;letter-spacing:.18em}.deck-state{display:flex;align-items:center;gap:12px;padding:18px 24px}.lamp{width:12px;height:12px;border-radius:50%;background:var(--orange);box-shadow:0 0 16px #ed5b2b88}.deck-state strong{font:700 12px var(--mono);letter-spacing:.14em}.deck-state span{display:block;color:var(--paper-dim);font-size:10px;margin-top:4px}.deck-clock{min-width:210px;padding:19px 22px;border-left:1px solid var(--line);display:grid;align-content:center}.deck-clock b{font-size:13px}.refresh{margin-top:10px;padding:6px 9px;border:1px solid var(--line);background:transparent;color:var(--paper);cursor:pointer;text-align:left;font-size:10px;letter-spacing:.1em}.refresh:hover,.refresh:focus-visible{border-color:var(--orange);color:var(--orange)}
.deck-nav{display:flex;align-items:stretch;border-bottom:1px solid var(--line);background:#11130f;overflow-x:auto}.deck-nav a{min-width:125px;padding:12px 16px;border-right:1px solid var(--line);color:var(--paper-dim);font-size:10px;letter-spacing:.12em;white-space:nowrap}.deck-nav a:hover{background:var(--orange);color:var(--coal)}.deck-nav a:first-child{background:var(--paper);color:var(--coal);font-weight:700}.deck-nav .spacer{flex:1;min-width:30px}.deck-nav .brain-link{color:var(--green)}
.deck-main{overflow:hidden}.deck-brief{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(330px,.7fr);min-height:390px;border-bottom:1px solid var(--line)}.brief-copy{position:relative;padding:44px 42px 48px;background:linear-gradient(135deg,#171914 0 55%,#11130f 55%)}.serial{display:block;color:var(--orange);font-size:10px;letter-spacing:.24em}.brief-copy h1{max-width:850px;margin:38px 0 20px;font:900 clamp(56px,7.7vw,116px)/.79 var(--display);letter-spacing:-.055em;text-transform:uppercase}.brief-copy p{max-width:620px;margin:0;color:var(--paper-dim);font-size:13px}.brief-copy:after{content:"01";position:absolute;right:25px;bottom:10px;color:#292b22;font:900 110px/1 var(--display)}.next-action{position:relative;padding:36px 30px;background:var(--orange);color:#160a05;display:flex;flex-direction:column}.next-action .serial{color:#411509}.next-action h2{margin:56px 0 12px;font:900 clamp(28px,3vw,46px)/.95 var(--display);text-transform:uppercase}.next-action p{margin:0 0 20px;line-height:1.55}.next-action code{margin-top:auto;padding-top:18px;border-top:1px solid #6f250f;font-size:9px}.action-button{display:flex;justify-content:space-between;align-items:center;margin-top:18px;padding:12px 14px;border:2px solid #1b0b06;font-weight:700;font-size:11px;letter-spacing:.08em}.action-button:hover{background:#1b0b06;color:var(--orange)}
.status-tape{display:flex;border-bottom:1px solid var(--line);background:var(--paper);color:var(--coal);overflow:hidden}.status-tape span{padding:10px 18px;border-right:1px solid #827a66;font-size:10px;letter-spacing:.08em;white-space:nowrap}.status-tape b{color:#8a2c13}.deck-section{border-bottom:1px solid var(--line)}.section-head{display:grid;grid-template-columns:90px 1fr auto;align-items:end;min-height:105px;padding:20px 26px;border-bottom:1px solid var(--line);background:#11130f}.section-head>span{font:900 48px/.8 var(--display);color:var(--orange)}.section-head h2{margin:0;font:900 clamp(28px,4vw,52px)/.9 var(--display);letter-spacing:.01em;text-transform:uppercase}.section-head p{max-width:360px;margin:0;color:var(--paper-dim);font-size:10px;text-align:right}.section-head a{color:var(--orange)}
.telemetry-head,.telemetry-line{display:grid;grid-template-columns:1.2fr .8fr .65fr .8fr .85fr;align-items:center}.telemetry-head{padding:8px 22px;background:#202219;color:var(--paper-dim);font-size:9px;letter-spacing:.12em}.telemetry-line{min-height:62px;padding:10px 22px;border-top:1px solid #34362b}.telemetry-line:first-child{border-top:0}.telemetry-line:hover{background:#171a14}.telemetry-line b{font-size:14px}.telemetry-line small{display:block;color:var(--paper-dim)}.telemetry-line code{font-size:10px}.telemetry-line em,.project-line em{justify-self:end;font-style:normal;font-size:9px;letter-spacing:.08em;color:var(--green)}.telemetry-line.offline em,.telemetry-line.warn em,.project-line em.warn{color:var(--red)}.bar{width:110px;height:5px;background:#303229}.bar i{display:block;height:100%;background:var(--green)}
.agent-layout{display:grid;grid-template-columns:1fr 1fr}.agent-column{min-height:190px}.agent-column+div{border-left:1px solid var(--line)}.subhead{padding:10px 20px;border-bottom:1px solid var(--line);color:var(--orange);font-size:9px;letter-spacing:.14em}.agent-line{display:grid;grid-template-columns:18px 1fr auto;align-items:center;min-height:58px;padding:10px 20px;border-bottom:1px solid #34362b}.agent-line i{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 10px #9ca66a88}.agent-line b,.agent-line small{display:block}.agent-line small{color:var(--paper-dim);font-size:10px}.agent-line em{font-style:normal;color:var(--green);font-size:9px}.empty-channel{padding:34px 22px;color:var(--paper-dim)}.empty-channel b,.empty-channel span{display:block}.empty-channel b{color:var(--orange);font-size:11px;letter-spacing:.11em}.empty-channel span{margin-top:8px;font-size:10px}.empty-channel.compact{padding:28px 20px}
.project-line{display:grid;grid-template-columns:74px 1fr auto;align-items:center;min-height:70px;padding:10px 24px;border-top:1px solid #34362b}.project-line:first-child{border-top:0}.project-line:hover,.signal-line:hover{background:var(--paper);color:var(--coal)}.project-line code,.signal-line code{color:var(--orange);font-size:10px}.project-line b,.project-line small{display:block}.project-line small{margin-top:3px;color:var(--paper-dim);font-size:10px}.project-line:hover small{color:#4e493d}
.signal-line{display:grid;grid-template-columns:74px 1fr 130px;align-items:center;min-height:62px;padding:9px 24px;border-top:1px solid #34362b}.signal-line:first-child{border-top:0}.signal-line b{font-size:12px}.signal-line span{justify-self:end;color:var(--paper-dim);font-size:9px;letter-spacing:.08em}.signal-line:hover span{color:#4e493d}.deck-footer{display:grid;grid-template-columns:1fr auto;gap:18px;padding:26px;background:var(--coal-2);color:var(--paper-dim);font-size:9px;letter-spacing:.08em}.deck-footer a{color:var(--green)}
@media(max-width:900px){.cassette-workbench{padding:0 0 40px;background:var(--coal)}.deck-frame{border:0}.deck-header{grid-template-columns:1fr auto}.deck-state{display:none}.deck-clock{min-width:180px}.deck-brief{grid-template-columns:1fr}.brief-copy{min-height:350px}.next-action{min-height:310px}.agent-layout{grid-template-columns:1fr}.agent-column+div{border-left:0;border-top:1px solid var(--line)}.section-head{grid-template-columns:62px 1fr}.section-head p{display:none}.telemetry-head{display:none}.telemetry-line{grid-template-columns:1fr auto}.telemetry-line>*:nth-child(2),.telemetry-line>*:nth-child(3),.telemetry-line>*:nth-child(4){display:none}}
@media(max-width:560px){.deck-header{grid-template-columns:1fr}.deck-id{border-right:0}.deck-clock{display:block;min-width:0;padding:0;border-left:0;border-top:1px solid var(--line)}.deck-clock>b,.deck-clock>small{display:none}.deck-clock .refresh{width:100%;margin:0;padding:12px 20px;border:0;text-align:center}.deck-nav a{min-width:auto}.brief-copy{padding:35px 20px;min-height:320px}.brief-copy h1{font-size:54px}.brief-copy:after{font-size:72px}.next-action{padding:30px 20px;min-height:280px}.status-tape span:nth-child(n+3){display:none}.section-head{min-height:88px;padding:17px 16px}.section-head>span{font-size:35px}.section-head h2{font-size:31px}.telemetry-line,.project-line,.signal-line{padding-inline:16px}.project-line{grid-template-columns:48px 1fr}.project-line em{display:none}.signal-line{grid-template-columns:48px 1fr}.signal-line span{display:none}.agent-line em{display:none}.deck-footer{grid-template-columns:1fr}.deck-footer span:last-child{display:none}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""

    script = """
(() => {
  const esc = value => { const node = document.createElement('span'); node.textContent = String(value ?? ''); return node.innerHTML; };
  const fleetRows = document.getElementById('fleetRows');
  const serviceRows = document.getElementById('serviceRows');
  const refresh = document.getElementById('deckRefresh');
  const state = document.getElementById('deckState');
  const stateDetail = document.getElementById('deckStateDetail');
  const fleetTape = document.getElementById('fleetTape');
  const clock = document.getElementById('deckClock');

  function tick() { clock.textContent = new Date().toLocaleTimeString('en-GB', {hour12:false}) + ' / LOCAL'; }
  tick(); setInterval(tick, 1000);

  async function loadFleet() {
    const response = await fetch('/api/vps/fleet', {credentials:'same-origin', cache:'no-store'});
    if (!response.ok) throw new Error(`Fleet HTTP ${response.status}`);
    const data = await response.json();
    const items = Array.isArray(data.items) ? data.items : [];
    const total = Number(data.summary?.total ?? items.length);
    const online = Number(data.summary?.online ?? items.filter(item => item.ok).length);
    fleetTape.textContent = `FLEET ${online}/${total} LINKED`;
    fleetRows.innerHTML = items.map(item => {
      const memTotal = Number(item.mem_total_mb || 0);
      const memUsed = Number(item.mem_used_mb || 0);
      const memPct = memTotal ? Math.round(memUsed / memTotal * 100) : 0;
      const diskPct = Number(item.disk_used_percent || 0);
      const klass = !item.ok ? 'offline' : diskPct >= 85 ? 'warn' : '';
      const status = !item.ok ? 'NO LINK' : diskPct >= 85 ? 'DISK WARN' : 'NOMINAL';
      return `<div class="telemetry-line ${klass}"><span><b>${esc(item.name || 'Unknown')}</b><small>${esc(item.region || item.hostname || 'unlabelled')}</small></span><code>${esc(item.spec || '—')}</code><span><small>MEMORY</small>${memPct}%</span><span><small>DISK</small><span class="bar"><i style="width:${Math.min(diskPct,100)}%"></i></span></span><em>${status}</em></div>`;
    }).join('') || '<div class="empty-channel"><b>NO FLEET RECORDS</b><span>The live endpoint returned an empty set.</span></div>';
    return {total, online};
  }

  async function loadServices() {
    const response = await fetch('/api/dashboard/health', {credentials:'same-origin', cache:'no-store'});
    if (!response.ok) throw new Error(`Service HTTP ${response.status}`);
    const data = await response.json();
    const items = Array.isArray(data.services) ? data.services : [];
    serviceRows.innerHTML = items.map(item => `<div class="agent-line"><i style="background:${item.alive ? 'var(--green)' : 'var(--red)'}"></i><span><b>${esc(item.name || 'Service')}</b><small>${esc(item.location || 'unknown')} · ${Number(item.latency_ms || 0)} ms</small></span><em style="color:${item.alive ? 'var(--green)' : 'var(--red)'}">${item.alive ? 'RESPONDING' : 'NO RESPONSE'}</em></div>`).join('') || '<div class="empty-channel compact"><b>NO SERVICE CHANNELS</b><span>No health checks are configured.</span></div>';
    return {total:items.length, online:items.filter(item => item.alive).length};
  }

  async function scan(showBusy = false) {
    if (showBusy) { refresh.disabled = true; refresh.textContent = 'SCANNING…'; }
    const results = await Promise.allSettled([loadFleet(), loadServices()]);
    const fleet = results[0].status === 'fulfilled' ? results[0].value : null;
    const services = results[1].status === 'fulfilled' ? results[1].value : null;
    const failures = (fleet ? fleet.total - fleet.online : 1) + (services ? services.total - services.online : 1);
    if (failures > 0) {
      state.textContent = `${failures} TELEMETRY EXCEPTION${failures === 1 ? '' : 'S'}`;
      stateDetail.textContent = 'Open the affected channel below; no automatic action was taken.';
    } else {
      state.textContent = 'ALL LIVE CHANNELS RESPONDING';
      stateDetail.textContent = 'No runtime exception detected in the current scan.';
    }
    if (!fleet) fleetRows.innerHTML = '<div class="empty-channel"><b>FLEET CHANNEL UNAVAILABLE</b><span>The page stayed usable; retry when ready.</span></div>';
    if (!services) serviceRows.innerHTML = '<div class="empty-channel compact"><b>SERVICE CHANNEL UNAVAILABLE</b><span>No status was inferred.</span></div>';
    if (showBusy) { refresh.disabled = false; refresh.textContent = '↻ RESCAN LIVE CHANNELS'; }
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
  <meta name="theme-color" content="#0c0e0c">
  <title>Command Deck · Brain</title>
  <style>{css}</style>
</head>
<body class="cassette-workbench">
  <div class="deck-frame">
    <header class="deck-header">
      <a class="deck-id" href="/design/cassette"><span class="deck-mark">HB</span><span><b>Command Deck</b><small>PERSONAL OPERATIONS / CANDIDATE B-01</small></span></a>
      <div class="deck-state"><i class="lamp"></i><span><strong id="deckState">{_e(initial_state)} / LIVE SCAN STARTING</strong><span id="deckStateDetail">This page reports exceptions; it does not act on them.</span></span></div>
      <div class="deck-clock"><b id="deckClock">--:--:-- / LOCAL</b><small>RENDERED {_e(now_utc)}</small><button class="refresh" id="deckRefresh" type="button">↻ RESCAN LIVE CHANNELS</button></div>
    </header>

    <nav class="deck-nav" aria-label="Workbench navigation">
      <a href="#deck-brief">00 / BRIEF</a><a href="#deck-fleet">01 / FLEET</a><a href="#deck-agents">02 / AGENTS</a><a href="#deck-projects">03 / PROJECTS</a><a href="#deck-signals">04 / SIGNALS</a><span class="spacer"></span><a class="brain-link" href="/proposals">BRAIN SUBSYSTEM ↗</a>
    </nav>

    <main class="deck-main">
      <section class="deck-brief" id="deck-brief">
        <div class="brief-copy"><span class="serial">SHIFT BRIEF / {_e(now_utc)}</span><h1>{_e(brief_title)}</h1><p>{_e(brief_copy)}</p></div>
        <aside class="next-action" id="deck-next"><span class="serial">NEXT MANUAL ACTION</span><h2>{_e(next_title)}</h2><p>{_e(next_meta)}</p><code>REF / {_e(proposal_id)}</code><a class="action-button" href="{next_href}"><span>{_e(next_action)}</span><span>→</span></a></aside>
      </section>

      <div class="status-tape" aria-label="Live status strip"><span id="fleetTape">FLEET SCAN STARTING</span><span>BRAIN {total_nodes} NODES / {pending_count} QUEUED</span><span>SIGNALS {signal_count} / UPDATED {_e(board_updated)}</span><span><b>MANUAL CONTROL</b> / NO AUTO ACTIONS</span></div>

      <section class="deck-section" id="deck-fleet">
        <header class="section-head"><span>01</span><h2>Fleet</h2><p>Actual machine telemetry from <a href="/fleet">the live fleet channel ↗</a></p></header>
        <div class="telemetry-head"><span>NODE / REGION</span><span>SPEC</span><span>MEM</span><span>STORAGE</span><span>STATE</span></div>
        <div id="fleetRows"><div class="empty-channel"><b>SCANNING FLEET CHANNEL</b><span>Waiting for /api/vps/fleet. No status is assumed.</span></div></div>
      </section>

      <section class="deck-section" id="deck-agents">
        <header class="section-head"><span>02</span><h2>Agents / Services</h2><p>Submission traces are activity, not proof of runtime health.</p></header>
        <div class="agent-layout">
          <div class="agent-column"><div class="subhead">KNOWN AGENT ACTIVITY / BRAIN RECORDS</div>{agents_html}</div>
          <div class="agent-column"><div class="subhead">RUNTIME SERVICE RESPONSES / LIVE</div><div id="serviceRows"><div class="empty-channel compact"><b>SCANNING SERVICE CHANNEL</b><span>Waiting for /api/dashboard/health.</span></div></div></div>
        </div>
      </section>

      <section class="deck-section" id="deck-projects">
        <header class="section-head"><span>03</span><h2>Projects</h2><p>Only projects with real Brain traces appear here. <a href="/hub">Open modules ↗</a></p></header>
        <div>{projects_html}</div>
      </section>

      <section class="deck-section" id="deck-signals">
        <header class="section-head"><span>04</span><h2>Signals</h2><p>Curated opportunities and source material. <a href="/linuxdo">Open signal board ↗</a></p></header>
        <div>{signals_html}</div>
      </section>
    </main>

    <footer class="deck-footer"><span>COMMAND DECK B-01 / ISOLATED DESIGN CANDIDATE / REAL DATA WHERE CONNECTED</span><span><a href="/">CURRENT HOMEBASE</a> · <a href="/settings">SETTINGS</a> · <a href="/logout">LOG OUT</a></span></footer>
  </div>
  <script>{script}</script>
</body>
</html>"""
