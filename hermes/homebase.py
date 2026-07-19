from __future__ import annotations

import html
from datetime import datetime, timezone
from urllib.parse import urlparse


def _e(value: object, *, quote: bool = False) -> str:
    return html.escape(str(value), quote=quote)


def _pct(numerator: int, denominator: int) -> int:
    return round(numerator / denominator * 100) if denominator else 0


def _signal_href(value: object) -> str:
    """Allow only normal web URLs or same-origin paths in signal links."""
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return raw
    if not parsed.scheme and raw.startswith("/") and not raw.startswith("//"):
        return raw
    return "/linuxdo"


def _lifecycle_chart(node_counts: dict[str, int]) -> tuple[str, str]:
    stages = ("draft", "refined", "verified", "canonized", "deprecated")
    values = [int(node_counts.get(stage, 0) or 0) for stage in stages]
    peak = max(values) or 1
    points: list[tuple[int, int]] = []
    for index, value in enumerate(values):
        x = round(index * 520 / (len(values) - 1))
        y = round(124 - (value / peak * 94))
        points.append((x, y))
    line = " ".join(f"{x},{y}" for x, y in points)
    area = f"M {line.replace(' ', ' L ')} L 520,150 L 0,150 Z"
    return line, area


def _attention_rows(
    *,
    pending_proposals: list[dict],
    dirty_nodes: int,
    conflicts: int,
    quarantined: int,
    sync_missing: int,
    stale_nodes: int,
) -> tuple[str, int]:
    rows: list[str] = []
    for proposal in pending_proposals[:3]:
        proposal_id = str(proposal.get("proposal_id") or "")
        summary = str(
            proposal.get("summary")
            or proposal.get("observation")
            or proposal.get("suggested_memory")
            or "Untitled proposal"
        )
        summary = " ".join(summary.split())
        if len(summary) > 180:
            summary = summary[:177].rstrip() + "…"
        risk = str(proposal.get("risk_level") or "review")
        rows.append(
            f'''<a class="attention-row" href="/review/{_e(proposal_id, quote=True)}">
              <span class="item-icon agent-icon">✦</span>
              <span class="item-copy"><b>{_e(summary)}</b><small>Proposal inbox · {_e(risk)} risk</small></span>
              <code>{_e(proposal_id)}</code><em>Review</em>
            </a>'''
        )

    health_issues = [
        (conflicts, "Knowledge conflicts need resolution", f"{conflicts} conflicting node{'s' if conflicts != 1 else ''}", "!"),
        (dirty_nodes, "Knowledge metadata needs cleanup", f"{dirty_nodes} dirty node{'s' if dirty_nodes != 1 else ''}", "▤"),
        (quarantined, "Quarantined knowledge needs review", f"{quarantined} quarantined item{'s' if quarantined != 1 else ''}", "!"),
        (sync_missing, "Approved proposals are not linked", f"{sync_missing} item{'s' if sync_missing != 1 else ''} missing from Knowledge", "↻"),
        (stale_nodes, "Knowledge has gone quiet", f"{stale_nodes} maintained node{'s' if stale_nodes != 1 else ''} never retrieved", "▤"),
    ]
    for count, title, detail, icon in health_issues:
        if not count or len(rows) >= 3:
            continue
        rows.append(
            f'''<a class="attention-row" href="/knowledge">
              <span class="item-icon server-icon">{icon}</span>
              <span class="item-copy"><b>{_e(title)}</b><small>{_e(detail)}</small></span>
              <code>Brain</code><em>Inspect</em>
            </a>'''
        )

    total = len(pending_proposals) + sum(count for count, *_ in health_issues)
    if not rows:
        rows.append(
            '''<a class="attention-row clear" href="/proposals">
              <span class="item-icon clear-icon">✓</span>
              <span class="item-copy"><b>Nothing needs a decision right now</b><small>Proposal inbox and maintained knowledge are clear.</small></span>
              <code>Now</code><em>Open Brain</em>
            </a>'''
        )
    return "".join(rows), total


def home_page(
    *,
    node_counts: dict[str, int],
    chart_count: int,
    health_summary: dict,
    recent_nodes: list | None = None,
    do_status: dict | None = None,
    proxy_status: dict | None = None,
    proxy_traffic: list | None = None,
    sub2api: dict | None = None,
    linuxdo_board: dict | None = None,
    proposal_counts: dict | None = None,
    knowledge_health: dict | None = None,
    lifecycle_overview: dict | None = None,
    pending_proposals: list | None = None,
) -> str:
    """Render the live Brain home page using the Homebase visual language."""
    del recent_nodes, do_status, proxy_status, proxy_traffic, sub2api

    proposal_counts = proposal_counts or {}
    knowledge_health = knowledge_health or health_summary or {}
    lifecycle_overview = lifecycle_overview or {}
    pending_proposals = pending_proposals or []
    linuxdo_board = linuxdo_board or {}

    total_nodes = sum(int(value or 0) for value in node_counts.values())
    canonized = int(node_counts.get("canonized", 0) or 0)
    refined = int(node_counts.get("refined", 0) or 0)
    draft = int(node_counts.get("draft", 0) or 0)
    verified = int(node_counts.get("verified", 0) or 0)
    pending_count = int(proposal_counts.get("pending", 0) or 0)
    approved_count = int(proposal_counts.get("approved_db_only", 0) or 0) + int(
        proposal_counts.get("approved_for_export", 0) or 0
    )

    dirty_nodes = int(knowledge_health.get("dirty_nodes", 0) or 0)
    stale_nodes = int(knowledge_health.get("stale_nodes", 0) or 0)
    conflicts = int(knowledge_health.get("conflict_count", 0) or 0)
    quarantined = int(knowledge_health.get("quarantined", 0) or 0)
    without_evidence = int(knowledge_health.get("nodes_without_evidence", 0) or 0)
    health_status = str(knowledge_health.get("status") or "ok")

    proposal_sync = lifecycle_overview.get("proposal_sync", {})
    if not isinstance(proposal_sync, dict):
        proposal_sync = {}
    sync_missing = int(proposal_sync.get("missing", 0) or 0)
    sync_coverage = float(proposal_sync.get("coverage", 100.0) or 0.0)

    attention_html, attention_total = _attention_rows(
        pending_proposals=pending_proposals,
        dirty_nodes=dirty_nodes,
        conflicts=conflicts,
        quarantined=quarantined,
        sync_missing=sync_missing,
        stale_nodes=stale_nodes,
    )

    pulse_penalty = min(
        60,
        pending_count * 4
        + dirty_nodes * 3
        + conflicts * 6
        + quarantined * 6
        + sync_missing * 3
        + min(stale_nodes, 10),
    )
    pulse_score = max(0, 100 - pulse_penalty)
    if attention_total:
        pulse_label = f"{attention_total} item{'s' if attention_total != 1 else ''} need a look"
        pulse_detail = "Real Brain health and proposal signals are driving this score."
    else:
        pulse_label = "Brain is steady"
        pulse_detail = "Proposal flow and maintained knowledge are quietly in order."

    line_points, area_path = _lifecycle_chart(node_counts)

    board_items = linuxdo_board.get("items") or []
    board_errors = linuxdo_board.get("fetch_errors") or []
    signal_count = len(board_items)
    board_updated = str(linuxdo_board.get("updated_at") or "")[:16].replace("T", " ") or "Not checked"
    signal_rows = []
    for item in board_items[:3]:
        title = str(item.get("title") or item.get("summary") or "Untitled signal")
        url = _signal_href(item.get("url") or item.get("link") or "/linuxdo")
        source = str(item.get("source") or "Linux.do")
        signal_rows.append(
            f'<a href="{_e(url, quote=True)}" target="_blank" rel="noopener"><b>{_e(title)}</b><small>{_e(source)}</small></a>'
        )
    if not signal_rows:
        empty_detail = "Signal fetch reported an error." if board_errors else "No curated signals are waiting."
        signal_rows.append(f'<a href="/linuxdo"><b>{_e(empty_detail)}</b><small>Open the live signal board</small></a>')
    signals_html = "".join(signal_rows)

    healthy_agents = 0
    pipeline_state = "Healthy" if health_status == "ok" else "Needs care"
    healthy_agents += health_status == "ok"
    proposal_state = "Clear" if pending_count == 0 else "Review"
    healthy_agents += pending_count == 0
    signal_state = "Ready" if signal_count and not board_errors else ("Delayed" if board_errors else "Quiet")
    healthy_agents += bool(signal_count and not board_errors)
    agent_health_pct = _pct(healthy_agents, 3)
    knowledge_pct = _pct(canonized + verified, total_nodes)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f6f2e9">
  <title>Homebase · Brain</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
:root{{--paper:#f6f2e9;--surface:#fffdf8;--glass:rgba(255,253,248,.72);--ink:#292824;--muted:#68635a;--line:#ded8ca;--soft:#ece6d9;--red:#c8584f;--red-bg:#fae9e5;--green:#4a8163;--green-bg:#e4f0e7;--amber:#b47734;--amber-bg:#f8ead6;--blue:#557da3;--blue-bg:#e7eef5;--purple:#77628d;--shadow:0 14px 40px rgba(80,60,40,.06),inset 0 1px rgba(255,255,255,.65);--sidebar:232px}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:radial-gradient(circle at 74% 8%,rgba(238,198,173,.38),transparent 30%),radial-gradient(circle at 28% 82%,rgba(188,208,197,.24),transparent 26%),var(--paper);background-attachment:fixed;color:var(--ink);font-family:'Manrope',system-ui,sans-serif;font-size:14px;line-height:1.55}}button,a{{font:inherit}}a{{color:inherit}}
.homebase-sidebar{{position:fixed;inset:0 auto 0 0;width:var(--sidebar);padding:28px 18px 20px;border-right:1px solid var(--line);background:rgba(239,233,220,.78);backdrop-filter:blur(22px) saturate(1.12);display:flex;flex-direction:column;z-index:20}}.brand{{display:flex;gap:11px;align-items:center;padding:0 8px 25px;color:var(--ink);text-decoration:none}}.brand-mark{{display:grid;place-items:center;width:38px;height:38px;border:1px solid #bbb19f;border-radius:12px;background:#fff9ed;font-size:21px}}.brand strong{{display:block;font-size:15px;letter-spacing:.02em}}.brand small{{display:block;margin-top:1px;color:#8b8375;font:500 8px/1.4 'DM Mono',monospace;letter-spacing:.08em}}.nav-list{{display:grid;gap:5px}}.nav-list a{{position:relative;display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:9px;color:#6d685f;text-decoration:none;font-weight:600;transition:.15s ease}}.nav-list a:hover{{background:rgba(255,255,255,.45);color:var(--ink)}}.nav-list a.active{{background:#fffaf0;color:var(--ink);box-shadow:inset 0 0 0 1px #d8cfbe}}.nav-icon{{width:19px;text-align:center;font:500 16px 'DM Mono',monospace}}.nav-count{{margin-left:auto;min-width:22px;padding:1px 6px;border-radius:99px;background:#df7866;color:white;font:500 10px 'DM Mono',monospace;text-align:center}}.nav-divider{{height:1px;background:var(--line);margin:12px 8px}}.nav-list.secondary a{{font-size:12px;padding-block:8px}}.sidebar-foot{{margin-top:auto;padding:16px 8px 0;border-top:1px solid #d9d1c2}}.tiny-status{{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:11px}}.tiny-status i{{width:7px;height:7px;border-radius:50%;background:#62a378;box-shadow:0 0 0 3px rgba(98,163,120,.12)}}.side-actions{{display:flex;gap:12px;margin-top:12px}}.side-actions a{{color:var(--muted);font-size:11px;text-decoration:none}}.side-actions a:hover{{color:var(--ink)}}
.homebase-shell{{min-height:100vh;margin-left:var(--sidebar)}}.topbar{{height:68px;padding:0 clamp(22px,4vw,58px);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;background:rgba(246,242,233,.68);backdrop-filter:blur(20px) saturate(1.15);position:sticky;top:0;z-index:10}}.date-line span{{font-weight:700}}.date-line small{{margin-left:12px;color:var(--muted)}}.top-actions{{display:flex;align-items:center;gap:12px}}.icon-button{{border:0;background:transparent;width:34px;height:34px;border-radius:50%;cursor:pointer;font-size:19px}}.icon-button:hover{{background:var(--soft)}}.icon-button.spinning{{animation:spin .65s ease}}.avatar{{display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:#403d37;color:white;font-weight:700}}.mobile-brand{{display:none;border:0;background:transparent}}.homebase-page{{max-width:1220px;margin:0 auto;padding:48px clamp(22px,4vw,58px) 80px;animation:appear .22s ease}}.page-heading{{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:32px}}.eyebrow{{margin:0 0 5px;color:#9a7556;font:500 10px/1.5 'DM Mono',monospace;letter-spacing:.14em}}.page-heading h1{{margin:0;font-size:clamp(27px,3vw,38px);line-height:1.25;letter-spacing:-.04em}}.page-heading h1 span{{color:#b59468;font-size:.72em}}.page-heading p:not(.eyebrow){{margin:9px 0 0;color:var(--muted)}}.soft-button{{padding:9px 14px;border:1px solid var(--line);border-radius:8px;background:var(--surface);cursor:pointer;font-weight:600;text-decoration:none}}.soft-button:hover{{border-color:#bfb5a4}}
.pulse-board{{display:grid;grid-template-columns:minmax(0,1fr) 330px;margin-bottom:22px;border:1px solid #dfc9b8;border-radius:18px;background:linear-gradient(135deg,rgba(255,249,239,.8),rgba(248,238,226,.72));backdrop-filter:blur(20px) saturate(1.08);box-shadow:0 18px 46px rgba(93,65,43,.08);overflow:hidden}}.pulse-hero{{display:grid;grid-template-columns:210px minmax(0,1fr);gap:25px;align-items:center;padding:24px 27px}}.pulse-kicker{{display:flex;align-items:center;gap:7px;color:#a07151;font:500 9px 'DM Mono',monospace;letter-spacing:.14em}}.pulse-kicker i{{width:7px;height:7px;border-radius:50%;background:#62a378;box-shadow:0 0 0 4px rgba(98,163,120,.12)}}.pulse-score{{display:flex;align-items:center;gap:10px;margin:8px 0 2px}}.pulse-score strong{{font:700 55px/1 'Manrope',sans-serif;letter-spacing:-.07em}}.pulse-score span{{color:var(--muted);font-size:10px;line-height:1.45}}.pulse-copy p{{max-width:210px;margin:8px 0 0;color:var(--muted);font-size:11px}}.pulse-chart{{position:relative;min-width:0;padding:5px 0 0 23px}}.pulse-chart svg{{display:block;width:100%;overflow:visible}}.chart-grid{{fill:none;stroke:#ddcfc0;stroke-width:1;stroke-dasharray:4 6}}.pulse-chart .area{{fill:url(#pulseFill)}}.pulse-chart .line{{fill:none;stroke:#d77f61;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}}.pulse-chart circle{{fill:#fff;stroke:#d77f61;stroke-width:4}}.chart-scale{{position:absolute;inset:6px auto 21px 0;display:flex;flex-direction:column;justify-content:space-between;color:#a49788;font:500 8px 'DM Mono',monospace}}.chart-days{{display:flex;justify-content:space-between;padding:3px 1px 0;color:#a49788;font:500 7px 'DM Mono',monospace;letter-spacing:.04em}}.chart-label{{margin:0 0 4px 23px;color:#9a7556;font:500 8px 'DM Mono',monospace;letter-spacing:.1em}}.pulse-metrics{{display:grid;border-left:1px solid #dfc9b8;background:rgba(255,253,248,.6)}}.pulse-metrics article{{display:grid;grid-template-columns:72px 1fr;gap:15px;align-items:center;padding:17px 20px}}.pulse-metrics article+article{{border-top:1px solid #dfc9b8}}.pulse-metrics article>div:last-child>*{{display:block}}.pulse-metrics small{{color:#a07151;font:500 8px 'DM Mono',monospace;letter-spacing:.08em}}.pulse-metrics b{{margin:3px 0;font-size:12px}}.pulse-metrics span{{color:var(--muted);font-size:10px}}.metric-ring,.tiny-donut{{display:grid;place-items:center;border-radius:50%;background:conic-gradient(#63a178 0 var(--value),#eadfd3 var(--value))}}.metric-ring{{width:58px;height:58px}}.metric-ring:before,.tiny-donut:before{{content:'';grid-area:1/1;border-radius:50%;background:var(--surface)}}.metric-ring:before{{width:44px;height:44px}}.metric-ring b,.tiny-donut b{{grid-area:1/1;z-index:1;font:500 10px 'DM Mono',monospace}}
.glass-panel{{background:var(--glass);backdrop-filter:blur(18px) saturate(1.08);box-shadow:var(--shadow)}}.attention-zone{{border:1px solid #e4c8bf;border-radius:14px;overflow:hidden;margin-bottom:22px}}.section-title,.panel-heading{{display:flex;align-items:center;justify-content:space-between}}.section-title{{padding:15px 18px;background:rgba(251,239,235,.78);border-bottom:1px solid #ead4cd}}.section-title>div,.panel-heading>div{{display:flex;align-items:center;gap:9px}}.section-title h2,.panel-heading h2{{font-size:15px;margin:0}}.section-title small{{color:#a65c52}}.section-symbol{{display:grid;place-items:center;width:23px;height:23px;border-radius:7px;font:600 12px 'DM Mono',monospace}}.section-symbol.danger{{background:#d56c5c;color:white}}.section-symbol.okay{{background:var(--green-bg);color:var(--green)}}.section-symbol.project{{background:#eee9f3;color:var(--purple)}}.section-symbol.intel{{background:var(--amber-bg);color:var(--amber)}}.attention-list{{padding:0 18px}}.attention-row{{display:grid;grid-template-columns:38px minmax(0,1fr) auto 62px;gap:12px;align-items:center;padding:16px 0;border-bottom:1px solid #eee9de;text-decoration:none}}.attention-row:last-child{{border-bottom:0}}.attention-row:hover .item-copy b{{color:#a85046}}.item-icon{{display:grid;place-items:center;width:36px;height:36px;border-radius:10px;font:600 16px 'DM Mono',monospace}}.agent-icon{{color:var(--purple);background:#eee9f3}}.server-icon{{color:var(--amber);background:var(--amber-bg)}}.clear-icon{{color:var(--green);background:var(--green-bg)}}.item-copy{{min-width:0}}.item-copy b,.item-copy small{{display:block;overflow:hidden;text-overflow:ellipsis}}.item-copy b{{font-size:13px;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;line-clamp:2}}.item-copy small{{margin-top:2px;color:var(--muted);font-size:12px;white-space:nowrap}}.attention-row code{{color:#999287;font:500 9px 'DM Mono',monospace;max-width:120px;overflow:hidden;text-overflow:ellipsis}}.attention-row em{{font-style:normal;padding:6px 10px;border:1px solid var(--line);border-radius:7px;background:white;font-size:11px;text-align:center}}
.overview-grid{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}.simple-panel{{border:1px solid var(--line);border-radius:14px;padding:18px}}.panel-heading a{{color:var(--muted);font-size:11px;text-decoration:none}}.panel-heading a:hover{{color:var(--ink)}}.panel-viz-row{{display:flex;align-items:center;justify-content:space-between}}.panel-summary{{margin:20px 0 12px;display:flex;gap:8px;align-items:baseline}}.panel-summary strong{{font-size:18px}}.panel-summary span{{color:var(--muted);font-size:11px}}.tiny-donut{{width:44px;height:44px;margin-top:9px}}.tiny-donut:before{{width:32px;height:32px}}.mini-list{{display:grid}}.mini-list>a,.mini-list>div{{display:grid;grid-template-columns:9px 96px minmax(0,1fr) auto;align-items:center;gap:8px;min-height:37px;border-top:1px solid #eee9df;text-decoration:none}}.mini-list b{{font-size:12px}}.mini-list small{{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.mini-list em{{font-style:normal;font-size:10px;color:var(--muted)}}.dot{{width:7px;height:7px;border-radius:50%}}.dot.green{{background:#63a178}}.dot.amber{{background:#da984b}}.dot.red{{background:#cf6258}}.dot.blue{{background:#628fb6}}.projects-panel,.signals-panel{{min-height:238px}}.project-strip{{display:grid;margin-top:12px}}.project-strip>a{{display:grid;grid-template-columns:35px minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px 0;border-top:1px solid #eee9df;text-decoration:none}}.project-logo{{display:grid;place-items:center;width:31px;height:31px;border-radius:9px;font-weight:800}}.project-logo.lavender{{background:#eee9f3;color:var(--purple)}}.project-logo.peach{{background:#f7e7dc;color:#a86648}}.project-logo.mint{{background:#e3efe8;color:var(--green)}}.project-logo.blue{{background:var(--blue-bg);color:var(--blue)}}.project-strip p{{margin:0}}.project-strip b,.project-strip small{{display:block}}.project-strip small{{color:var(--muted);font-size:10px}}.tag{{padding:3px 7px;border-radius:99px;font-style:normal;font-size:9px}}.tag.healthy{{background:var(--green-bg);color:var(--green)}}.tag.attention{{background:var(--amber-bg);color:var(--amber)}}.signal-totals{{display:flex;gap:22px;margin:20px 0 13px}}.signal-totals div{{display:grid}}.signal-totals strong{{font:600 22px 'DM Mono',monospace}}.signal-totals span{{color:var(--muted);font-size:10px}}.signal-list{{display:grid}}.signal-list a{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;padding:10px 0;border-top:1px solid #eee9df;text-decoration:none}}.signal-list b{{font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.signal-list small{{color:var(--muted);font-size:9px}}
.mobile-nav{{display:none}}.homebase-toast{{position:fixed;left:50%;bottom:28px;z-index:60;padding:9px 15px;border-radius:8px;background:#35332e;color:white;font-size:11px;opacity:0;transform:translate(-50%,20px);pointer-events:none;transition:.2s}}.homebase-toast.show{{opacity:1;transform:translate(-50%,0)}}
@keyframes appear{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:none}}}}@keyframes spin{{to{{transform:rotate(360deg)}}}}
@media(max-width:900px){{.pulse-board{{grid-template-columns:1fr}}.pulse-metrics{{grid-template-columns:1fr 1fr;border-left:0;border-top:1px solid #dfc9b8}}.pulse-metrics article+article{{border-top:0;border-left:1px solid #dfc9b8}}.overview-grid{{grid-template-columns:1fr}}}}
@media(max-width:700px){{:root{{--sidebar:0px}}.homebase-sidebar{{display:none}}.homebase-shell{{margin-left:0;padding-bottom:66px}}.topbar{{height:56px;padding:0 16px}}.mobile-brand{{display:block}}.date-line{{display:none}}.homebase-page{{padding:28px 15px 88px}}.page-heading{{display:block;margin-bottom:23px}}.page-heading .soft-button{{display:none}}.page-heading h1{{font-size:27px}}.pulse-board{{border-radius:14px}}.pulse-hero{{grid-template-columns:118px minmax(0,1fr);gap:12px;padding:17px 15px}}.pulse-score strong{{font-size:42px}}.pulse-copy p{{display:none}}.pulse-chart{{padding-left:18px}}.chart-days{{font-size:5px}}.pulse-metrics article{{grid-template-columns:43px 1fr;gap:9px;padding:11px 10px}}.metric-ring{{width:40px;height:40px}}.metric-ring:before{{width:30px;height:30px}}.attention-list{{padding:0 13px}}.attention-row{{grid-template-columns:35px minmax(0,1fr) auto;gap:9px;padding:14px 0}}.attention-row code{{display:none}}.attention-row em{{border:0;background:transparent;padding:5px;color:#a15349}}.simple-panel{{padding:15px;border-radius:12px}}.mini-list>a,.mini-list>div{{grid-template-columns:8px 92px minmax(0,1fr)}}.mini-list em{{display:none}}.mobile-nav{{position:fixed;left:0;right:0;bottom:0;z-index:30;height:62px;padding:6px 7px calc(6px + env(safe-area-inset-bottom));border-top:1px solid var(--line);background:rgba(246,242,233,.9);backdrop-filter:blur(18px);display:grid;grid-template-columns:repeat(4,1fr)}}.mobile-nav a{{display:grid;place-items:center;color:var(--muted);text-decoration:none;font-size:9px}}.mobile-nav a span{{font:500 17px 'DM Mono',monospace}}.mobile-nav a.active{{color:var(--ink)}}}}
  </style>
</head>
<body>
  <aside class="homebase-sidebar" aria-label="Main navigation">
    <a class="brand" href="/" aria-label="Homebase overview"><span class="brand-mark">⌂</span><span><strong>Homebase</strong><small>BRAIN CONTROL ROOM</small></span></a>
    <nav class="nav-list">
      <a class="active" href="/"><span class="nav-icon">⌂</span><span>Overview</span></a>
      <a href="/fleet"><span class="nav-icon">▰</span><span>Servers &amp; Agents</span></a>
      <a href="/hub"><span class="nav-icon">◇</span><span>Projects</span></a>
      <a href="/linuxdo"><span class="nav-icon">◉</span><span>Signals</span><b class="nav-count">{signal_count}</b></a>
      <a href="/knowledge"><span class="nav-icon">▤</span><span>Library</span></a>
    </nav>
    <div class="nav-divider"></div>
    <nav class="nav-list secondary" aria-label="Brain business routes">
      <a href="/proposals"><span class="nav-icon">🧠</span><span>Brain Lifecycle</span></a>
      <a href="/control"><span class="nav-icon">◫</span><span>Control</span></a>
      <a href="/gallery"><span class="nav-icon">▧</span><span>Gallery</span></a>
    </nav>
    <div class="sidebar-foot"><div class="tiny-status"><i></i><span>Live Brain data</span></div><div class="side-actions"><a href="/settings">Settings</a><a href="/logout">Log out</a></div></div>
  </aside>

  <main class="homebase-shell">
    <header class="topbar"><button class="mobile-brand" type="button">⌂ <b>Homebase</b></button><div class="date-line"><span id="todayText">Today</span><small>Rendered {_e(now_utc)}</small></div><div class="top-actions"><button class="icon-button" id="refreshButton" aria-label="Refresh live data" title="Refresh live data">↻</button><div class="avatar" title="Brain owner">B</div></div></header>

    <section class="homebase-page">
      <div class="page-heading"><div><p class="eyebrow">DAILY CHECK</p><h1 id="homeGreeting">Welcome home <span>˙ᵕ˙</span></h1><p>You only need to check what is unusual and what needs a decision.</p></div><a class="soft-button" href="/linuxdo">View today's signals <span>→</span></a></div>

      <section class="pulse-board" id="home-system-pulse" aria-label="System Pulse">
        <div class="pulse-hero"><div class="pulse-copy"><div class="pulse-kicker"><i></i> SYSTEM PULSE</div><div class="pulse-score"><strong>{pulse_score}</strong><span>/ 100<br>{_e(pulse_label)}</span></div><p>{_e(pulse_detail)}</p></div><div class="pulse-chart" title="Live Brain knowledge lifecycle"><p class="chart-label">KNOWLEDGE LIFECYCLE</p><div class="chart-scale"><span>{max(node_counts.values()) if node_counts else 0}</span><span>0</span></div><svg viewBox="0 0 520 150" role="img" aria-label="Live Brain knowledge nodes by lifecycle stage"><defs><linearGradient id="pulseFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#efb391" stop-opacity=".42"/><stop offset="1" stop-color="#efb391" stop-opacity="0"/></linearGradient></defs><path class="chart-grid" d="M0 25H520M0 75H520M0 125H520"/><path class="area" d="{area_path}"/><polyline class="line" points="{line_points}"/></svg><div class="chart-days"><span>DRAFT</span><span>REFINED</span><span>VERIFIED</span><span>CANON</span><span>ARCHIVE</span></div></div></div>
        <div class="pulse-metrics"><article><div class="metric-ring" style="--value:{knowledge_pct}%"><b>{knowledge_pct}%</b></div><div><small>KNOWLEDGE HEALTH</small><b>{total_nodes} live nodes</b><span>{canonized} canonized · {without_evidence} without evidence</span></div></article><article><div class="metric-ring" style="--value:{round(sync_coverage)}%"><b>{round(sync_coverage)}%</b></div><div><small>PROPOSAL FLOW</small><b>{pending_count} waiting</b><span>{approved_count} approved · {sync_missing} unlinked</span></div></article></div>
      </section>

      <section class="attention-zone glass-panel" id="home-attention" aria-labelledby="attention-title"><div class="section-title"><div><span class="section-symbol danger">!</span><h2 id="attention-title">Needs your attention</h2></div><small>{attention_total} item{'s' if attention_total != 1 else ''}</small></div><div class="attention-list">{attention_html}</div></section>

      <div class="overview-grid">
        <section class="simple-panel glass-panel" id="home-servers"><div class="panel-heading"><div><span class="section-symbol okay">●</span><h2>Servers</h2></div><a href="/fleet">Open fleet →</a></div><div class="panel-viz-row"><p class="panel-summary"><strong id="serverSummary">Checking live fleet</strong><span id="serverDetail">No static server status</span></p><div class="tiny-donut" id="serverDonut" style="--value:0%"><b id="serverPercent">—</b></div></div><div class="mini-list" id="serverList"><div><span class="dot blue"></span><b>Live probe</b><small>Loading /api/vps/fleet</small><em>Checking</em></div></div></section>

        <section class="simple-panel glass-panel" id="home-agents"><div class="panel-heading"><div><span class="section-symbol okay">✦</span><h2>Agents</h2></div><a href="/control">Open control →</a></div><div class="panel-viz-row"><p class="panel-summary"><strong>{healthy_agents} of 3 steady</strong><span>derived from live Brain data</span></p><div class="tiny-donut" style="--value:{agent_health_pct}%"><b>{agent_health_pct}%</b></div></div><div class="mini-list"><a href="/knowledge"><span class="dot {'green' if health_status == 'ok' else 'amber'}"></span><b>Brain Curator</b><small>{total_nodes} nodes · {dirty_nodes} dirty</small><em>{_e(pipeline_state)}</em></a><a href="/proposals?tab=review"><span class="dot {'green' if pending_count == 0 else 'amber'}"></span><b>Proposal Steward</b><small>{pending_count} waiting · {approved_count} approved</small><em>{proposal_state}</em></a><a href="/linuxdo"><span class="dot {'green' if signal_count and not board_errors else 'amber'}"></span><b>Signal Scout</b><small>{signal_count} curated · {_e(board_updated)}</small><em>{_e(signal_state)}</em></a></div></section>

        <section class="simple-panel glass-panel projects-panel" id="home-projects"><div class="panel-heading"><div><span class="section-symbol project">◇</span><h2>Projects</h2></div><a href="/hub">All modules →</a></div><div class="project-strip"><a href="/proposals"><span class="project-logo lavender">B</span><p><b>Brain</b><small>Proposal lifecycle and evidence</small></p><em class="tag {'attention' if pending_count else 'healthy'}">{pending_count} pending</em></a><a href="/knowledge"><span class="project-logo mint">K</span><p><b>Knowledge</b><small>{canonized} canonized · {refined} refined · {draft} draft</small></p><em class="tag healthy">{total_nodes} nodes</em></a><a href="/gallery"><span class="project-logo peach">V</span><p><b>viz-skills</b><small>Scientific visualization gallery</small></p><em class="tag healthy">{chart_count} templates</em></a><a href="/linuxdo"><span class="project-logo blue">S</span><p><b>Daily Signals</b><small>Curated live source board</small></p><em class="tag {'healthy' if not board_errors else 'attention'}">{signal_count} ready</em></a></div></section>

        <section class="simple-panel glass-panel signals-panel" id="home-signals"><div class="panel-heading"><div><span class="section-symbol intel">◉</span><h2>Today's Signals</h2></div><a href="/linuxdo">View all {signal_count} →</a></div><div class="signal-totals"><div><strong>{signal_count}</strong><span>CURATED</span></div><div><strong>{len(board_errors)}</strong><span>FETCH ERRORS</span></div><div><strong>{_e(board_updated[-5:] if board_updated != 'Not checked' else '—')}</strong><span>UPDATED</span></div></div><div class="signal-list">{signals_html}</div></section>
      </div>
    </section>
  </main>

  <nav class="mobile-nav" aria-label="Mobile navigation"><a class="active" href="/"><span>⌂</span>Overview</a><a href="/fleet"><span>▰</span>Resources</a><a href="/linuxdo"><span>◉</span>Signals</a><a href="/hub"><span>◇</span>Projects</a></nav>
  <div class="homebase-toast" id="homebaseToast" role="status"></div>
  <script>
(() => {{
  const toast = document.getElementById('homebaseToast');
  let toastTimer;
  function showToast(message) {{ toast.textContent = message; toast.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('show'), 1800); }}
  const date = new Date();
  const weekdays = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  document.getElementById('todayText').textContent = `${{weekdays[date.getDay()]}} · ${{date.toLocaleDateString('en-US', {{month:'long',day:'numeric'}})}}`;
  const hour = date.getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const name = localStorage.getItem('hermes_display_name') || '';
  document.getElementById('homeGreeting').innerHTML = `${{greeting}}${{name ? ', ' + name.replace(/[<>&"']/g, '') : ''}} <span>˙ᵕ˙</span>`;

  function escapeHtml(value) {{ const el = document.createElement('span'); el.textContent = String(value ?? ''); return el.innerHTML; }}
  async function refreshFleet() {{
    const response = await fetch('/api/vps/fleet', {{credentials:'same-origin',cache:'no-store'}});
    if (!response.ok) throw new Error(`Fleet HTTP ${{response.status}}`);
    const data = await response.json();
    const items = Array.isArray(data.items) ? data.items : [];
    const total = Number(data.summary?.total ?? items.length);
    const online = Number(data.summary?.online ?? items.filter(item => item.ok).length);
    const pct = total ? Math.round(online / total * 100) : 0;
    document.getElementById('serverSummary').textContent = `${{online}} of ${{total}} online`;
    document.getElementById('serverDetail').textContent = `${{Math.max(total-online,0)}} need attention · live probe`;
    document.getElementById('serverPercent').textContent = `${{pct}}%`;
    document.getElementById('serverDonut').style.setProperty('--value', `${{pct}}%`);
    const list = document.getElementById('serverList');
    list.innerHTML = items.slice(0,3).map(item => `<a href="/fleet"><span class="dot ${{item.ok?'green':'red'}}"></span><b>${{escapeHtml(item.name||item.hostname||'Server')}}</b><small>${{escapeHtml(item.region||item.role||'Live fleet')}}</small><em>${{item.ok ? (Number(item.disk_used_percent||0)+'% disk') : 'Offline'}}</em></a>`).join('') || '<div><span class="dot amber"></span><b>No fleet rows</b><small>The live API returned no machines.</small><em>Empty</em></div>';
    return data;
  }}
  const refresh = document.getElementById('refreshButton');
  async function runRefresh(notify) {{
    refresh.classList.add('spinning');
    try {{ await refreshFleet(); if (notify) showToast('Live fleet refreshed'); }}
    catch (error) {{ document.getElementById('serverSummary').textContent='Fleet unavailable'; document.getElementById('serverDetail').textContent=error.message; if (notify) showToast('Fleet check failed'); }}
    finally {{ refresh.classList.remove('spinning'); }}
  }}
  refresh.addEventListener('click', () => runRefresh(true));
  runRefresh(false);
}})();
  </script>
</body>
</html>'''
