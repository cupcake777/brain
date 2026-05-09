"""HTML templates for Hermes review UI – dependency-free, mobile-first, dark theme."""

from __future__ import annotations
import os

import html as _html

# ---------------------------------------------------------------------------
# Shared CSS – shadcn-inspired OKLCH design system
# ---------------------------------------------------------------------------

_DARK_CSS = """\
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  /* 3-layer depth: bg → surface → card */
  --bg:oklch(.13 .01 270);
  --surface:oklch(.16 .01 270);
  --card:oklch(.20 .02 275);
  --card-hover:oklch(.25 .025 275);
  /* Borders */
  --border:oklch(1 0 0 / 10%);
  --border-hover:oklch(1 0 0 / 18%);
  --border-focus:#a78bfa;
  /* Text */
  --ink:#e2e4ed;
  --ink-muted:#8b90a5;
  --ink-dim:#5c6078;
  /* Semantic colors */
  --primary:#a78bfa;--primary-muted:rgba(167,139,250,.12);
  --success:#34d399;--success-muted:rgba(52,211,153,.12);
  --warning:#fbbf24;--warning-muted:rgba(251,191,36,.12);
  --danger:#f87171;--danger-muted:rgba(248,113,113,.12);
  --info:#67e8f9;--info-muted:rgba(103,232,249,.12);
  /* Radius scale */
  --r-sm:6px;--r-md:10px;--r-lg:14px;--r-xl:18px;--r-pill:999px;
  /* Shadows */
  --shadow-xs:0 1px 2px rgba(0,0,0,.2);
  --shadow-sm:0 2px 4px rgba(0,0,0,.25);
  --shadow-md:0 4px 12px rgba(0,0,0,.3);
  --shadow-lg:0 8px 24px rgba(0,0,0,.4);
  --shadow-xl:0 12px 40px rgba(0,0,0,.5);
  /* Spacing */
  --sp-xs:4px;--sp-sm:8px;--sp-md:16px;--sp-lg:24px;--sp-xl:32px;
  /* Font */
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
  --font-mono:"JetBrains Mono","Fira Code","SF Mono",monospace;
  /* Transition */
  --ease-out:cubic-bezier(.16,1,.3,1);
  --duration:150ms;
}
html{font-family:var(--font);background:var(--surface);color:var(--ink);line-height:1.6;-webkit-text-size-adjust:100%;font-synthesis-weight:none;text-rendering:optimizeLegibility}
body{min-height:100vh}
a{color:var(--primary);text-decoration:none;transition:color var(--duration)}
a:hover{color:var(--ink)}
::selection{background:var(--primary);color:var(--bg)}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--surface)}
::-webkit-scrollbar-thumb{background:var(--card);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--ink-muted)}
@keyframes fadeIn{from{opacity:0;transform:scale(.96)}to{opacity:1;transform:scale(1)}}
@keyframes slideInRight{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}
@keyframes slideUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* ---- Top nav ---- */
.topnav{display:flex;align-items:center;justify-content:space-between;padding:0 var(--sp-lg);background:var(--surface);border-bottom:1px solid var(--border);min-height:56px;position:sticky;top:0;z-index:50;backdrop-filter:blur(8px)}
.topnav .brand{font-weight:700;font-size:1.15rem;color:var(--primary);white-space:nowrap;letter-spacing:-.01em}
.topnav .links-desktop{display:none;gap:4px}
.topnav .links-desktop a{color:var(--ink-muted);font-size:.88rem;padding:8px 14px;min-height:44px;display:flex;align-items:center;white-space:nowrap;border-radius:var(--r-md);transition:background var(--duration),color var(--duration)}
.topnav .links-desktop a.active{color:var(--ink);background:var(--primary-muted);font-weight:500}
.topnav .links-desktop a:hover{color:var(--ink);background:var(--border-hover)}
.hamburger{display:flex;flex-direction:column;gap:5px;padding:12px 4px;cursor:pointer;background:none;border:none;min-width:44px;min-height:44px;align-items:center;justify-content:center;border-radius:var(--r-md);transition:background var(--duration)}
.hamburger:hover{background:var(--border-hover)}
.hamburger span{display:block;width:20px;height:2px;background:var(--ink);border-radius:2px;transition:transform .2s,opacity .2s}
.hamburger.open span:nth-child(1){transform:translateY(7px) rotate(45deg)}
.hamburger.open span:nth-child(2){opacity:0}
.hamburger.open span:nth-child(3){transform:translateY(-7px) rotate(-45deg)}
.mobile-menu{display:none;position:fixed;top:56px;left:0;right:0;bottom:0;background:var(--surface);z-index:40;padding:var(--sp-md);flex-direction:column;gap:0;border-top:1px solid var(--border)}
.mobile-menu.open{display:flex}
.mobile-menu a{display:flex;align-items:center;gap:10px;padding:14px 12px;font-size:.95rem;color:var(--ink-muted);min-height:48px;border-radius:var(--r-md);text-decoration:none;transition:background var(--duration),color var(--duration)}
.mobile-menu a.active{color:var(--ink);background:var(--primary-muted);font-weight:500}
.mobile-menu a:hover{color:var(--ink);background:var(--border-hover)}
.mobile-menu a svg{width:20px;height:20px;flex-shrink:0}

@media(min-width:720px){
  .topnav .links-desktop{display:flex}
  .hamburger{display:none}
}

/* ---- Filter tabs ---- */
.tabs{display:flex;gap:6px;padding:var(--sp-md) var(--sp-md) var(--sp-sm);overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tabs a,.tabs button{
  display:inline-flex;align-items:center;gap:6px;
  padding:8px 16px;border:1px solid var(--border);border-radius:var(--r-pill);
  background:transparent;color:var(--ink-muted);font-size:.84rem;font-weight:500;cursor:pointer;
  min-height:40px;white-space:nowrap;transition:all var(--duration)
}
.tabs a.active,.tabs button.active{background:var(--primary-muted);color:var(--ink);border-color:var(--border-focus)}
.tabs a:hover,.tabs button:hover{background:var(--border-hover);color:var(--ink)}
.tab-count{font-size:.72rem;background:var(--border-hover);border-radius:var(--r-pill);padding:1px 7px;color:var(--ink-dim);font-weight:600;margin-left:2px}

/* ---- Card grid ---- */
.card-grid{display:grid;grid-template-columns:1fr;gap:var(--sp-md);padding:0 var(--sp-md) var(--sp-md)}
@media(min-width:720px){.card-grid{grid-template-columns:repeat(auto-fill,minmax(380px,1fr))}}

.card{display:block;background:var(--card);border-radius:var(--r-lg);padding:var(--sp-md);border:1px solid var(--border);text-decoration:none;color:var(--ink);min-height:44px;transition:all var(--duration) var(--ease-out);box-shadow:var(--shadow-xs)}
.card:hover{border-color:var(--border-focus);background:var(--card-hover);text-decoration:none;transform:translateY(-2px);box-shadow:var(--shadow-md)}
.card-top{display:flex;align-items:center;gap:var(--sp-sm);flex-wrap:wrap;margin-bottom:var(--sp-sm)}
.card-preview{font-size:.9rem;color:var(--ink);overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;max-width:100%;line-height:1.5}
.card-meta{display:flex;gap:var(--sp-sm);margin-top:var(--sp-sm);font-size:.78rem;color:var(--ink-muted)}

/* ---- Badges ---- */
.badge{display:inline-flex;align-items:center;height:22px;padding:2px 10px;border-radius:var(--r-pill);font-size:.7rem;font-weight:600;letter-spacing:.02em;white-space:nowrap;transition:all var(--duration)}
.badge-pending{background:var(--warning-muted);color:var(--warning)}
.badge-approved_db_only{background:var(--success-muted);color:var(--success)}
.badge-approved_for_export{background:rgba(52,211,153,.22);color:var(--success)}
.badge-rejected{background:var(--danger-muted);color:var(--danger)}
.badge-superseded{background:var(--border-hover);color:var(--ink-dim)}
.badge-rule{background:var(--primary-muted);color:var(--primary)}
.badge-pattern{background:var(--info-muted);color:var(--info)}
.badge-insight{background:rgba(251,146,60,.12);color:#fb923c}
.badge-warning{background:rgba(251,113,133,.12);color:#fb7185}
.badge-risk-high{background:var(--danger-muted);color:var(--danger)}
.badge-risk-medium{background:var(--warning-muted);color:var(--warning)}
.badge-risk-low{background:var(--success-muted);color:var(--success)}

/* ---- Detail page ---- */
.detail-header{padding:var(--sp-md);display:flex;align-items:center;gap:var(--sp-sm);flex-wrap:wrap}
.back-link{display:inline-flex;align-items:center;gap:4px;color:var(--ink-muted);font-size:.88rem;min-height:44px;border-radius:var(--r-sm);transition:color var(--duration)}
.back-link:hover{color:var(--primary)}
.detail-title{font-size:1.1rem;font-weight:700;word-break:break-all;color:var(--ink)}
.detail-body{padding:0 var(--sp-md) var(--sp-md)}
.section{margin-bottom:var(--sp-lg);background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-md);transition:border-color var(--duration)}
.section:hover{border-color:var(--border-hover)}
.section h3{color:var(--primary);font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:var(--sp-sm);font-weight:600}
.section p{color:var(--ink);font-size:.9rem;white-space:pre-wrap;word-break:break-word;line-height:1.6}
.meta-grid{display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-sm) var(--sp-md);padding:var(--sp-md);font-size:.84rem}
.meta-grid .label{color:var(--ink-muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em}
.meta-grid .value{color:var(--ink);font-weight:500}

/* ---- Action buttons ---- */
.action-bar{
  position:fixed;bottom:0;left:0;right:0;
  display:flex;gap:var(--sp-sm);padding:var(--sp-sm) var(--sp-md);
  background:var(--surface);border-top:1px solid var(--border);
  backdrop-filter:blur(8px);z-index:100
}
body:has(.action-bar){padding-bottom:76px}
.action-bar .btn{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;padding:12px var(--sp-sm);border:none;border-radius:var(--r-md);font-size:.9rem;font-weight:600;cursor:pointer;min-height:48px;transition:all var(--duration) var(--ease-out);position:relative;overflow:hidden}
.action-bar .btn:active{transform:translateY(1px)}
.btn-approve{background:var(--success-muted);color:var(--success)}
.btn-approve:hover{background:rgba(52,211,153,.25);box-shadow:var(--shadow-sm)}
.btn-export{background:var(--primary-muted);color:var(--primary)}
.btn-export:hover{background:rgba(167,139,250,.25);box-shadow:var(--shadow-sm)}
.btn-reject{background:var(--danger-muted);color:var(--danger)}
.btn-reject:hover{background:rgba(248,113,113,.25);box-shadow:var(--shadow-sm)}
.btn:disabled{opacity:.4;cursor:not-allowed;transform:none}
.btn:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(167,139,250,.3)}
kbd{font-family:var(--font-mono);font-size:.68rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--r-sm);padding:1px 5px;margin-left:4px;color:var(--ink-dim);font-weight:500}

/* ---- Dashboard ---- */
.dash-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;padding:0 var(--sp-md) var(--sp-md)}
@media(min-width:720px){.dash-grid{grid-template-columns:repeat(4,1fr)}}
.dash-card{background:var(--card);border-radius:var(--r-lg);padding:var(--sp-lg) var(--sp-md);border:1px solid var(--border);text-align:center;box-shadow:var(--shadow-xs);transition:all var(--duration)}
.dash-card:hover{border-color:var(--border-hover);box-shadow:var(--shadow-sm)}
.dash-card .num{font-size:2rem;font-weight:700;line-height:1}
.dash-card .label{font-size:.75rem;color:var(--ink-muted);margin-top:4px;text-transform:uppercase;letter-spacing:.06em}
.dash-section{padding:0 var(--sp-md) var(--sp-md)}
.dash-section h3{color:var(--primary);font-size:.88rem;margin-bottom:var(--sp-sm);font-weight:600}
.dash-table{width:100%;border-collapse:collapse;font-size:.84rem}
.dash-table th,.dash-table td{padding:var(--sp-sm) 12px;text-align:left;border-bottom:1px solid var(--border)}
.dash-table th{color:var(--ink-muted);font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.04em}
.dash-table td{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:120px}
.dash-details{padding:0 var(--sp-md) var(--sp-sm)}
.dash-details-header{display:flex;align-items:center;gap:var(--sp-sm);padding:var(--sp-sm) var(--sp-md);cursor:pointer;font-size:.92rem;font-weight:600;color:var(--ink);user-select:none;border-bottom:1px solid var(--border);background:var(--card);border-radius:var(--r-lg);margin:var(--sp-sm) 0;transition:background var(--duration)}
.dash-details-header:hover{background:var(--card-hover)}
.dash-details-count{font-size:.72rem;background:var(--border-hover);border-radius:var(--r-pill);padding:2px 8px;color:var(--ink-dim);margin-left:auto}
.dash-details[open] .dash-details-header{border-radius:var(--r-lg) var(--r-lg) 0 0}

/* ---- Exports list ---- */
.export-list{padding:0 var(--sp-md) var(--sp-md)}
.export-item{display:flex;align-items:center;justify-content:space-between;padding:var(--sp-sm) var(--sp-md);background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);margin-bottom:var(--sp-sm);min-height:44px;gap:var(--sp-sm);text-decoration:none;color:var(--ink);transition:all var(--duration);box-shadow:var(--shadow-xs)}
.export-item:hover{border-color:var(--border-focus);background:var(--card-hover);text-decoration:none;box-shadow:var(--shadow-sm)}
.export-item .file-name{font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.export-item .file-meta{font-size:.78rem;color:var(--ink-muted);display:flex;gap:var(--sp-sm);flex-shrink:0}
.export-item .download-icon{color:var(--primary);font-size:1.2rem;flex-shrink:0}

/* ---- State dot ---- */
.state-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px;vertical-align:middle}
.state-dot-pending{background:var(--warning)}
.state-dot-approved_db_only{background:var(--success)}
.state-dot-approved_for_export{background:var(--success)}
.state-dot-rejected{background:var(--danger)}
.state-dot-superseded{background:var(--ink-dim)}

/* ---- Empty state ---- */
.empty{padding:var(--sp-xl) var(--sp-md);text-align:center;color:var(--ink-dim);font-size:.95rem}

/* ---- Quota board ---- */
.quota-summary{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;padding:0 var(--sp-md) var(--sp-sm)}
@media(min-width:720px){.quota-summary{grid-template-columns:repeat(4,1fr)}}
.quota-summary .qs-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:14px 10px;text-align:center;box-shadow:var(--shadow-xs)}
.quota-summary .qs-num{font-size:1.6rem;font-weight:700;line-height:1}
.quota-summary .qs-label{font-size:.72rem;color:var(--ink-muted);margin-top:2px;text-transform:uppercase;letter-spacing:.04em}
.quota-board{padding:0 var(--sp-md) var(--sp-md)}
.quota-col-header{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:var(--sp-sm);padding:var(--sp-sm) 12px;font-size:.72rem;color:var(--ink-muted);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--border)}
.quota-row{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:var(--sp-sm);align-items:center;padding:10px 12px;border-bottom:1px solid var(--border);font-size:.84rem;transition:background var(--duration)}
.quota-row:hover{background:var(--card)}
.quota-row .qr-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500}
.quota-row .qr-bar{height:6px;border-radius:3px;background:var(--border-hover);overflow:hidden;min-width:60px}
.quota-row .qr-bar-fill{height:100%;border-radius:3px;transition:width .3s}
.quota-row .qr-status{font-size:.78rem;font-weight:600}
.quota-col-section{padding:var(--sp-md) var(--sp-md) var(--sp-xs);font-size:.84rem;font-weight:600;color:var(--primary);display:flex;align-items:center;gap:6px}
.quota-col-section .qcs-count{font-size:.72rem;color:var(--ink-dim);font-weight:400}
.refresh-info{padding:var(--sp-xs) var(--sp-md) var(--sp-sm);font-size:.72rem;color:var(--ink-dim);text-align:right}

/* ---- Confirm modal ---- */
.confirm-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);backdrop-filter:blur(4px);z-index:200;justify-content:center;align-items:center}
.confirm-overlay[style*="flex"]{animation:fadeIn var(--duration) var(--ease-out)}
.confirm-modal{background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-lg);max-width:380px;width:90%;text-align:center;box-shadow:var(--shadow-xl);animation:fadeIn var(--duration) var(--ease-out)}
.confirm-modal h3{font-size:1.05rem;margin:0 0 var(--sp-sm);color:var(--ink);font-weight:600}
.confirm-modal .confirm-actions{display:flex;gap:var(--sp-sm);justify-content:center;margin-top:var(--sp-md)}
.confirm-modal .confirm-actions button{padding:10px 24px;border:none;border-radius:var(--r-md);font-size:.88rem;font-weight:600;cursor:pointer;min-height:44px;transition:all var(--duration) var(--ease-out)}
.confirm-modal .btn-yes{background:var(--primary);color:var(--bg)}
.confirm-modal .btn-yes:hover{opacity:.85;box-shadow:var(--shadow-sm)}
.confirm-modal .btn-yes:active{transform:translateY(1px)}
.confirm-modal .btn-no{background:var(--border-hover);color:var(--ink)}
.confirm-modal .btn-no:hover{background:var(--card-hover)}

/* ---- Toast (global) ---- */
.toast{position:fixed;bottom:20px;right:20px;padding:12px 20px;border-radius:var(--r-lg);font-size:.88rem;font-weight:600;z-index:300;opacity:0;transform:translateX(20px);transition:all .2s var(--ease-out);pointer-events:none;box-shadow:var(--shadow-lg)}
.toast.show{opacity:1;transform:translateX(0)}
.toast-approve{background:var(--success);color:var(--bg)}
.toast-reject{background:var(--danger);color:#fff}
.toast-export{background:var(--primary);color:var(--bg)}

/* ---- Search bar ---- */
.search-bar{display:flex;gap:var(--sp-sm);padding:var(--sp-sm) var(--sp-md) 0}
.search-bar input{flex:1;padding:10px 14px;border:1px solid var(--border);border-radius:var(--r-md);background:var(--surface);color:var(--ink);font-size:.88rem;outline:none;transition:border-color var(--duration),box-shadow var(--duration);min-height:44px}
.search-bar input:focus{border-color:var(--border-focus);box-shadow:0 0 0 3px rgba(167,139,250,.2)}
.search-bar input::placeholder{color:var(--ink-dim)}
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
_ICON_STATUS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>'
_ICON_EXPORT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
_ICON_SECURITY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'
_ICON_LOGOUT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>'

_ICON_QUOTA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>'
_ICON_GROK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/></svg>'
_ICON_GALLERY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>'
_ICON_SHIELD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'
_ICON_KNOWLEDGE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>'


_ICON_SETTINGS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>'

def _nav(*, active: str = "queue") -> str:
    links = [
        ("review", "Review", "/review", _ICON_QUEUE),
        ("knowledge", "Knowledge", "/knowledge", _ICON_KNOWLEDGE),
        ("gallery", "Gallery", "/gallery", _ICON_GALLERY),
        ("security", "Security", "/security", _ICON_SECURITY),
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

    body = f"""{_nav(active="queue")}
<h1 style="padding:16px 16px 0;font-size:1.2rem">{_html.escape(heading)}</h1>
<div class="tabs">{tab_html}</div>
<div class="search-bar"><input type="text" id="search-input" placeholder="Search proposals…" oninput="filterCards()"></div>
<div class="card-grid" id="card-grid">{cards}</div>
<script>
function filterCards(){{
  var q = document.getElementById('search-input').value.toLowerCase();
  var cards = document.querySelectorAll('#card-grid .card');
  cards.forEach(function(c){{
    c.style.display = c.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
</script>
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
  var overlay = document.getElementById('confirm-overlay');
  var modal = document.getElementById('confirm-modal');
  var modalTitle = document.getElementById('confirm-title');
  var modalBtn = document.getElementById('confirm-action-btn');
  modalTitle.textContent = actionName + '?';
  modalBtn.onclick = function() {
    overlay.style.display = 'none';
    var btn = document.querySelector('.action-bar .btn:focus, .action-bar .btn:hover') || document.activeElement;
    if (btn) btn.disabled = true;
    fetch(url, {method:'POST',headers:{'Content-Type':'application/json'}})
      .then(function(r){ return r.json(); })
      .then(function(data){
        if (data.next_id) {
          window.location.href = '/review/' + data.next_id;
        } else {
          window.location.href = '/review';
        }
      })
      .catch(function(e){
        showToast('Error: ' + e.message, 'reject');
        if (btn) btn.disabled = false;
      });
  };
  overlay.style.display = 'flex';
  modalBtn.focus();
}
function hideConfirm() {
  document.getElementById('confirm-overlay').style.display = 'none';
}
function showToast(msg, type) {
  var t = document.createElement('div');
  t.className = 'toast toast-' + (type||'approve');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(function(){ t.classList.add('show'); },10);
  setTimeout(function(){ t.classList.remove('show'); setTimeout(function(){ t.remove(); },300); },2500);
}
document.addEventListener('keydown', function(e){
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  var btns = document.querySelectorAll('.action-bar .btn');
  if (e.key === 'a' || e.key === 'A') { if(btns[0]) btns[0].click(); }
  else if (e.key === 's' || e.key === 'S') { if(btns[1]) btns[1].click(); }
  else if (e.key === 'r' || e.key === 'R') { if(btns[2]) btns[2].click(); }
  else if (e.key === 'p' || e.key === 'P') { if(btns[1] && btns[1].textContent.includes('Promote')) btns[1].click(); }
  else if (e.key === 'Escape') { hideConfirm(); }
});
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

    weight = str(proposal.get("weight", ""))
    weight_html = f'<span class="label">Weight</span><span class="value">{_html.escape(weight)}</span>' if weight else ''

    # Action buttons
    btns = ""
    if is_pending or is_approved_db:
        btns += (
            f'<button class="btn btn-approve" onclick="act(\'/api/review/{_html.escape(pid)}/approve-db-only?state={_html.escape(state)}\',\'存入记忆库\')">'
            '✓ Approve <kbd>A</kbd></button>'
        )
        btns += (
            f'<button class="btn btn-export" onclick="act(\'/api/review/{_html.escape(pid)}/approve-for-export?state={_html.escape(state)}\',\'批准并同步导出\')">'
            '↗ Approve & Sync <kbd>S</kbd></button>'
        )
    if is_approved_db:
        btns += (
            f'<button class="btn btn-export" onclick="act(\'/api/review/{_html.escape(pid)}/promote-to-export?state={_html.escape(state)}\',\'升级为同步导出\')">'
            '⬆ Promote <kbd>P</kbd></button>'
        )
    if is_pending or is_approved_db:
        btns += (
            f'<button class="btn btn-reject" onclick="act(\'/api/review/{_html.escape(pid)}/reject?state={_html.escape(state)}\',\'拒绝此提案\')">'
            '✕ Reject <kbd>R</kbd></button>'
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
  {weight_html}
</div>
<div class="detail-body">{sections_html}</div>
<div class="action-bar">{btns}</div>
<div class="confirm-overlay" id="confirm-overlay" onclick="if(event.target===this)hideConfirm()">
  <div class="confirm-modal">
    <h3 id="confirm-title"></h3>
    <div class="confirm-actions">
      <button class="btn-yes" id="confirm-action-btn">Confirm</button>
      <button class="btn-no" onclick="hideConfirm()">Cancel</button>
    </div>
  </div>
</div>
"""
    return _page(f"Proposal {pid[:12]}", body, extra_js=_ACTION_JS)


# ---------------------------------------------------------------------------
# Dashboard page
# ---------------------------------------------------------------------------

def login_page(*, error: str = "") -> str:
    """Render a username/password login form that sets a session cookie."""
    error_html = f'<p style="color:var(--danger);text-align:center;margin-bottom:12px">{_html.escape(error)}</p>' if error else ""
    body = f"""<div style="display:flex;align-items:center;justify-content:center;min-height:100vh;padding:16px">
<div style="background:var(--card);border-radius:var(--r-md);padding:32px 24px;max-width:360px;width:100%;border:1px solid var(--card-hover)">
  <h1 style="text-align:center;color:var(--primary);margin-bottom:24px;font-size:1.4rem">🧠 Hermes</h1>
  {error_html}
  <form method="POST" action="/login">
    <label style="display:block;margin-bottom:8px;color:var(--ink-muted);font-size:.85rem">Username</label>
    <input type="text" name="username" autocomplete="username"
      style="width:100%;padding:12px;border:1px solid var(--card-hover);border-radius:var(--r-md);
             background:var(--surface);color:var(--ink);font-size:1rem;margin-bottom:16px;min-height:48px"
      placeholder="Username" autofocus>
    <label style="display:block;margin-bottom:8px;color:var(--ink-muted);font-size:.85rem">Password</label>
    <input type="password" name="password" autocomplete="current-password"
      style="width:100%;padding:12px;border:1px solid var(--card-hover);border-radius:var(--r-md);
             background:var(--surface);color:var(--ink);font-size:1rem;margin-bottom:20px;min-height:48px"
      placeholder="Password">
    <button type="submit"
      style="width:100%;padding:14px;border:none;border-radius:var(--r-md);
             background:var(--primary);color:var(--bg);font-size:1rem;font-weight:600;cursor:pointer;min-height:48px">
      Sign In
    </button>
  </form>
  <p style="text-align:center;margin-top:16px;font-size:.75rem;color:var(--ink-dim)">
    API: <code style="background:var(--card-hover);padding:2px 6px;border-radius:4px">Authorization: Bearer &lt;token&gt;</code>
  </p>
</div>
</div>"""
    return _page("Hermes Login", body)


def gallery_page() -> str:
    """Render the plotting library gallery page with interactive actions."""
    import yaml, json as _json, os as _os
    _plotting_dir = os.environ.get("BRAIN_PLOTTING_DIR", "")
    _catalog_path = _os.path.join(_plotting_dir, "catalog.yaml")

    try:
        with open(_catalog_path) as _f:
            _catalog = yaml.safe_load(_f)
    except Exception:
        _catalog = {"charts": []}

    # Build demo/interactive maps from catalog (no hardcoded dicts needed)
    _demo_files = {}
    _interactive_files = {}
    for _c in _catalog.get("charts", []):
        _n = _c.get("name", "")
        if _c.get("demo"):
            # Verify file exists
            if _os.path.exists(_os.path.join(_plotting_dir, _c["demo"])):
                _demo_files[_n] = _c["demo"]
        if _c.get("interactive"):
            if _os.path.exists(_os.path.join(_plotting_dir, _c["interactive"])):
                _interactive_files[_n] = _c["interactive"]

    all_tags = set()
    chart_cards = ""
    for c in _catalog.get("charts", []):
        name = c.get("name", "")
        title = c.get("title", name)
        desc = c.get("description", "")
        tags = c.get("tags", [])
        tpl_path = c.get("template", "")
        has_template = (
            _os.path.exists(_os.path.join(_plotting_dir, "templates", f"{name}.py"))
            or (tpl_path and _os.path.exists(_os.path.join(_plotting_dir, tpl_path)))
        )
        img_file = _demo_files.get(name)
        interactive_file = _interactive_files.get(name)

        for t in tags:
            all_tags.add(t)

        card_class = "has-demo" if img_file else "no-demo"
        badges = '<span class="gallery-badge green">Template</span>' if has_template else '<span class="gallery-badge orange">Planned</span>'
        if interactive_file:
            badges += ' <span class="gallery-badge blue">Interactive</span>'

        if img_file:
            img_url = f"/gallery/static/{img_file}"
            preview = f'<div class="card-img"><img src="{img_url}" onclick="openModal(this)" loading="lazy"></div>'
        else:
            preview = '<div class="card-img" style="color:#484f58;font-size:13px;">Preview not available</div>'

        tags_html = "".join(f'<span class="tag">{_html.escape(t)}</span>' for t in tags[:4])

        safe_name = _html.escape(name)
        interactive_btn = (
            f'<button class="btn-act btn-interactive" onclick="openInteractive(\'{safe_name}\')">↗ Interactive</button>'
            if interactive_file else ""
        )
        actions = (
            f'<div class="card-actions">'
            f'<button class="btn-act btn-ok" onclick="feedback(\'{safe_name}\',\'approve\')">✓ Approve</button>'
            f'<button class="btn-act btn-edit" onclick="feedback(\'{safe_name}\',\'suggest\')">✎ Suggest</button>'
            f'<button class="btn-act btn-no" onclick="feedback(\'{safe_name}\',\'reject\')">✕ Reject</button>'
            f'{interactive_btn}'
            f'</div>' if img_file else ""
        )

        chart_cards += (
            f'<div class="gallery-card {card_class}" data-tags="{" ".join(tags)}">'
            f'{badges}{preview}'
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
.gallery-header h1 { color: var(--ink); font-size: 24px; }
.gallery-header p { color: var(--ink-dim); font-size: 14px; }
.filter-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }
.filter-btn { background: var(--card); border: 1px solid var(--card-hover); color: var(--ink-dim); padding: 6px 16px; border-radius: 20px; cursor: pointer; font-size: 12px; transition: all 0.2s; }
.filter-btn:hover, .filter-btn.active { background: var(--card-hover); border-color: var(--primary); color: var(--primary); }
.gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.gallery-card { background: var(--card); border: 1px solid var(--card-hover); border-radius: 8px; overflow: hidden; transition: all 0.3s; position: relative; }
.gallery-card:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(189,147,249,0.15); }
.gallery-card.has-demo { border-left: 3px solid var(--success); }
.gallery-card.no-demo { border-left: 3px solid var(--ink-dim); opacity: 0.7; }
.card-img { background: var(--bg); min-height: 180px; display: flex; align-items: center; justify-content: center; padding: 8px; cursor: pointer; border-bottom: 1px solid var(--card-hover); }
.card-img img { max-width: 100%; max-height: 200px; object-fit: contain; }
.card-info { padding: 12px 14px; }
.card-info h3 { font-size: 14px; color: var(--ink); margin: 0 0 4px; }
.card-info .desc { font-size: 13px; color: var(--ink-dim); margin-bottom: 8px; line-height: 1.4; }
.card-info .tags { display: flex; gap: 6px; flex-wrap: wrap; }
.card-info .tag { font-size: 11px; background: var(--card-hover); border: 1px solid var(--card-hover); color: var(--ink-dim); padding: 1px 8px; border-radius: 10px; }
.gallery-badge { position: absolute; top: 8px; right: 8px; font-size: 10px; padding: 2px 8px; border-radius: 10px; }
.gallery-badge.green { background: rgba(80,250,123,.3); color: var(--success); }
.gallery-badge.orange { background: rgba(255,184,108,.3); color: var(--orange); }
.gallery-badge.blue { background: rgba(139,233,253,.3); color: var(--info); }
.card-actions { display: flex; gap: 6px; padding: 8px 14px 12px; border-top: 1px solid var(--card-hover); }
.btn-act { border: 1px solid var(--card-hover); border-radius: 4px; padding: 4px 10px; font-size: 11px; cursor: pointer; transition: all 0.2s; background: var(--card); color: var(--ink-dim); }
.btn-ok:hover { background: rgba(80,250,123,.2); border-color: var(--success); color: var(--success); }
.btn-edit:hover { background: rgba(189,147,249,.2); border-color: var(--primary); color: var(--primary); }
.btn-no:hover { background: rgba(255,85,85,.2); border-color: var(--danger); color: var(--danger); }
.btn-interactive { border-color: var(--primary); color: var(--primary); }
.btn-interactive:hover { background: rgba(189,147,249,.2); border-color: var(--primary); color: var(--ink); }
.modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 1000; justify-content: center; align-items: center; }
.modal-overlay.show { display: flex; }
.modal-overlay img { max-width: 90vw; max-height: 85vh; object-fit: contain; background: var(--card); border-radius: 4px; }
.modal-overlay .close { position: absolute; top: 20px; right: 30px; color: var(--ink); font-size: 28px; cursor: pointer; }
.iframe-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1100; }
.iframe-modal.show { display: flex; flex-direction: column; }
.iframe-modal .iframe-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 20px; background: var(--surface); border-bottom: 1px solid var(--card-hover); }
.iframe-modal .iframe-header h3 { color: var(--ink); font-size: 16px; margin: 0; }
.iframe-modal .iframe-close { color: var(--ink-dim); font-size: 24px; cursor: pointer; padding: 0 8px; }
.iframe-modal .iframe-close:hover { color: var(--danger); }
.iframe-modal iframe { flex: 1; border: none; width: 100%; }
.toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 20px; border-radius: 8px; color: var(--bg); font-size: 14px; z-index: 2000; opacity: 0; transition: opacity 0.3s; pointer-events: none; }
.toast.show { opacity: 1; }
.toast.approve { background: var(--success); }
.toast.suggest { background: var(--primary); }
.toast.reject { background: var(--danger); }
.suggest-input { margin: 6px 14px 10px; }
.suggest-input textarea { width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--card-hover); background: var(--bg); color: var(--ink); font-size: 13px; min-height: 60px; resize: vertical; box-sizing: border-box; }
.suggest-input textarea:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 2px rgba(189,147,249,.3); }
.suggest-input button { margin-top: 4px; padding: 4px 12px; border-radius: 4px; background: var(--primary); color: var(--bg); border: none; font-size: 12px; cursor: pointer; }
</style>
'''

    body = (
        gallery_css +
        f'{_nav(active="gallery")}'
        '<div class="gallery-container">'
        '<div class="gallery-header"><h1>Sci-Fig Gallery</h1>'
        '<p>View demo charts, approve / suggest / reject to iterate templates.</p></div>'
        '<div class="filter-bar">' + filter_btns + '</div>'
        '<div class="gallery-grid">' + chart_cards + '</div>'
        '<div class="modal-overlay" id="modal" onclick="closeModal()"><span class="close">&times;</span>'
        '<img id="modal-img" src=""></div>'
        '<div class="iframe-modal" id="iframe-modal">'
        '<div class="iframe-header"><h3 id="iframe-title">Interactive Chart</h3><span class="iframe-close" onclick="closeInteractive()">&times;</span></div>'
        '<iframe id="iframe-chart" src="" sandbox="allow-scripts allow-same-origin"></iframe>'
        '</div>'
        '<div class="toast" id="toast"></div>'
        '</div>'
    )

    gallery_js = """
// Interactive chart URL mapping (name -> HTML path)
var INTERACTIVE_MAP = %s;

function openModal(img) {
  document.getElementById('modal-img').src = img.src;
  document.getElementById('modal').classList.add('show');
}
function closeModal() {
  document.getElementById('modal').classList.remove('show');
}
function openInteractive(name) {
  var url = INTERACTIVE_MAP[name];
  if (!url) { showToast('No interactive version available', 'reject'); return; }
  document.getElementById('iframe-title').textContent = 'Interactive: ' + name;
  document.getElementById('iframe-chart').src = '/gallery/static/' + url;
  document.getElementById('iframe-modal').classList.add('show');
}
function closeInteractive() {
  document.getElementById('iframe-modal').classList.remove('show');
  document.getElementById('iframe-chart').src = '';
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

    return _page("Sci-Fig Gallery", body, extra_js=gallery_js % _json.dumps(_interactive_files))


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
        bar_color = "var(--success)" if cnt / max_cnt < 0.3 else "var(--orange)" if cnt / max_cnt < 0.7 else "var(--danger)"
        attacker_rows += f"""<div class="sec-bar-row">
  <span class="sec-ip">{ip}</span>
  <div class="sec-bar-bg"><div class="sec-bar-fill" style="width:{bar_w:.0f}%;background:{bar_color}"></div></div>
  <span class="sec-cnt">{cnt}</span>
</div>"""

    # Build UFW rule rows for a given server
    def _ufw_rows(rules):
        rows = ""
        for r in rules:
            action = _html.escape(r.get("action", "?"))
            to = _html.escape(r.get("to", "?"))
            comment = _html.escape(r.get("comment", ""))
            ucolor = "var(--success)" if action == "ALLOW" else "var(--danger)" if action in ("REJECT", "DENY") else "var(--ink-dim)"
            rows += f"""<div class="sec-ufw-row">
  <span class="sec-ufw-action" style="color:{ucolor}">{action}</span>
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
<button class="sec-refresh-btn" id="pause-btn" onclick="toggleRefresh()" title="Pause auto-refresh">⏸</button>
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
var _secTimer = null;
var _secPaused = false;
function toggleRefresh() {{
  if (_secPaused) {{
    _secPaused = false;
    document.getElementById('refresh-indicator').textContent = '⟳ Live';
    document.getElementById('pause-btn').textContent = '⏸';
    _secTimer = setTimeout(function(){{ location.reload(); }}, 30000);
  }} else {{
    _secPaused = true;
    document.getElementById('refresh-indicator').textContent = '⏸ Paused';
    document.getElementById('pause-btn').textContent = '▶';
    if (_secTimer) clearTimeout(_secTimer);
  }}
}}
_secTimer = setTimeout(function(){{ location.reload(); }}, 30000);
</script>

<style>
.sec-header{{display:flex;align-items:center;justify-content:space-between;padding:12px 16px 0}}
.sec-header h1{{font-size:1.2rem;margin:0}}
.sec-refresh{{font-size:.78rem;color:var(--ink-dim);animation:pulse 2s infinite}}
.sec-refresh-btn{{background:none;border:1px solid var(--card-hover);border-radius:4px;color:var(--ink-dim);padding:2px 6px;cursor:pointer;font-size:.85rem;margin-left:8px}}
.sec-refresh-btn:hover{{background:var(--card-hover);color:var(--ink)}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.sec-kanban{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 16px 16px}}
@media(max-width:720px){{.sec-kanban{{grid-template-columns:1fr}}}}
.sec-col{{min-width:0}}
.sec-col h3{{font-size:1rem;margin:12px 0 6px;color:var(--primary)}}
.sec-col h4{{font-size:.85rem;margin:10px 0 4px;color:var(--ink-muted)}}
.sec-card{{background:var(--card);border-radius:var(--r-md);padding:10px 12px;margin-bottom:8px}}
.sec-overview{{background:var(--card-hover);border-radius:var(--r-md)}}
.sec-empty{{color:var(--ink-dim);font-size:.82rem;font-style:italic}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}}
.dot-green{{background:var(--success)}}
.dot-red{{background:var(--danger)}}
.sec-badge{{font-size:.7rem;padding:2px 7px;border-radius:10px;background:var(--card-hover);color:var(--ink-dim);margin-left:6px}}
.sec-badge-red{{background:var(--danger);color:#fff}}
.sec-stat-row{{display:flex;justify-content:space-between;padding:3px 0;font-size:.88rem;border-bottom:1px solid var(--card-hover)}}
.sec-stat-row:last-child{{border-bottom:none}}
.sec-bar-row{{display:flex;align-items:center;gap:8px;padding:3px 0;font-size:.82rem}}
.sec-ip{{min-width:130px;color:var(--ink-dim);font-family:monospace;font-size:.78rem}}
.sec-bar-bg{{flex:1;height:6px;background:var(--card-hover);border-radius:3px;overflow:hidden}}
.sec-bar-fill{{height:100%;background:var(--danger);border-radius:3px}}
.sec-cnt{{min-width:40px;text-align:right;color:var(--ink-dim);font-size:.78rem}}
.sec-ufw-row{{display:flex;align-items:center;gap:6px;padding:3px 0;font-size:.82rem;border-bottom:1px solid var(--card-hover)}}
.sec-ufw-row:last-child{{border-bottom:none}}
.sec-ufw-action{{min-width:48px;font-weight:600;font-size:.78rem}}
.sec-ufw-to{{min-width:90px;font-family:monospace;font-size:.78rem}}
.sec-ufw-comment{{color:var(--ink-dim);font-size:.75rem}}
.sec-inbound-card{{background:var(--card);border-radius:var(--r-md);padding:10px 12px;margin-bottom:8px}}
.sec-inbound-header{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.sec-inbound-name{{font-weight:600;font-size:.92rem}}
.sec-inbound-meta{{font-size:.78rem;color:var(--ink-dim);font-family:monospace}}
.sec-inbound-traffic{{font-size:.78rem;color:var(--info);margin-left:auto}}
.sec-inbound-clients{{margin-top:6px;padding-left:14px}}
.sec-client-row{{display:flex;align-items:center;gap:6px;padding:2px 0;font-size:.82rem}}
.sec-client-name{{min-width:120px}}
.sec-client-traffic{{color:var(--ink-dim);font-size:.78rem;font-family:monospace}}
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
.settings-section{{background:var(--card);border-radius:var(--r-md);padding:16px 20px;margin-bottom:16px;border:1px solid var(--card-hover)}}
.settings-section h3{{color:var(--primary);font-size:.95rem;margin:0 0 12px}}
.settings-form{{display:flex;flex-direction:column;gap:10px;max-width:400px}}
.settings-label{{font-size:.85rem;color:var(--ink-muted);margin-top:4px}}
.settings-input{{background:var(--surface);border:1px solid var(--card-hover);border-radius:var(--r-md);padding:10px 12px;color:var(--ink);font-size:.95rem;outline:none;transition:border-color .15s,box-shadow .15s}}
.settings-input:focus{{border-color:var(--primary);box-shadow:0 0 0 2px rgba(189,147,249,.3)}}
.settings-btn{{background:var(--primary);color:var(--surface);border:none;border-radius:var(--r-md);padding:12px;font-size:.95rem;font-weight:600;cursor:pointer;transition:opacity .15s;margin-top:4px}}
.settings-btn:hover{{opacity:.85}}
.settings-error{{background:rgba(255,85,85,.15);color:var(--danger);padding:8px 12px;border-radius:var(--r-md);font-size:.9rem;margin-bottom:8px}}
.settings-success{{background:rgba(80,250,123,.15);color:var(--success);padding:8px 12px;border-radius:var(--r-md);font-size:.9rem;margin-bottom:8px}}
.settings-info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.settings-info-item{{background:var(--card-hover);border-radius:var(--r-md);padding:12px}}
.settings-info-label{{display:block;font-size:.75rem;color:var(--ink-muted);text-transform:uppercase;letter-spacing:.04em}}
.settings-info-value{{display:block;font-size:1.1rem;font-weight:600;color:var(--ink);margin-top:2px}}
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


# ---------------------------------------------------------------------------
# Knowledge Tree page
# ---------------------------------------------------------------------------

_STAGE_BADGE_MAP_KN = {
    "draft": "badge-pending",
    "refined": "badge-pattern",
    "verified": "badge-approved_db_only",
    "canonized": "badge-approved_for_export",
    "deprecated": "badge-superseded",
}

def _stage_badge_knowledge(stage: str) -> str:
    cls = _STAGE_BADGE_MAP_KN.get(stage, "badge-pending")
    return f'<span class="badge {cls}">{_html.escape(stage)}</span>'

# Stage badge mapping (knowledge lifecycle)
_STAGE_BADGE_MAP = {
    "draft": "badge-pending",
    "refined": "badge-pattern",
    "verified": "badge-approved_db_only",
    "canonized": "badge-approved_for_export",
    "deprecated": "badge-superseded",
}

_STAGE_LABEL = {
    "draft": "Draft",
    "refined": "Refined",
    "verified": "Verified",
    "canonized": "Canonized",
    "deprecated": "Deprecated",
}

# Category badge (reuse existing _CATEGORY_BADGE_MAP + extras)
_KN_CATEGORY_BADGE_MAP = {
    "rule": "badge-rule",
    "pattern": "badge-pattern",
    "insight": "badge-insight",
    "warning": "badge-warning",
    "workflow": "badge-approved_db_only",
    "preference": "badge-pending",
    "fact": "badge-pattern",
}


def _stage_badge(stage: str) -> str:
    cls = _STAGE_BADGE_MAP.get(stage, "badge-pending")
    label = _STAGE_LABEL.get(stage, stage.title())
    return f'<span class="badge {cls}">{_html.escape(label)}</span>'


def _kn_category_badge(category: str) -> str:
    cls = _KN_CATEGORY_BADGE_MAP.get(category, "badge-rule")
    return f'<span class="badge {cls}">{_html.escape(category)}</span>'


def _confidence_bar(confidence: float) -> str:
    """Render a horizontal confidence bar 0-100%."""
    pct = max(0, min(100, int(confidence * 100)))
    if pct >= 70:
        color = "var(--success)"
    elif pct >= 40:
        color = "var(--warning)"
    else:
        color = "var(--danger)"
    return (
        f'<div class="kn-conf-bar">'
        f'<div class="kn-conf-fill" style="width:{pct}%;background:{color}"></div>'
        f'</div>'
        f'<span class="kn-conf-label">{pct}%</span>'
    )


def knowledge_page(
    *,
    nodes: list,
    stage_counts: dict[str, int],
    active_stage: str = "all",
    active_category: str = "",
    active_domain: str = "",
) -> str:
    """Render the knowledge tree browser with stage filters."""
    total = sum(stage_counts.values())
    stages = [
        ("all", "All", total),
        ("draft", "Draft", stage_counts.get("draft", 0)),
        ("refined", "Refined", stage_counts.get("refined", 0)),
        ("verified", "Verified", stage_counts.get("verified", 0)),
        ("canonized", "Canonized", stage_counts.get("canonized", 0)),
        ("deprecated", "Deprecated", stage_counts.get("deprecated", 0)),
    ]
    tab_html = ""
    for key, label, count in stages:
        active_cls = " active" if key == active_stage else ""
        href = f"/knowledge?stage={key}" if key != "all" else "/knowledge"
        tab_html += (
            f'<a href="{href}" class="{active_cls.lstrip()}">'
            f'{_html.escape(label)} <span class="tab-count">{count}</span></a>'
        )

    cards = ""
    for n in nodes:
        nid = str(n.id) if hasattr(n, 'id') else str(n.get("id", ""))
        summary = str(n.summary[:120]) if hasattr(n, 'summary') else str(n.get("summary", ""))[:120]
        category = str(n.category) if hasattr(n, 'category') else str(n.get("category", ""))
        domain = str(n.domain) if hasattr(n, 'domain') else str(n.get("domain", ""))
        stage = str(n.stage) if hasattr(n, 'stage') else str(n.get("stage", ""))
        confidence = n.confidence if hasattr(n, 'confidence') else n.get("confidence", 0)
        source = str(n.source) if hasattr(n, 'source') else str(n.get("source", ""))
        cards += f"""<a href="/knowledge/{_html.escape(nid)}" class="card">
  <div class="card-top">{_category_badge(category)} {_stage_badge_knowledge(stage)}</div>
  <div class="card-preview">{_html.escape(summary)}</div>
  <div class="card-meta">
    <span>{_html.escape(domain)}</span>
    <span>conf: {confidence:.2f}</span>
  </div>
</a>"""

    if not nodes:
        cards = '<div class="empty">No knowledge nodes in this view.</div>'

    body = f"""{_nav(active="knowledge")}
<h1 style="padding:16px 16px 0;font-size:1.2rem">📚 Knowledge Tree</h1>
<div class="tabs">{tab_html}</div>
<div class="search-bar"><input type="text" id="search-input" placeholder="Search knowledge…" oninput="filterCards()"></div>
<div class="card-grid" id="card-grid">{cards}</div>
<script>
function filterCards(){{
  var q = document.getElementById('search-input').value.toLowerCase();
  var cards = document.querySelectorAll('#card-grid .card');
  cards.forEach(function(c){{
    c.style.display = c.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
</script>
"""
    return _page("Hermes Knowledge", body)


def knowledge_tree_page(
    *,
    nodes: list[dict],
    counts: dict[str, int],
    active_stage: str = "all",
    active_category: str = "",
    active_domain: str = "",
    domains: list[str] | None = None,
) -> str:
    """Render the knowledge tree overview with stats bar, filters, and node cards."""
    if domains is None:
        domains = []
    total = sum(counts.values())

    # -- Stats bar --
    stat_cards = [
        ("Total", str(total), "var(--ink)"),
        ("Draft", str(counts.get("draft", 0)), "var(--warning)"),
        ("Refined", str(counts.get("refined", 0)), "var(--info)"),
        ("Verified", str(counts.get("verified", 0)), "var(--success)"),
        ("Canonized", str(counts.get("canonized", 0)), "var(--primary)"),
        ("Deprecated", str(counts.get("deprecated", 0)), "var(--ink-dim)"),
    ]
    stats_html = ""
    for label, num, color in stat_cards:
        stats_html += (
            f'<div class="dash-card">'
            f'<div class="num" style="color:{color}">{num}</div>'
            f'<div class="label">{_html.escape(label)}</div>'
            f'</div>'
        )

    # -- Stage filter tabs --
    stage_tabs = [
        ("all", "All", total),
        ("draft", "Draft", counts.get("draft", 0)),
        ("refined", "Refined", counts.get("refined", 0)),
        ("verified", "Verified", counts.get("verified", 0)),
        ("canonized", "Canonized", counts.get("canonized", 0)),
        ("deprecated", "Deprecated", counts.get("deprecated", 0)),
    ]
    tab_html = ""
    for key, label, count in stage_tabs:
        active_cls = " active" if key == active_stage else ""
        href = f"/knowledge?stage={key}" if key != "all" else "/knowledge"
        if active_category:
            href += f"&category={active_category}"
        if active_domain:
            href += f"&domain={active_domain}"
        tab_html += (
            f'<a href="{href}" class="{active_cls.lstrip()}">'
            f'{_html.escape(label)} <span class="tab-count">{count}</span></a>'
        )

    # -- Category options for filter --
    cat_options = '<option value="">All Categories</option>'
    for cat in sorted(_KN_CATEGORY_BADGE_MAP):
        sel = ' selected' if cat == active_category else ''
        cat_options += f'<option value="{_html.escape(cat)}"{sel}>{_html.escape(cat.title())}</option>'

    # -- Domain options for filter --
    dom_options = '<option value="">All Domains</option>'
    for dom in sorted(domains):
        sel = ' selected' if dom == active_domain else ''
        dom_options += f'<option value="{_html.escape(dom)}"{sel}>{_html.escape(dom)}</option>'

    # -- Node cards grouped by domain --
    # Group nodes by domain for collapsible sections
    domain_groups: dict[str, list] = {}
    for n in nodes:
        domain = str(n.get("domain", "general"))
        domain_groups.setdefault(domain, []).append(n)

    _domain_icons = {"devops": "🔧", "network": "🌐", "apa": "🧬", "general": "📦", "security": "🔒"}
    _domain_order = {"devops": 0, "network": 1, "apa": 2, "security": 3, "general": 99}

    cards_html = ""
    if not nodes:
        cards_html = '<div class="empty">No knowledge nodes match the current filters.</div>'
    else:
        for domain in sorted(domain_groups, key=lambda d: _domain_order.get(d, 50)):
            group = domain_groups[domain]
            icon = _domain_icons.get(domain, "📁")
            # Count by stage within this domain
            stage_counts = {}
            for n in group:
                s = str(n.get("stage", "draft"))
                stage_counts[s] = stage_counts.get(s, 0) + 1
            stage_summary = " · ".join(f"{s}: {c}" for s, c in sorted(stage_counts.items()))

            group_cards = ""
            for n in group:
                nid = str(n.get("id", ""))
                summary = str(n.get("summary", ""))
                stage = str(n.get("stage", "draft"))
                category = str(n.get("category", "fact"))
                ndomain = str(n.get("domain", "general"))
                confidence = float(n.get("confidence", 0))
                source = str(n.get("source", ""))
                retrieval_count = int(n.get("retrieval_count", 0))
                created_at = str(n.get("created_at", ""))[:19]
                preview = summary[:140] + ("..." if len(summary) > 140 else "")

                group_cards += f"""<a href="/knowledge/{_html.escape(nid)}" class="card">
  <div class="card-top">{_stage_badge(stage)} {_kn_category_badge(category)} <span class="badge badge-rule" style="font-size:.65rem">{_html.escape(ndomain)}</span></div>
  <div class="card-preview">{_html.escape(preview)}</div>
  <div style="margin-top:8px;display:flex;align-items:center;gap:8px">
    {_confidence_bar(confidence)}
  </div>
  <div class="card-meta">
    <span>🔍 {retrieval_count} uses</span>
    <span>📁 {_html.escape(source[:30])}</span>
    <span>{_html.escape(created_at)}</span>
  </div>
</a>"""

            cards_html += f"""<div class="kn-domain-group" data-domain="{_html.escape(domain)}">
  <button class="kn-domain-header" onclick="toggleDomain(this)">
    <span class="kn-domain-toggle">▼</span>
    <span class="kn-domain-icon">{icon}</span>
    <span class="kn-domain-name">{_html.escape(domain.title())}</span>
    <span class="kn-domain-count">{len(group)} nodes</span>
    <span class="kn-domain-stages">{_html.escape(stage_summary)}</span>
  </button>
  <div class="kn-domain-cards">{group_cards}</div>
</div>"""

    body = f"""{_nav(active="queue")}
<h1 style="padding:16px 16px 0;font-size:1.2rem">🌳 Knowledge Tree</h1>
<div class="dash-grid">{stats_html}</div>
<div class="tabs">{tab_html}</div>
<div style="padding:0 16px 8px;display:flex;gap:8px;flex-wrap:wrap">
  <form method="get" action="/knowledge" style="display:flex;gap:8px;flex-wrap:wrap;flex:1" id="kn-filter-form">
    <input type="hidden" name="stage" value="{_html.escape(active_stage)}">
    <select name="category" class="kn-filter-select" onchange="this.form.submit()">{cat_options}</select>
    <select name="domain" class="kn-filter-select" onchange="this.form.submit()">{dom_options}</select>
    <input type="text" name="q" placeholder="Search knowledge…" class="kn-search-input" id="kn-search">
  </form>
</div>
<div id="kn-card-grid">{cards_html}</div>

<style>
.kn-filter-select{{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  color:var(--ink);font-size:.84rem;padding:8px 12px;min-height:40px;outline:none;
  transition:border-color var(--duration);cursor:pointer
}}
.kn-filter-select:focus{{border-color:var(--border-focus)}}
.kn-search-input{{
  flex:1;min-width:160px;padding:8px 14px;border:1px solid var(--border);border-radius:var(--r-md);
  background:var(--surface);color:var(--ink);font-size:.84rem;outline:none;min-height:40px;
  transition:border-color var(--duration),box-shadow var(--duration)
}}
.kn-search-input:focus{{border-color:var(--border-focus);box-shadow:0 0 0 3px rgba(167,139,250,.2)}}
.kn-search-input::placeholder{{color:var(--ink-dim)}}
.kn-domain-group{{margin-bottom:8px}}
.kn-domain-header{{
  display:flex;align-items:center;gap:10px;width:100%;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  padding:10px 14px;cursor:pointer;font-size:.9rem;font-weight:600;color:var(--ink);
  transition:background var(--duration),border-color var(--duration)
}}
.kn-domain-header:hover{{background:var(--card-hover);border-color:var(--border-focus)}}
.kn-domain-toggle{{font-size:.7rem;transition:transform .2s ease}}
.kn-domain-group.collapsed .kn-domain-toggle{{transform:rotate(-90deg)}}
.kn-domain-icon{{font-size:1.1rem}}
.kn-domain-name{{flex:1;text-align:left}}
.kn-domain-count{{font-size:.72rem;color:var(--ink-dim);font-weight:400}}
.kn-domain-stages{{font-size:.68rem;color:var(--ink-muted);font-weight:400}}
.kn-domain-cards{{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;
  padding:8px 0 4px;transition:max-height .3s ease,opacity .2s ease;overflow:hidden
}}
.kn-domain-group.collapsed .kn-domain-cards{{max-height:0;opacity:0;padding:0;border:0;pointer-events:none}}
.kn-conf-bar{{
  flex:1;height:6px;background:var(--border-hover);border-radius:3px;overflow:hidden;min-width:60px
}}
.kn-conf-fill{{height:100%;border-radius:3px;transition:width .3s var(--ease-out)}}
.kn-conf-label{{font-size:.72rem;color:var(--ink-muted);font-weight:600;min-width:32px;text-align:right}}
</style>
<script>
(function(){{
  // Search filter
  var input = document.getElementById('kn-search');
  if (input) {{
    input.addEventListener('input', function(){{
      var q = this.value.toLowerCase();
      var cards = document.querySelectorAll('#kn-card-grid .card');
      cards.forEach(function(c){{
        c.style.display = c.textContent.toLowerCase().includes(q) ? '' : 'none';
      }});
      // Show/hide domain groups based on visible cards
      document.querySelectorAll('.kn-domain-group').forEach(function(g){{
        var visible = g.querySelectorAll('.card[style=""], .card:not([style])');
        var allHidden = true;
        g.querySelectorAll('.card').forEach(function(c){{
          if (c.style.display !== 'none') allHidden = false;
        }});
        g.style.display = allHidden ? 'none' : '';
      }});
    }});
  }}
}})();

function toggleDomain(btn) {{
  var group = btn.closest('.kn-domain-group');
  group.classList.toggle('collapsed');
}}
</script>
"""
    return _page("Knowledge Tree", body)


# ---------------------------------------------------------------------------
# Knowledge Detail page
# ---------------------------------------------------------------------------

_KN_ACTION_JS = """\
function knAct(url, actionName, successMsg) {
  var overlay = document.getElementById('confirm-overlay');
  var modal = document.getElementById('confirm-modal');
  var modalTitle = document.getElementById('confirm-title');
  var modalBtn = document.getElementById('confirm-action-btn');
  modalTitle.textContent = actionName + '?';
  modalBtn.onclick = function() {
    overlay.style.display = 'none';
    fetch(url, {method:'POST',headers:{'Content-Type':'application/json'}})
      .then(function(r){ return r.json(); })
      .then(function(data){
        showToast(successMsg || 'Done', 'approve');
        setTimeout(function(){ location.reload(); }, 800);
      })
      .catch(function(e){
        showToast('Error: ' + e.message, 'reject');
      });
  };
  overlay.style.display = 'flex';
  modalBtn.focus();
}
function knDeprecate(url) {
  knAct(url, 'Deprecate this knowledge node', 'Node deprecated');
}
function knPromote(url) {
  knAct(url, 'Promote to next stage', 'Stage updated');
}
function knMerge(url, actionName) {
  knAct(url, actionName || 'Merge nodes', 'Nodes merged');
}
function hideConfirm() {
  document.getElementById('confirm-overlay').style.display = 'none';
}
function showToast(msg, type) {
  var t = document.createElement('div');
  t.className = 'toast toast-' + (type||'approve');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(function(){ t.classList.add('show'); },10);
  setTimeout(function(){ t.classList.remove('show'); setTimeout(function(){ t.remove(); },300); },2500);
}
document.addEventListener('keydown', function(e){
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'Escape') { hideConfirm(); }
});
"""


def knowledge_detail_page(
    *,
    node: dict,
    thought_chains: list[dict] | None = None,
    parent_node: dict | None = None,
    child_nodes: list[dict] | None = None,
    supersedes_node: dict | None = None,
    superseded_by: list[dict] | None = None,
    contradicts_nodes: list[dict] | None = None,
) -> str:
    """Render the full detail view for a knowledge node with relationships, thought chain, and actions."""
    if thought_chains is None:
        thought_chains = []
    if child_nodes is None:
        child_nodes = []
    if superseded_by is None:
        superseded_by = []
    if contradicts_nodes is None:
        contradicts_nodes = []

    nid = str(node.get("id", ""))
    summary = str(node.get("summary", ""))
    content = str(node.get("content", ""))
    stage = str(node.get("stage", "draft"))
    category = str(node.get("category", "fact"))
    domain = str(node.get("domain", "general"))
    operation = str(node.get("operation", ""))
    confidence = float(node.get("confidence", 0))
    source = str(node.get("source", ""))
    evidence_raw = str(node.get("evidence", "[]"))
    merged_from_raw = str(node.get("merged_from", "[]"))
    contradicts_raw = str(node.get("contradicts", "[]"))
    verified_by_raw = str(node.get("verified_by", "[]"))
    created_at = str(node.get("created_at", ""))[:19]
    refined_at = str(node.get("refined_at", ""))[:19] if node.get("refined_at") else ""
    verified_at = str(node.get("verified_at", ""))[:19] if node.get("verified_at") else ""
    deprecated_at = str(node.get("deprecated_at", ""))[:19] if node.get("deprecated_at") else ""
    retrieval_count = int(node.get("retrieval_count", 0))
    last_used_at = str(node.get("last_used_at", ""))[:19] if node.get("last_used_at") else ""
    correction_count = int(node.get("correction_count", 0))

    # -- Confidence bar (larger, detail view) --
    pct = max(0, min(100, int(confidence * 100)))
    if pct >= 70:
        conf_color = "var(--success)"
    elif pct >= 40:
        conf_color = "var(--warning)"
    else:
        conf_color = "var(--danger)"
    confidence_html = (
        f'<div style="display:flex;align-items:center;gap:12px">'
        f'<div style="flex:1;height:10px;background:var(--border-hover);border-radius:5px;overflow:hidden">'
        f'<div style="width:{pct}%;height:100%;background:{conf_color};border-radius:5px;transition:width .4s var(--ease-out)"></div>'
        f'</div>'
        f'<span style="font-size:1.1rem;font-weight:700;color:{conf_color}">{pct}%</span>'
        f'</div>'
    )

    # -- Evidence list --
    import json as _json
    try:
        evidence_list = _json.loads(evidence_raw) if evidence_raw else []
    except Exception:
        evidence_list = []
    evidence_html = ""
    for ev in evidence_list:
        evidence_html += f'<div style="padding:4px 0;font-size:.88rem;color:var(--ink);border-bottom:1px solid var(--border)">• {_html.escape(str(ev))}</div>'
    if not evidence_html:
        evidence_html = '<div style="color:var(--ink-dim);font-style:italic">No evidence recorded</div>'

    # -- Merged from / Contradicts / Verified by --
    try:
        merged_list = _json.loads(merged_from_raw) if merged_from_raw else []
    except Exception:
        merged_list = []
    try:
        contradict_list = _json.loads(contradicts_raw) if contradicts_raw else []
    except Exception:
        contradict_list = []
    try:
        verified_list = _json.loads(verified_by_raw) if verified_by_raw else []
    except Exception:
        verified_list = []

    def _id_list_html(items: list, base_url: str = "/knowledge/") -> str:
        if not items:
            return '<span style="color:var(--ink-dim);font-style:italic">None</span>'
        parts = []
        for item_id in items:
            sid = _html.escape(str(item_id))
            parts.append(f'<a href="{base_url}{sid}" style="font-family:var(--font-mono);font-size:.82rem">{sid[:16]}…</a>')
        return " ".join(parts)

    # -- Relationships section --
    rel_cards = ""

    if parent_node:
        pid = str(parent_node.get("id", ""))[:16]
        psummary = str(parent_node.get("summary", ""))[:60]
        rel_cards += f"""<a href="/knowledge/{_html.escape(str(parent_node.get('id', '')))}" class="kn-rel-card">
  <span class="kn-rel-type">⬆ Parent</span>
  <span class="kn-rel-summary">{_html.escape(psummary)}</span>
  <span class="kn-rel-id">{_html.escape(pid)}…</span>
</a>"""

    if supersedes_node:
        sid = str(supersedes_node.get("id", ""))[:16]
        ssummary = str(supersedes_node.get("summary", ""))[:60]
        rel_cards += f"""<a href="/knowledge/{_html.escape(str(supersedes_node.get('id', '')))}" class="kn-rel-card">
  <span class="kn-rel-type">⬅ Supersedes</span>
  <span class="kn-rel-summary">{_html.escape(ssummary)}</span>
  <span class="kn-rel-id">{_html.escape(sid)}…</span>
</a>"""

    for child in child_nodes:
        cid = str(child.get("id", ""))[:16]
        csummary = str(child.get("summary", ""))[:60]
        rel_cards += f"""<a href="/knowledge/{_html.escape(str(child.get('id', '')))}" class="kn-rel-card">
  <span class="kn-rel-type">⬇ Child</span>
  <span class="kn-rel-summary">{_html.escape(csummary)}</span>
  <span class="kn-rel-id">{_html.escape(cid)}…</span>
</a>"""

    for sup in superseded_by:
        sid2 = str(sup.get("id", ""))[:16]
        ssummary2 = str(sup.get("summary", ""))[:60]
        rel_cards += f"""<a href="/knowledge/{_html.escape(str(sup.get('id', '')))}" class="kn-rel-card">
  <span class="kn-rel-type">➡ Superseded by</span>
  <span class="kn-rel-summary">{_html.escape(ssummary2)}</span>
  <span class="kn-rel-id">{_html.escape(sid2)}…</span>
</a>"""

    for con in contradicts_nodes:
        conid = str(con.get("id", ""))[:16]
        cons = str(con.get("summary", ""))[:60]
        rel_cards += f"""<a href="/knowledge/{_html.escape(str(con.get('id', '')))}" class="kn-rel-card">
  <span class="kn-rel-type">⚡ Contradicts</span>
  <span class="kn-rel-summary">{_html.escape(cons)}</span>
  <span class="kn-rel-id">{_html.escape(conid)}…</span>
</a>"""

    if not rel_cards:
        rel_cards = '<div style="color:var(--ink-dim);font-style:italic;padding:8px 0">No relationships</div>'

    # -- Thought chain timeline --
    _ACTION_ICON = {
        "dedup_check": "🔍",
        "merge": "🔗",
        "refine": "✏️",
        "contradiction_detect": "⚡",
        "canonize": "✅",
        "deprecate": "🗑️",
        "create": "🆕",
    }
    _DECISION_COLOR = {
        "create": "var(--success)",
        "merge": "var(--primary)",
        "refine": "var(--info)",
        "ignore": "var(--ink-dim)",
        "flag_contradiction": "var(--danger)",
        "canonize": "var(--success)",
        "deprecate": "var(--warning)",
    }

    timeline_html = ""
    for tc in (thought_chains or []):
        tc_action = str(tc.get("action", ""))
        tc_reasoning = str(tc.get("reasoning", ""))
        tc_decision = str(tc.get("decision", ""))
        tc_conf = float(tc.get("confidence_in_decision", 0) or 0)
        tc_created = str(tc.get("created_at", ""))[:19]
        icon = _ACTION_ICON.get(tc_action, "📝")
        dec_color = _DECISION_COLOR.get(tc_decision, "var(--ink-muted)")

        timeline_html += f"""<div class="kn-tl-item">
  <div class="kn-tl-dot" style="background:{dec_color}"></div>
  <div class="kn-tl-content">
    <div class="kn-tl-header">
      <span>{icon} <strong>{_html.escape(tc_action.replace('_', ' ').title())}</strong></span>
      <span class="kn-tl-time">{_html.escape(tc_created)}</span>
    </div>
    <div class="kn-tl-reasoning">{_html.escape(tc_reasoning)}</div>
    <div class="kn-tl-meta">
      <span>Decision: <strong style="color:{dec_color}">{_html.escape(tc_decision)}</strong></span>
      <span>Confidence: {int(tc_conf * 100)}%</span>
    </div>
  </div>
</div>"""

    if not timeline_html:
        timeline_html = '<div style="color:var(--ink-dim);font-style:italic;padding:16px 0;text-align:center">No thought chain entries</div>'

    # -- Action buttons --
    btns = ""
    next_stage = {"draft": "refined", "refined": "verified", "verified": "canonized"}
    if stage in next_stage:
        nxt = next_stage[stage]
        btns += (
            f'<button class="btn btn-approve" onclick="knPromote(&apos;/api/knowledge/{_html.escape(nid)}/stage&apos;)">'
            f'⬆ Promote to {_html.escape(nxt.title())} <kbd>P</kbd></button>'
        )
    if stage not in ("deprecated",):
        btns += (
            f'<button class="btn btn-reject" onclick="knDeprecate(&apos;/api/knowledge/{_html.escape(nid)}/stage&apos;)">'
            f'🗑 Deprecate <kbd>D</kbd></button>'
        )
    # Merge buttons for contradicted nodes
    if contradict_list:
        for cid in contradict_list:
            cid_esc = _html.escape(str(cid))
            btns += (
                f'<button class="btn" style="background:var(--primary);color:#fff" '
                f'onclick="knMerge(&apos;/api/knowledge/{cid_esc}/merge/{_html.escape(nid)}&apos;, '
                f'&apos;Merge this node into {cid_esc[:8]}…&apos;)">'
                f'🔗 Merge into {cid_esc[:8]}… </button>'
            )
    if not btns:
        btns = f'<div class="empty" style="flex:1">Node is {stage} — no actions available.</div>'

    body = f"""{_nav(active="queue")}
<div class="detail-header">
  <a href="/knowledge" class="back-link">← Knowledge Tree</a>
  <span class="detail-title">{_html.escape(summary[:60])}</span>
  {_stage_badge(stage)}
  {_kn_category_badge(category)}
</div>

<div class="detail-body">

  <!-- Summary & Confidence -->
  <div class="section">
    <h3>Summary</h3>
    <p style="font-size:1rem;font-weight:500">{_html.escape(summary)}</p>
  </div>

  <div class="section">
    <h3>Confidence</h3>
    {confidence_html}
  </div>

  <!-- Full content -->
  <div class="section">
    <h3>Content</h3>
    <p style="white-space:pre-wrap">{_html.escape(content)}</p>
  </div>

  <!-- Metadata grid -->
  <div class="meta-grid" style="background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);margin-bottom:var(--sp-lg)">
    <span class="label">Node ID</span><span class="value" style="font-family:var(--font-mono);font-size:.78rem;word-break:break-all">{_html.escape(nid)}</span>
    <span class="label">Category</span><span class="value">{_kn_category_badge(category)}</span>
    <span class="label">Domain</span><span class="value">{_html.escape(domain)}</span>
    <span class="label">Stage</span><span class="value">{_stage_badge(stage)}</span>
    <span class="label">Operation</span><span class="value">{_html.escape(operation)}</span>
    <span class="label">Source</span><span class="value" style="font-size:.82rem;word-break:break-all">{_html.escape(source)}</span>
    <span class="label">Created</span><span class="value">{_html.escape(created_at)}</span>
    {'<span class="label">Refined</span><span class="value">' + _html.escape(refined_at) + '</span>' if refined_at else ''}
    {'<span class="label">Verified</span><span class="value">' + _html.escape(verified_at) + '</span>' if verified_at else ''}
    {'<span class="label">Deprecated</span><span class="value">' + _html.escape(deprecated_at) + '</span>' if deprecated_at else ''}
    <span class="label">Retrievals</span><span class="value">{retrieval_count}</span>
    <span class="label">Last Used</span><span class="value">{_html.escape(last_used_at) if last_used_at else '—'}</span>
    <span class="label">Corrections</span><span class="value">{correction_count}</span>
  </div>

  <!-- Evidence -->
  <div class="section">
    <h3>Evidence</h3>
    {evidence_html}
  </div>

  <!-- Provenance (merged/contradicts/verified) -->
  <div class="section">
    <h3>Provenance</h3>
    <div style="display:grid;gap:8px">
      <div><span style="color:var(--ink-muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em">Merged From</span><div style="margin-top:2px">{_id_list_html(merged_list)}</div></div>
      <div><span style="color:var(--ink-muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em">Contradicts</span><div style="margin-top:2px">{_id_list_html(contradict_list)}</div></div>
      <div><span style="color:var(--ink-muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em">Verified By</span><div style="margin-top:2px">{_id_list_html(verified_list)}</div></div>
    </div>
  </div>

  <!-- Relationships -->
  <div class="section">
    <h3>Relationships</h3>
    <div style="display:flex;flex-direction:column;gap:6px">{rel_cards}</div>
  </div>

  <!-- Thought Chain Timeline -->
  <div class="section">
    <h3>Thought Chain Timeline</h3>
    <div class="kn-timeline">{timeline_html}</div>
  </div>

</div>

<div class="action-bar">{btns}</div>

<div class="confirm-overlay" id="confirm-overlay" onclick="if(event.target===this)hideConfirm()">
  <div class="confirm-modal">
    <h3 id="confirm-title"></h3>
    <div class="confirm-actions">
      <button class="btn-yes" id="confirm-action-btn">Confirm</button>
      <button class="btn-no" onclick="hideConfirm()">Cancel</button>
    </div>
  </div>
</div>

<style>
.kn-rel-card{{
  display:flex;align-items:center;gap:10px;padding:10px 14px;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  text-decoration:none;color:var(--ink);transition:all var(--duration);min-height:44px
}}
.kn-rel-card:hover{{border-color:var(--border-focus);background:var(--card-hover);text-decoration:none}}
.kn-rel-type{{font-size:.72rem;font-weight:600;color:var(--primary);min-width:100px;white-space:nowrap}}
.kn-rel-summary{{flex:1;font-size:.84rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.kn-rel-id{{font-size:.72rem;color:var(--ink-dim);font-family:var(--font-mono);flex-shrink:0}}

.kn-timeline{{position:relative;padding-left:24px}}
.kn-tl-item{{position:relative;padding-bottom:16px}}
.kn-tl-item:last-child{{padding-bottom:0}}
.kn-tl-item::before{{
  content:'';position:absolute;left:-20px;top:12px;bottom:-4px;
  width:2px;background:var(--border)
}}
.kn-tl-item:last-child::before{{display:none}}
.kn-tl-dot{{
  position:absolute;left:-24px;top:6px;width:12px;height:12px;
  border-radius:50%;border:2px solid var(--card);z-index:1
}}
.kn-tl-content{{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  padding:10px 14px;transition:border-color var(--duration)
}}
.kn-tl-content:hover{{border-color:var(--border-hover)}}
.kn-tl-header{{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}}
.kn-tl-time{{font-size:.72rem;color:var(--ink-dim);font-family:var(--font-mono)}}
.kn-tl-reasoning{{font-size:.84rem;color:var(--ink);margin-top:6px;line-height:1.5;white-space:pre-wrap;word-break:break-word}}
.kn-tl-meta{{display:flex;gap:16px;margin-top:6px;font-size:.75rem;color:var(--ink-muted)}}
</style>
"""
    return _page(f"Knowledge · {summary[:40]}", body, extra_js=_KN_ACTION_JS)

