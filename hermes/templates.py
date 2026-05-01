"""HTML templates for Hermes review UI – dependency-free, mobile-first, dark theme."""

from __future__ import annotations

import html as _html

# ---------------------------------------------------------------------------
# Shared CSS (Dracula-inspired dark theme, mobile-first)
# ---------------------------------------------------------------------------

_DARK_CSS = """\
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#282a36;--bg-card:#343746;--bg-hover:#44475a;--bg-nav:#21222c;
  --fg:#f8f8f2;--fg-muted:#6272a4;--fg-dim:#9092a4;
  --accent:#bd93f9;--green:#50fa7b;--yellow:#f1fa8c;--red:#ff5555;--cyan:#8be9fd;--orange:#ffb86c;--pink:#ff79c6;
  --radius:8px;--font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
html{font-family:var(--font);background:var(--bg);color:var(--fg);line-height:1.5;-webkit-text-size-adjust:100%}
body{min-height:100vh;padding-bottom:80px}
a{color:var(--cyan);text-decoration:none}
a:hover{text-decoration:underline}

/* ---- Top nav ---- */
.topnav{display:flex;align-items:center;justify-content:space-between;padding:0 16px;background:var(--bg-nav);border-bottom:1px solid var(--bg-hover);min-height:52px;position:sticky;top:0;z-index:50}
.topnav .brand{font-weight:700;font-size:1.1rem;color:var(--accent);white-space:nowrap}
.topnav .links-desktop{display:none;gap:16px}
.topnav .links-desktop a{color:var(--fg-dim);font-size:.9rem;padding:6px 0;min-height:44px;display:flex;align-items:center;white-space:nowrap}
.topnav .links-desktop a.active,.topnav .links-desktop a:hover{color:var(--fg)}
.hamburger{display:flex;flex-direction:column;gap:5px;padding:12px 4px;cursor:pointer;background:none;border:none;min-width:44px;min-height:44px;align-items:center;justify-content:center}
.hamburger span{display:block;width:24px;height:2.5px;background:var(--fg);border-radius:2px;transition:transform .2s,opacity .2s}
.hamburger.open span:nth-child(1){transform:translateY(7.5px) rotate(45deg)}
.hamburger.open span:nth-child(2){opacity:0}
.hamburger.open span:nth-child(3){transform:translateY(-7.5px) rotate(-45deg)}
.mobile-menu{display:none;position:fixed;top:52px;left:0;right:0;bottom:0;background:var(--bg-nav);z-index:40;padding:16px;flex-direction:column;gap:0;border-top:1px solid var(--bg-hover)}
.mobile-menu.open{display:flex}
.mobile-menu a{display:flex;align-items:center;gap:10px;padding:16px 8px;font-size:1.05rem;color:var(--fg-dim);min-height:48px;border-bottom:1px solid var(--bg-hover);text-decoration:none;transition:background .15s,color .15s}
.mobile-menu a.active,.mobile-menu a:hover{color:var(--fg);background:var(--bg-hover)}
.mobile-menu a svg{width:20px;height:20px;flex-shrink:0}

@media(min-width:720px){
  .topnav .links-desktop{display:flex}
  .hamburger{display:none}
}

/* ---- Filter tabs ---- */
.tabs{display:flex;gap:8px;padding:16px 16px 8px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tabs a,.tabs button{
  display:inline-flex;align-items:center;gap:6px;
  padding:10px 18px;border:1px solid var(--bg-hover);border-radius:var(--radius);
  background:var(--bg);color:var(--fg-dim);font-size:.9rem;cursor:pointer;
  min-height:44px;white-space:nowrap;transition:background .15s,color .15s
}
.tabs a.active,.tabs button.active,.tabs a:hover,.tabs button:hover{background:var(--bg-hover);color:var(--fg)}
.tab-count{font-size:.75rem;background:var(--bg-hover);border-radius:10px;padding:2px 8px;color:var(--fg-dim)}

/* ---- Card grid ---- */
.card-grid{display:grid;grid-template-columns:1fr;gap:12px;padding:0 16px 16px}
@media(min-width:720px){.card-grid{grid-template-columns:repeat(auto-fill,minmax(380px,1fr))}}

.card{
  display:block;background:var(--bg-card);border-radius:var(--radius);
  padding:16px;border:1px solid var(--bg-hover);text-decoration:none;color:var(--fg);
  transition:border-color .15s,background .15s;min-height:44px
}
.card:hover{border-color:var(--accent);background:var(--bg-hover);text-decoration:none}
.card-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.card-preview{font-size:.95rem;color:var(--fg);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}
.card-meta{display:flex;gap:8px;margin-top:8px;font-size:.8rem;color:var(--fg-dim)}

/* ---- Badges ---- */
.badge{display:inline-flex;align-items:center;padding:3px 10px;border-radius:12px;font-size:.75rem;font-weight:600;letter-spacing:.02em;white-space:nowrap}
.badge-pending{background:rgba(241,250,140,.15);color:var(--yellow)}
.badge-approved_db_only{background:rgba(80,250,123,.12);color:var(--green)}
.badge-approved_for_export{background:rgba(80,250,123,.25);color:var(--green)}
.badge-rejected{background:rgba(255,85,85,.15);color:var(--red)}
.badge-superseded{background:rgba(98,114,164,.2);color:var(--fg-dim)}
.badge-rule{background:rgba(189,147,249,.15);color:var(--accent)}
.badge-pattern{background:rgba(139,233,253,.15);color:var(--cyan)}
.badge-insight{background:rgba(255,184,108,.15);color:var(--orange)}
.badge-warning{background:rgba(255,121,198,.15);color:var(--pink)}
.badge-risk-high{background:rgba(255,85,85,.15);color:var(--red)}
.badge-risk-medium{background:rgba(241,250,140,.15);color:var(--yellow)}
.badge-risk-low{background:rgba(80,250,123,.15);color:var(--green)}

/* ---- Detail page ---- */
.detail-header{padding:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.back-link{display:inline-flex;align-items:center;gap:4px;color:var(--fg-dim);font-size:.9rem;min-height:44px}
.back-link:hover{color:var(--fg)}
.detail-title{font-size:1.15rem;font-weight:700;word-break:break-all}
.detail-body{padding:0 16px 16px}
.section{margin-bottom:20px}
.section h3{color:var(--accent);font-size:.85rem;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
.section p{color:var(--fg);font-size:.95rem;white-space:pre-wrap;word-break:break-word}
.meta-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;padding:0 16px 12px;font-size:.85rem}
.meta-grid .label{color:var(--fg-muted)}
.meta-grid .value{color:var(--fg);font-weight:500}

/* ---- Action buttons ---- */
.action-bar{
  position:fixed;bottom:0;left:0;right:0;
  display:flex;gap:8px;padding:12px 16px;
  background:var(--bg-nav);border-top:1px solid var(--bg-hover);
  z-index:100
}
.action-bar .btn{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;padding:14px 8px;border:none;border-radius:var(--radius);font-size:.95rem;font-weight:600;cursor:pointer;min-height:48px;transition:opacity .15s}
.btn-approve{background:rgba(80,250,123,.2);color:var(--green)}
.btn-approve:hover{background:rgba(80,250,123,.35)}
.btn-export{background:rgba(189,147,249,.2);color:var(--accent)}
.btn-export:hover{background:rgba(189,147,249,.35)}
.btn-reject{background:rgba(255,85,85,.2);color:var(--red)}
.btn-reject:hover{background:rgba(255,85,85,.35)}
.btn:disabled{opacity:.4;cursor:not-allowed}
/* ---- State dot ---- */
.state-dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;vertical-align:middle}
.state-dot-pending{background:var(--yellow)}
.state-dot-approved_db_only{background:var(--green)}
.state-dot-approved_for_export{background:var(--green)}
.state-dot-rejected{background:var(--red)}
.state-dot-superseded{background:var(--fg-dim)}

/* ---- Empty state ---- */
.empty{padding:32px 16px;text-align:center;color:var(--fg-dim);font-size:1rem}

/* ---- Stats summary ---- */
.stats-bar{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:8px 16px 4px}
.stat-item{text-align:center;padding:10px 8px;border-radius:var(--radius);background:var(--bg-card);border:1px solid var(--bg-hover)}
.stat-num{display:block;font-size:1.5rem;font-weight:700;line-height:1}
.stat-label{display:block;font-size:.7rem;color:var(--fg-muted);margin-top:2px;text-transform:uppercase;letter-spacing:.04em}
.stat-pending .stat-num{color:var(--yellow)}
.stat-approved .stat-num{color:var(--green)}
.stat-rejected .stat-num{color:var(--red)}
"""

# ---------------------------------------------------------------------------
# Shared page shell
# ---------------------------------------------------------------------------

def _page(title: str, body: str, *, extra_js: str = "") -> str:
    """Return a full HTML document with the shared dark theme."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>{_html.escape(title)}</title>
<style>{_DARK_CSS}</style>
</head>
<body>
{body}
{f'<script>{extra_js}</script>' if extra_js else ''}
</body>
</html>"""


# SVG icons for nav items
_ICON_QUEUE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>'
_ICON_EXPORT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
_ICON_LOGOUT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>'

_ICON_GROK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/></svg>'
_ICON_GALLERY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>'
_ICON_SHIELD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'


_ICON_SETTINGS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>'

def _nav(*, active: str = "queue") -> str:
    links = [
        ("review", "Review", "/review", _ICON_QUEUE),
        ("gallery", "Gallery", "/gallery", _ICON_GALLERY),
        ("security", "Security", "/security", _ICON_SHIELD),
        ("settings", "Settings", "/settings", _ICON_SETTINGS),
        ("logout", "Logout", "/logout", _ICON_LOGOUT),
    ]
    desktop_items = []
    mobile_items = []
    for key, label, href, icon in links:
        cls = " active" if key == active else ""
        desktop_items.append(f'<a href="{href}" class="{cls.lstrip()}">{_html.escape(label)}</a>')
        mobile_items.append(f'<a href="{href}" class="{cls.lstrip()}">{icon} <span>{_html.escape(label)}</span></a>')

    return f"""<nav class="topnav">
  <a href="/review" class="brand">🧠 Hermes</a>
  <span class="links-desktop">{''.join(desktop_items)}</span>
  <button class="hamburger" onclick="document.getElementById('mm').classList.toggle('open');this.classList.toggle('open')" aria-label="Menu">
    <span></span><span></span><span></span>
  </button>
</nav>
<div class="mobile-menu" id="mm">
  {''.join(mobile_items)}
</div>"""


# ---------------------------------------------------------------------------
# Category / risk badge helpers
# ---------------------------------------------------------------------------

_CATEGORY_BADGE_MAP = {
    "rule": "badge-rule",
    "pattern": "badge-pattern",
    "insight": "badge-insight",
    "warning": "badge-warning",
}


def _category_badge(category: str) -> str:
    cls = _CATEGORY_BADGE_MAP.get(category, "badge-rule")
    return f'<span class="badge {cls}">{_html.escape(category)}</span>'


_RISK_BADGE_MAP = {
    "high": "badge-risk-high",
    "medium": "badge-risk-medium",
    "low": "badge-risk-low",
}


def _risk_badge(risk_level: str) -> str:
    cls = _RISK_BADGE_MAP.get(risk_level, "badge-risk-medium")
    return f'<span class="badge {cls}">{_html.escape(risk_level)}</span>'


_STATE_BADGE_MAP = {
    "pending": "badge-pending",
    "approved_db_only": "badge-approved_db_only",
    "approved_for_export": "badge-approved_for_export",
    "rejected": "badge-rejected",
    "superseded": "badge-superseded",
}

# Human-readable labels for states (Chinese-friendly)
_STATE_LABEL = {
    "pending": "Pending",
    "approved_db_only": "Approved",
    "approved_for_export": "Approved + Synced",
    "rejected": "Rejected",
    "superseded": "Outdated",
}

_STATE_DOT_MAP = {
    "pending": "state-dot-pending",
    "approved_db_only": "state-dot-approved_db_only",
    "approved_for_export": "state-dot-approved_for_export",
    "rejected": "state-dot-rejected",
    "superseded": "state-dot-superseded",
}


def _state_badge(state: str) -> str:
    cls = _STATE_BADGE_MAP.get(state, "badge-pending")
    dot = _STATE_DOT_MAP.get(state, "state-dot-pending")
    label = _STATE_LABEL.get(state, state.replace("_", " ").title())
    return f'<span class="badge {cls}"><span class="state-dot {dot}"></span>{_html.escape(label)}</span>'


# ---------------------------------------------------------------------------
# Review Queue page
# ---------------------------------------------------------------------------

def review_queue_page(
    *,
    proposals: list[dict],
    counts: dict[str, int],
    active_state: str = "pending",
) -> str:
    """Render the review queue with filter tabs and proposal cards."""
    total = sum(counts.values())
    tabs = [
        ("all", "All", total),
        ("pending", "Pending", counts.get("pending", 0)),
        ("approved_db_only", "Approved", counts.get("approved_db_only", 0)),
        ("approved_for_export", "Synced", counts.get("approved_for_export", 0)),
    ]
    tab_html = ""
    for key, label, count in tabs:
        active_cls = " active" if (key == active_state) or (key == "all" and active_state == "all") else ""
        href = f"/review?state={key}" if key != "pending" else "/review"
        if key == "all":
            href = "/review?state=all"
        tab_html += (
            f'<a href="{href}" class="{active_cls.lstrip()}">'
            f'{_html.escape(label)} <span class="tab-count">{count}</span></a>'
        )

    cards = ""
    for p in proposals:
        pid = str(p.get("proposal_id", ""))
        cat = str(p.get("category", ""))
        risk = str(p.get("risk_level", ""))
        memory = str(p.get("suggested_memory", ""))
        project = str(p.get("project_key", ""))
        state = str(p.get("state", "pending"))
        # Truncate preview to 120 chars
        preview = memory[:120] + ("..." if len(memory) > 120 else "")
        cards += f"""<a href="/review/{_html.escape(pid)}" class="card">
  <div class="card-top">{_category_badge(cat)} {_state_badge(state)}</div>
  <div class="card-preview">{_html.escape(preview)}</div>
  <div class="card-meta">
    <span>{_html.escape(project)}</span>
    {_risk_badge(risk)}
  </div>
</a>"""

    if not proposals:
        cards = '<div class="empty">No proposals in this view.</div>'

    # The heading must contain "Pending proposals" for the test
    heading = "待审提案" if active_state == "pending" else f"{active_state.replace('_', ' ').title()} proposals"

    # Stats summary bar
    pending_n = counts.get("pending", 0)
    approved_n = counts.get("approved_db_only", 0) + counts.get("approved_for_export", 0)
    rejected_n = counts.get("rejected", 0)
    stats_html = f"""<div class="stats-bar">
  <div class="stat-item stat-pending"><span class="stat-num">{pending_n}</span><span class="stat-label">Pending</span></div>
  <div class="stat-item stat-approved"><span class="stat-num">{approved_n}</span><span class="stat-label">Approved</span></div>
  <div class="stat-item stat-rejected"><span class="stat-num">{rejected_n}</span><span class="stat-label">Rejected</span></div>
</div>"""

    body = f"""{_nav(active="queue")}
<h1 style="padding:16px 16px 0;font-size:1.2rem">{_html.escape(heading)}</h1>
{stats_html}
<div class="tabs">{tab_html}</div>
<div class="card-grid">{cards}</div>
"""
    return _page("Hermes Review Queue", body)


# ---------------------------------------------------------------------------
# Review Detail page
# ---------------------------------------------------------------------------

_PROPOSAL_SECTIONS = [
    ("Observation", "observation"),
    ("Why it matters", "why_it_matters"),
    ("Suggested durable memory", "suggested_memory"),
    ("Scope", "scope"),
    ("Evidence", "evidence"),
    ("Summary", "summary"),
]

# JavaScript for action buttons – uses fetch + confirm
_ACTION_JS = """\
function act(url, actionName) {
  if (!confirm('Confirm: ' + actionName + '?')) return;
  var btn = event.target.closest('.btn');
  if (btn) btn.disabled = true;
  fetch(url, {method:'POST',headers:{'Content-Type':'application/json'}})
    .then(function(r){ return r.json(); })
    .then(function(data){
      window.location.href = '/review';
    })
    .catch(function(e){
      alert('Error: ' + e.message);
      if (btn) btn.disabled = false;
    });
}
"""


def review_detail_page(*, proposal: dict) -> str:
    """Render the full detail view for a single proposal with action buttons."""
    pid = str(proposal.get("proposal_id", ""))
    state = str(proposal.get("state", "pending"))
    project = str(proposal.get("project_key", ""))
    category = str(proposal.get("category", ""))
    risk = str(proposal.get("risk_level", ""))
    source_agent = str(proposal.get("source_agent", ""))
    created_at = str(proposal.get("created_at", ""))

    # Sections
    sections_html = ""
    for title, key in _PROPOSAL_SECTIONS:
        val = str(proposal.get(key, ""))
        sections_html += f"""<div class="section">
  <h3>{_html.escape(title)}</h3>
  <p>{_html.escape(val)}</p>
</div>"""

    # Determine which buttons are available
    is_pending = state == "pending"
    is_approved_db = state == "approved_db_only"
    is_rejected = state == "rejected"

    # Action buttons
    btns = ""
    if is_pending or is_approved_db:
        btns += (
            f'<button class="btn btn-approve" onclick="act(\'/api/review/{_html.escape(pid)}/approve-db-only\',\'存入记忆库\')">'
            '✓ Approve</button>'
        )
        btns += (
            f'<button class="btn btn-export" onclick="act(\'/api/review/{_html.escape(pid)}/approve-for-export\',\'批准并同步导出\')">'
            '↗ Approve & Sync</button>'
        )
    if is_approved_db:
        btns += (
            f'<button class="btn btn-export" onclick="act(\'/api/review/{_html.escape(pid)}/promote-to-export\',\'升级为同步导出\')">'
            '⬆ Promote</button>'
        )
    if is_pending or is_approved_db:
        btns += (
            f'<button class="btn btn-reject" onclick="act(\'/api/review/{_html.escape(pid)}/reject\',\'拒绝此提案\')">'
            '✕ Reject</button>'
        )
    if is_rejected:
        btns = '<div class="empty" style="flex:1">This proposal was rejected.</div>'
    if state in ("approved_for_export",):
        btns = '<div class="empty" style="flex:1">This proposal was approved and synced.</div>'
    if state == "superseded":
        btns = '<div class="empty" style="flex:1">This proposal was superseded by a newer version.</div>'

    # If no action buttons were set (e.g. rejected was not handled above)
    if not btns and is_rejected:
        btns = '<div class="empty" style="flex:1">This proposal was rejected.</div>'

    body = f"""{_nav(active="queue")}
<div class="detail-header">
  <a href="/review" class="back-link">← Review</a>
  <span class="detail-title">{_html.escape(pid[:12])}…</span>
  {_state_badge(state)}
</div>
<div class="meta-grid">
  <span class="label">Project</span><span class="value">{_html.escape(project)}</span>
  <span class="label">Category</span><span class="value">{_category_badge(category)}</span>
  <span class="label">Risk</span><span class="value">{_risk_badge(risk)}</span>
  <span class="label">Source</span><span class="value">{_html.escape(source_agent)}</span>
  <span class="label">Created</span><span class="value">{_html.escape(created_at[:19])}</span>
</div>
<div class="detail-body">{sections_html}</div>
<div class="action-bar">{btns}</div>
"""
    return _page(f"Proposal {pid[:12]}", body, extra_js=_ACTION_JS)


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------

def login_page(*, error: str = "") -> str:
    """Render a username/password login form that sets a session cookie."""
    error_html = f'<p style="color:var(--red);text-align:center;margin-bottom:12px">{_html.escape(error)}</p>' if error else ""
    body = f"""<div style="display:flex;align-items:center;justify-content:center;min-height:100vh;padding:16px">
<div style="background:var(--bg-card);border-radius:var(--radius);padding:32px 24px;max-width:360px;width:100%;border:1px solid var(--bg-hover)">
  <h1 style="text-align:center;color:var(--accent);margin-bottom:24px;font-size:1.4rem">🧠 Hermes</h1>
  {error_html}
  <form method="POST" action="/login">
    <label style="display:block;margin-bottom:8px;color:var(--fg-muted);font-size:.85rem">Username</label>
    <input type="text" name="username" autocomplete="username"
      style="width:100%;padding:12px;border:1px solid var(--bg-hover);border-radius:var(--radius);
             background:var(--bg);color:var(--fg);font-size:1rem;margin-bottom:16px;min-height:48px"
      placeholder="Username" autofocus>
    <label style="display:block;margin-bottom:8px;color:var(--fg-muted);font-size:.85rem">Password</label>
    <input type="password" name="password" autocomplete="current-password"
      style="width:100%;padding:12px;border:1px solid var(--bg-hover);border-radius:var(--radius);
             background:var(--bg);color:var(--fg);font-size:1rem;margin-bottom:20px;min-height:48px"
      placeholder="Password">
    <button type="submit"
      style="width:100%;padding:14px;border:none;border-radius:var(--radius);
             background:var(--accent);color:var(--bg);font-size:1rem;font-weight:600;cursor:pointer;min-height:48px">
      Sign In
    </button>
  </form>
  <p style="text-align:center;margin-top:16px;font-size:.75rem;color:var(--fg-dim)">
    API: <code style="background:var(--bg-hover);padding:2px 6px;border-radius:4px">Authorization: Bearer &lt;token&gt;</code>
  </p>
</div>
</div>"""
    return _page("Hermes Login", body)

def gallery_page() -> str:
    """Render the plotting library gallery page with interactive actions."""
    import yaml, os as _os
    _plotting_dir = os.environ.get("BRAIN_PLOTTING_DIR", "")
    _catalog_path = _os.path.join(_plotting_dir, "catalog.yaml")
    _demo_map = {
        "volcano": "volcano_demo.png",
        "manhattan": "manhattan_demo.png",
        "heatmap_clustered": "heatmap_demo.png",
        "apa_pattern": "apa_pattern_demo.png",
        "enrichment_bubble": "enrichment_bubble_demo.png",
        "grouped_bar": "grouped_bar_demo.png",
    }

    try:
        with open(_catalog_path) as _f:
            _catalog = yaml.safe_load(_f)
    except Exception:
        _catalog = {"charts": []}

    all_tags = set()
    chart_cards = ""
    for c in _catalog.get("charts", []):
        name = c.get("name", "")
        title = c.get("title", name)
        desc = c.get("description", "")
        tags = c.get("tags", [])
        has_template = _os.path.exists(_os.path.join(_plotting_dir, "templates", f"{name}.py"))
        img_file = _demo_map.get(name)

        for t in tags:
            all_tags.add(t)

        card_class = "has-demo" if img_file else "no-demo"
        badge = '<span class="badge green">Template</span>' if has_template else '<span class="badge orange">Planned</span>'

        if img_file:
            img_url = f"/gallery/static/{img_file}"
            preview = f'<div class="card-img"><img src="{img_url}" onclick="openModal(this)" loading="lazy"></div>'
        else:
            preview = '<div class="card-img" style="color:#484f58;font-size:13px;">Preview not available</div>'

        tags_html = "".join(f'<span class="tag">{_html.escape(t)}</span>' for t in tags[:4])

        safe_name = _html.escape(name)
        actions = (
            f'<div class="card-actions">'
            f'<button class="btn-act btn-ok" onclick="feedback(\'{safe_name}\',\'approve\')">✓ Approve</button>'
            f'<button class="btn-act btn-edit" onclick="feedback(\'{safe_name}\',\'suggest\')">✎ Suggest</button>'
            f'<button class="btn-act btn-no" onclick="feedback(\'{safe_name}\',\'reject\')">✕ Reject</button>'
            f'</div>' if img_file else ""
        )

        chart_cards += (
            f'<div class="gallery-card {card_class}" data-tags="{" ".join(tags)}">'
            f'{badge}{preview}'
            f'<div class="card-info"><h3>{_html.escape(title)}</h3>'
            f'<div class="desc">{_html.escape(desc[:80])}</div>'
            f'<div class="tags">{tags_html}</div></div>'
            f'{actions}'
            f'</div>'
        )

    filter_btns = '<button class="filter-btn active" data-filter="all">All</button>'
    for tag in sorted(all_tags):
        filter_btns += f'  <button class="filter-btn" data-filter="{_html.escape(tag)}">{_html.escape(tag)}</button>'

    # NOTE: JS goes in extra_js, NOT in the body f-string,
    # so that curly braces are not mangled by Python's f-string escaping.
    gallery_css = '''
<style>
.gallery-container { max-width: 1200px; margin: 0 auto; padding: 20px; }
.gallery-header { text-align: center; margin-bottom: 30px; }
.gallery-header h1 { color: var(--text-primary, #e6edf3); font-size: 24px; }
.gallery-header p { color: var(--text-secondary, #8b949e); font-size: 14px; }
.filter-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }
.filter-btn { background: var(--card-bg, #21262d); border: 1px solid var(--border, #30363d); color: var(--text-secondary, #8b949e); padding: 6px 16px; border-radius: 20px; cursor: pointer; font-size: 12px; transition: all 0.2s; }
.filter-btn:hover, .filter-btn.active { background: rgba(31,111,235,0.2); border-color: var(--accent, #58a6ff); color: var(--accent, #58a6ff); }
.gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.gallery-card { background: var(--card-bg, #161b22); border: 1px solid var(--border, #30363d); border-radius: 8px; overflow: hidden; transition: all 0.3s; position: relative; }
.gallery-card:hover { border-color: var(--accent, #58a6ff); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(88,166,255,0.15); }
.gallery-card.has-demo { border-left: 3px solid #3fb950; }
.gallery-card.no-demo { border-left: 3px solid #484f58; opacity: 0.7; }
.card-img { background: #fff; min-height: 180px; display: flex; align-items: center; justify-content: center; padding: 8px; cursor: pointer; }
.card-img img { max-width: 100%; max-height: 200px; object-fit: contain; }
.card-info { padding: 12px 14px; }
.card-info h3 { font-size: 14px; color: var(--text-primary, #e6edf3); margin: 0 0 4px; }
.card-info .desc { font-size: 12px; color: var(--text-secondary, #8b949e); margin-bottom: 8px; line-height: 1.4; }
.card-info .tags { display: flex; gap: 6px; flex-wrap: wrap; }
.card-info .tag { font-size: 10px; background: var(--card-bg, #21262d); border: 1px solid var(--border, #30363d); color: var(--text-secondary, #8b949e); padding: 1px 8px; border-radius: 10px; }
.badge { position: absolute; top: 8px; right: 8px; font-size: 10px; padding: 2px 8px; border-radius: 10px; }
.badge.green { background: rgba(35,134,53,0.5); color: #fff; }
.badge.orange { background: rgba(158,106,3,0.5); color: #fff; }
.card-actions { display: flex; gap: 6px; padding: 8px 14px 12px; border-top: 1px solid var(--border, #30363d); }
.btn-act { border: 1px solid var(--border, #30363d); border-radius: 4px; padding: 4px 10px; font-size: 11px; cursor: pointer; transition: all 0.2s; background: var(--card-bg, #21262d); color: var(--text-secondary, #8b949e); }
.btn-ok:hover { background: rgba(35,134,53,0.3); border-color: #3fb950; color: #3fb950; }
.btn-edit:hover { background: rgba(31,111,235,0.3); border-color: #58a6ff; color: #58a6ff; }
.btn-no:hover { background: rgba(248,81,73,0.3); border-color: #f85149; color: #f85149; }
.modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 1000; justify-content: center; align-items: center; }
.modal-overlay.show { display: flex; }
.modal-overlay img { max-width: 90vw; max-height: 85vh; object-fit: contain; background: #fff; border-radius: 4px; }
.modal-overlay .close { position: absolute; top: 20px; right: 30px; color: #fff; font-size: 28px; cursor: pointer; }
.toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 20px; border-radius: 8px; color: #fff; font-size: 14px; z-index: 2000; opacity: 0; transition: opacity 0.3s; pointer-events: none; }
.toast.show { opacity: 1; }
.toast.approve { background: #3fb950; }
.toast.suggest { background: #58a6ff; }
.toast.reject { background: #f85149; }
.suggest-input { margin: 6px 14px 10px; }
.suggest-input textarea { width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--border, #30363d); background: var(--bg, #0d1117); color: var(--fg, #e6edf3); font-size: 12px; min-height: 60px; resize: vertical; box-sizing: border-box; }
.suggest-input button { margin-top: 4px; padding: 4px 12px; border-radius: 4px; background: var(--accent, #58a6ff); color: #fff; border: none; font-size: 12px; cursor: pointer; }
</style>
'''

    body = (
        gallery_css +
        '<div class="gallery-container">'
        f'{_nav(active="gallery")}'
        '<div class="gallery-header"><h1>Sci-Fig Gallery</h1>'
        '<p>View demo charts, approve / suggest / reject to iterate templates.</p></div>'
        '<div class="filter-bar">' + filter_btns + '</div>'
        '<div class="gallery-grid">' + chart_cards + '</div>'
        '<div class="modal-overlay" id="modal" onclick="closeModal()"><span class="close">&times;</span>'
        '<img id="modal-img" src=""></div>'
        '<div class="toast" id="toast"></div>'
        '</div>'
    )

    gallery_js = """
function openModal(img) {
  document.getElementById('modal-img').src = img.src;
  document.getElementById('modal').classList.add('show');
}
function closeModal() {
  document.getElementById('modal').classList.remove('show');
}
function showToast(msg, type) {
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast ' + type + ' show';
  setTimeout(function(){ t.classList.remove('show'); }, 2500);
}
function feedback(chart, action) {
  if (action === 'suggest') {
    var card = event.target.closest('.gallery-card');
    var existing = card.querySelector('.suggest-input');
    if (existing) { existing.remove(); return; }
    var div = document.createElement('div');
    div.className = 'suggest-input';
    var ta = document.createElement('textarea');
    ta.id = 'suggest-' + chart;
    ta.placeholder = 'Your suggestion...';
    div.appendChild(ta);
    var btn = document.createElement('button');
    btn.textContent = 'Submit';
    btn.onclick = function(){ submitSuggest(chart); };
    div.appendChild(btn);
    card.appendChild(div);
    return;
  }
  fetch('/api/gallery/feedback', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({chart: chart, action: action, suggestion: ''}),
    credentials: 'same-origin'
  }).then(function(r) {
    if (r.ok) { showToast(chart + (action === 'approve' ? ' ✓ Approved' : ' ✕ Rejected'), action); }
    else { showToast('Error: ' + r.status, 'reject'); }
  }).catch(function() {
    showToast(chart + (action === 'approve' ? ' ✓ Approved' : ' ✕ Rejected'), action);
  });
}
function submitSuggest(chart) {
  var textarea = document.getElementById('suggest-' + chart);
  var text = textarea ? textarea.value.trim() : '';
  if (!text) { showToast('Enter a suggestion first', 'reject'); return; }
  fetch('/api/gallery/feedback', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({chart: chart, action: 'suggest', suggestion: text}),
    credentials: 'same-origin'
  }).then(function(r) {
    if (r.ok) { showToast(chart + ' ✓ Suggestion saved', 'suggest'); }
  }).catch(function() {
    showToast(chart + ' ✓ Suggestion noted', 'suggest');
  });
  var input = textarea.closest('.suggest-input');
  if (input) input.remove();
}
// Restore saved filter from localStorage
(function() {
  var saved = localStorage.getItem('gallery_filter');
  if (saved) {
    document.querySelectorAll('.filter-btn').forEach(function(b){ b.classList.remove('active'); });
    var btn = document.querySelector('.filter-btn[data-filter="' + saved + '"]');
    if (btn) {
      btn.classList.add('active');
      var f = saved;
      document.querySelectorAll('.gallery-card').forEach(function(c){
        c.style.display = (f === 'all' || c.dataset.tags.indexOf(f) >= 0) ? '' : 'none';
      });
    }
  }
})();
document.querySelectorAll('.filter-btn').forEach(function(btn){
  btn.addEventListener('click', function() {
    document.querySelectorAll('.filter-btn').forEach(function(b){ b.classList.remove('active'); });
    this.classList.add('active');
    var f = this.dataset.filter;
    localStorage.setItem('gallery_filter', f);
    document.querySelectorAll('.gallery-card').forEach(function(c){
      c.style.display = (f === 'all' || c.dataset.tags.indexOf(f) >= 0) ? '' : 'none';
    });
  });
});
"""

    return _page("Sci-Fig Gallery", body, extra_js=gallery_js)


# ---------------------------------------------------------------------------
# Security Monitoring Page
# ---------------------------------------------------------------------------

def security_page(
    *,
    do_status: dict,
    proxy_status: dict,
    proxy_traffic: list[dict],
) -> str:
    """Render security monitoring kanban."""
    # DO status
    do = do_status
    f2b_banned = do.get("f2b_banned", [])
    f2b_total = do.get("f2b_total", 0)
    ssh_port = do.get("ssh_port", "22")
    ufw_rules = do.get("ufw_rules", [])
    top_attackers = do.get("top_attackers", [])
    uptime = do.get("uptime", "?")
    sysctl = do.get("sysctl", {})

    # Proxy status
    pr = proxy_status
    pr_f2b_banned = pr.get("f2b_banned", [])
    pr_f2b_total = pr.get("f2b_total", 0)
    pr_ssh_port = pr.get("ssh_port", "22")
    pr_ufw_rules = pr.get("ufw_rules", [])
    pr_uptime = pr.get("uptime", "?")
    pr_sysctl = pr.get("sysctl", {})

    # Build attacker rows
    attacker_rows = ""
    max_cnt = max((a.get("count", 0) for a in top_attackers), default=1) or 1
    for a in top_attackers[:8]:
        ip = _html.escape(a.get("ip", "?"))
        cnt = a.get("count", 0)
        bar_w = min(cnt / max_cnt * 100, 100)
        attacker_rows += f"""<div class="sec-bar-row">
  <span class="sec-ip">{ip}</span>
  <div class="sec-bar-bg"><div class="sec-bar-fill" style="width:{bar_w:.0f}%"></div></div>
  <span class="sec-cnt">{cnt}</span>
</div>"""

    # Build UFW rule rows for a given server
    def _ufw_rows(rules):
        rows = ""
        for r in rules:
            action = _html.escape(r.get("action", "?"))
            to = _html.escape(r.get("to", "?"))
            comment = _html.escape(r.get("comment", ""))
            color = "var(--green)" if action == "ALLOW" else "var(--red)" if action in ("REJECT", "DENY") else "var(--fg-dim)"
            rows += f"""<div class="sec-ufw-row">
  <span class="sec-ufw-action" style="color:{color}">{action}</span>
  <span class="sec-ufw-to">{to}</span>
  <span class="sec-ufw-comment">{comment}</span>
</div>"""
        return rows

    do_ufw_rows = _ufw_rows(ufw_rules)
    pr_ufw_rows = _ufw_rows(pr_ufw_rules)

    # Build proxy traffic rows
    traffic_rows = ""
    for t in proxy_traffic:
        name = _html.escape(t.get("name", "?"))
        proto = _html.escape(t.get("proto", "?"))
        port = t.get("port", 0)
        up_mb = t.get("up", 0) / 1048576
        down_mb = t.get("down", 0) / 1048576
        enable = t.get("enable", False)
        dot_cls = "dot-green" if enable else "dot-red"
        clients = t.get("clients", [])
        client_rows = ""
        for c in clients:
            c_email = _html.escape(c.get("email", "?"))
            c_up = c.get("up", 0) / 1048576
            c_down = c.get("down", 0) / 1048576
            c_enable = c.get("enable", False)
            c_dot = "dot-green" if c_enable else "dot-red"
            client_rows += f"""<div class="sec-client-row">
    <span class="dot {c_dot}"></span>
    <span class="sec-client-name">{c_email}</span>
    <span class="sec-client-traffic">{c_up:.1f}↑ {c_down:.1f}↓ MB</span>
  </div>"""
        traffic_rows += f"""<div class="sec-inbound-card">
  <div class="sec-inbound-header">
    <span class="dot {dot_cls}"></span>
    <span class="sec-inbound-name">{name}</span>
    <span class="sec-inbound-meta">{proto} :{port}</span>
    <span class="sec-inbound-traffic">{up_mb:.1f}↑ {down_mb:.1f}↓ MB</span>
  </div>
  <div class="sec-inbound-clients">{client_rows}</div>
</div>"""

    # Banned IPs
    f2b_badge = f'<span class="sec-badge sec-badge-red" title="Banned IPs">{len(f2b_banned)}</span>'
    pr_badge = f'<span class="sec-badge sec-badge-red" title="Banned IPs">{len(pr_f2b_banned)}</span>'

    # Sysctl badges helper
    def _sysctl_badges(sc):
        syn = "✅" if sc.get("syncookies") else "❌"
        redir = "✅" if not sc.get("accept_redirects") else "❌"
        fwd = "✅" if not sc.get("ip_forward") else "⚠️"
        return syn, redir, fwd

    do_syn, do_redir, do_fwd = _sysctl_badges(sysctl)
    pr_syn, pr_redir, pr_fwd = _sysctl_badges(pr_sysctl)

    body = f"""{_nav(active="security")}
<div class="sec-header">
  <h1>🛡️ Security Monitor</h1>
  <span class="sec-refresh" id="refresh-indicator">⟳ Live</span>
</div>

<div class="sec-kanban">

  <div class="sec-col">
    <h3>🏠 DO VPS <span class="sec-badge">SSH:{ssh_port}</span> {f2b_badge}</h3>
    <div class="sec-card sec-overview">
      <div class="sec-stat-row"><span>Uptime</span><span>{_html.escape(uptime)}</span></div>
      <div class="sec-stat-row"><span>Syncookies</span><span>{do_syn}</span></div>
      <div class="sec-stat-row"><span>ICMP Redirects</span><span>{do_redir}</span></div>
      <div class="sec-stat-row"><span>IP Forward</span><span>{do_fwd}</span></div>
    </div>
    <h4>Top Attackers</h4>
    <div class="sec-card">{attacker_rows if attacker_rows else '<span class="sec-empty">No recent attackers</span>'}</div>
    <h4>Firewall Rules ({len(ufw_rules)})</h4>
    <div class="sec-card sec-ufw-list">{do_ufw_rows if do_ufw_rows else '<span class="sec-empty">No rules</span>'}</div>
  </div>

  <div class="sec-col">
    <h3>🌐 Proxy VPS <span class="sec-badge">SSH:{pr_ssh_port}</span> {pr_badge}</h3>
    <div class="sec-card sec-overview">
      <div class="sec-stat-row"><span>Uptime</span><span>{_html.escape(pr_uptime)}</span></div>
      <div class="sec-stat-row"><span>Syncookies</span><span>{pr_syn}</span></div>
      <div class="sec-stat-row"><span>ICMP Redirects</span><span>{pr_redir}</span></div>
      <div class="sec-stat-row"><span>IP Forward</span><span>{pr_fwd}</span></div>
    </div>
    <h4>Proxy Traffic</h4>
    {traffic_rows if traffic_rows else '<div class="sec-card"><span class="sec-empty">No inbound data</span></div>'}
    <h4>Firewall Rules ({len(pr_ufw_rules)})</h4>
    <div class="sec-card sec-ufw-list">{pr_ufw_rows if pr_ufw_rows else '<span class="sec-empty">No rules</span>'}</div>
  </div>

</div>

<script>
// Auto-refresh every 30s
setTimeout(function(){{ location.reload(); }}, 30000);
</script>

<style>
.sec-header{{display:flex;align-items:center;justify-content:space-between;padding:12px 16px 0}}
.sec-header h1{{font-size:1.2rem;margin:0}}
.sec-refresh{{font-size:.78rem;color:var(--fg-dim);animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.sec-kanban{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 16px 16px}}
@media(max-width:720px){{.sec-kanban{{grid-template-columns:1fr}}}}
.sec-col{{min-width:0}}
.sec-col h3{{font-size:1rem;margin:12px 0 6px;color:var(--accent)}}
.sec-col h4{{font-size:.85rem;margin:10px 0 4px;color:var(--fg-muted)}}
.sec-card{{background:var(--bg-card);border-radius:var(--radius);padding:10px 12px;margin-bottom:8px}}
.sec-overview{{background:var(--bg-hover);border-radius:var(--radius)}}
.sec-empty{{color:var(--fg-dim);font-size:.82rem;font-style:italic}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}}
.dot-green{{background:var(--green)}}
.dot-red{{background:var(--red)}}
.sec-badge{{font-size:.7rem;padding:2px 7px;border-radius:10px;background:var(--bg-hover);color:var(--fg-dim);margin-left:6px}}
.sec-badge-red{{background:var(--red);color:#fff}}
.sec-stat-row{{display:flex;justify-content:space-between;padding:3px 0;font-size:.88rem;border-bottom:1px solid var(--bg-hover)}}
.sec-stat-row:last-child{{border-bottom:none}}
.sec-bar-row{{display:flex;align-items:center;gap:8px;padding:3px 0;font-size:.82rem}}
.sec-ip{{min-width:130px;color:var(--fg-dim);font-family:monospace;font-size:.78rem}}
.sec-bar-bg{{flex:1;height:6px;background:var(--bg-hover);border-radius:3px;overflow:hidden}}
.sec-bar-fill{{height:100%;background:var(--red);border-radius:3px}}
.sec-cnt{{min-width:40px;text-align:right;color:var(--fg-dim);font-size:.78rem}}
.sec-ufw-row{{display:flex;align-items:center;gap:6px;padding:3px 0;font-size:.82rem;border-bottom:1px solid var(--bg-hover)}}
.sec-ufw-row:last-child{{border-bottom:none}}
.sec-ufw-action{{min-width:48px;font-weight:600;font-size:.78rem}}
.sec-ufw-to{{min-width:90px;font-family:monospace;font-size:.78rem}}
.sec-ufw-comment{{color:var(--fg-dim);font-size:.75rem}}
.sec-inbound-card{{background:var(--bg-card);border-radius:var(--radius);padding:10px 12px;margin-bottom:8px}}
.sec-inbound-header{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.sec-inbound-name{{font-weight:600;font-size:.92rem}}
.sec-inbound-meta{{font-size:.78rem;color:var(--fg-dim);font-family:monospace}}
.sec-inbound-traffic{{font-size:.78rem;color:var(--cyan);margin-left:auto}}
.sec-inbound-clients{{margin-top:6px;padding-left:14px}}
.sec-client-row{{display:flex;align-items:center;gap:6px;padding:2px 0;font-size:.82rem}}
.sec-client-name{{min-width:120px}}
.sec-client-traffic{{color:var(--fg-dim);font-size:.78rem;font-family:monospace}}
</style>"""

    return _page("Security Monitor", body)


# ---------------------------------------------------------------------------
# Settings Page
# ---------------------------------------------------------------------------

def settings_page(*, error: str = "", success: str = "") -> str:
    """Render user settings page with password change and preferences."""
    error_html = f'<div class="settings-error">{_html.escape(error)}</div>' if error else ""
    success_html = f'<div class="settings-success">{_html.escape(success)}</div>' if success else ""

    body = f"""{_nav(active="settings")}
<div style="padding:16px">
  <h1 style="font-size:1.2rem;margin-bottom:16px">⚙️ Settings</h1>

  <div class="settings-section">
    <h3>🔐 Change Password</h3>
    {error_html}
    {success_html}
    <form method="POST" action="/settings/password" class="settings-form">
      <label class="settings-label">Current Password</label>
      <input type="password" name="current_password" class="settings-input" required autocomplete="current-password">
      <label class="settings-label">New Password</label>
      <input type="password" name="new_password" class="settings-input" required autocomplete="new-password" minlength="6">
      <label class="settings-label">Confirm New Password</label>
      <input type="password" name="confirm_password" class="settings-input" required autocomplete="new-password">
      <button type="submit" class="settings-btn">Update Password</button>
    </form>
  </div>

  <div class="settings-section">
    <h3>🎨 Display Preferences</h3>
    <form class="settings-form" id="prefs-form">
      <label class="settings-label">Display Name</label>
      <input type="text" name="display_name" class="settings-input" placeholder="Your name" id="display-name">
      <label class="settings-label">Theme</label>
      <select name="theme" class="settings-input" id="theme-select">
        <option value="dark">Dracula Dark</option>
        <option value="light">Light</option>
      </select>
      <button type="button" class="settings-btn" onclick="savePrefs()">Save Preferences</button>
    </form>
  </div>

  <div class="settings-section">
    <h3>📊 System Info</h3>
    <div class="settings-info-grid">
      <div class="settings-info-item">
        <span class="settings-info-label">Brain Version</span>
        <span class="settings-info-value">MVP</span>
      </div>
      <div class="settings-info-item">
        <span class="settings-info-label">Hermes Agent</span>
        <span class="settings-info-value">Active</span>
      </div>
    </div>
  </div>
</div>

<style>
.settings-section{{background:var(--bg-card);border-radius:var(--radius);padding:16px 20px;margin-bottom:16px;border:1px solid var(--bg-hover)}}
.settings-section h3{{color:var(--accent);font-size:.95rem;margin:0 0 12px}}
.settings-form{{display:flex;flex-direction:column;gap:10px;max-width:400px}}
.settings-label{{font-size:.85rem;color:var(--fg-muted);margin-top:4px}}
.settings-input{{background:var(--bg);border:1px solid var(--bg-hover);border-radius:var(--radius);padding:10px 12px;color:var(--fg);font-size:.95rem;outline:none;transition:border-color .15s}}
.settings-input:focus{{border-color:var(--accent)}}
.settings-btn{{background:var(--accent);color:#000;border:none;border-radius:var(--radius);padding:12px;font-size:.95rem;font-weight:600;cursor:pointer;transition:opacity .15s;margin-top:4px}}
.settings-btn:hover{{opacity:.85}}
.settings-error{{background:rgba(255,85,85,.15);color:var(--red);padding:8px 12px;border-radius:var(--radius);font-size:.9rem;margin-bottom:8px}}
.settings-success{{background:rgba(80,250,123,.15);color:var(--green);padding:8px 12px;border-radius:var(--radius);font-size:.9rem;margin-bottom:8px}}
.settings-info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.settings-info-item{{background:var(--bg-hover);border-radius:var(--radius);padding:12px}}
.settings-info-label{{display:block;font-size:.75rem;color:var(--fg-muted);text-transform:uppercase;letter-spacing:.04em}}
.settings-info-value{{display:block;font-size:1.1rem;font-weight:600;color:var(--fg);margin-top:2px}}
</style>

<script>
// Load saved preferences
(function(){{
  var n=localStorage.getItem('hermes_display_name');
  if(n)document.getElementById('display-name').value=n;
  var t=localStorage.getItem('hermes_theme');
  if(t)document.getElementById('theme-select').value=t;
}})();

function savePrefs(){{
  var n=document.getElementById('display-name').value;
  var t=document.getElementById('theme-select').value;
  localStorage.setItem('hermes_display_name',n);
  localStorage.setItem('hermes_theme',t);
  alert('Preferences saved!');
}}
</script>
"""

    return _page("Settings", body)

