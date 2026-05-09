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
@keyframes pageEnter{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes staggerFade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
body{animation:pageEnter .35s var(--ease-out)}
.topnav{animation:slideUp .25s var(--ease-out)}
.tabs{animation:staggerFade .3s var(--ease-out) .05s both}
.search-bar{animation:staggerFade .3s var(--ease-out) .1s both}
.card-grid{animation:staggerFade .3s var(--ease-out) .1s both}
.dash-grid{animation:staggerFade .3s var(--ease-out) .08s both}
.card{animation:staggerFade .25s var(--ease-out) both}
.card:nth-child(1){animation-delay:.08s}.card:nth-child(2){animation-delay:.12s}.card:nth-child(3){animation-delay:.16s}.card:nth-child(4){animation-delay:.2s}.card:nth-child(5){animation-delay:.24s}.card:nth-child(6){animation-delay:.28s}
.section{animation:staggerFade .3s var(--ease-out) both}
.section:nth-child(2){animation-delay:.06s}.section:nth-child(3){animation-delay:.12s}.section:nth-child(4){animation-delay:.18s}.section:nth-child(5){animation-delay:.24s}
.dash-card{animation:staggerFade .25s var(--ease-out) both}
.dash-card:nth-child(1){animation-delay:.06s}.dash-card:nth-child(2){animation-delay:.1s}.dash-card:nth-child(3){animation-delay:.14s}.dash-card:nth-child(4){animation-delay:.18s}.dash-card:nth-child(5){animation-delay:.22s}.dash-card:nth-child(6){animation-delay:.26s}
.sec-col{animation:staggerFade .3s var(--ease-out) both}
.sec-col:nth-child(2){animation-delay:.08s}
.sec-card{animation:staggerFade .25s var(--ease-out) both}
.kn-domain-group{animation:staggerFade .25s var(--ease-out) both}
.action-bar{animation:slideUp .3s var(--ease-out) .15s both}

/* ---- Top nav ---- */
.topnav{display:flex;align-items:center;justify-content:space-between;padding:0 var(--sp-lg);background:var(--surface);border-bottom:1px solid var(--border);min-height:56px;position:sticky;top:0;z-index:50;backdrop-filter:blur(8px)}
.topnav .brand{font-weight:700;font-size:1.15rem;color:var(--primary);white-space:nowrap;letter-spacing:-.01em;background:linear-gradient(135deg,var(--primary),var(--info));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
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
.tabs a.active,.tabs button.active{background:var(--primary-muted);color:var(--ink);border-color:var(--primary);box-shadow:0 0 0 1px var(--primary)}
.tabs a:hover,.tabs button:hover{background:var(--border-hover);color:var(--ink)}
.tab-count{font-size:.72rem;background:var(--border-hover);border-radius:var(--r-pill);padding:1px 7px;color:var(--ink-dim);font-weight:600;margin-left:2px}

/* ---- Card grid ---- */
.card-grid{display:grid;grid-template-columns:1fr;gap:var(--sp-md);padding:0 var(--sp-md) var(--sp-md)}
@media(min-width:720px){.card-grid{grid-template-columns:repeat(auto-fill,minmax(380px,1fr))}}

.card{display:block;background:var(--card);border-radius:var(--r-lg);padding:var(--sp-md);border:1px solid var(--border);text-decoration:none;color:var(--ink);min-height:44px;transition:all var(--duration) var(--ease-out);box-shadow:var(--shadow-xs)}
.card:hover{border-color:var(--primary);background:var(--card-hover);text-decoration:none;transform:translateY(-2px);box-shadow:var(--shadow-md),0 0 0 1px var(--primary)}
.card-top{display:flex;align-items:center;gap:var(--sp-sm);flex-wrap:wrap;margin-bottom:var(--sp-sm)}
.card-preview{font-size:.9rem;color:var(--ink);overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;max-width:100%;line-height:1.5}
.card-meta{display:flex;gap:var(--sp-sm);margin-top:var(--sp-sm);font-size:.78rem;color:var(--ink-muted)}

/* ---- Badges ---- */
.badge{display:inline-flex;align-items:center;height:22px;padding:2px 10px;border-radius:var(--r-pill);font-size:.7rem;font-weight:600;letter-spacing:.02em;white-space:nowrap;transition:all var(--duration);box-shadow:0 1px 2px rgba(0,0,0,.15)}
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
.section{margin-bottom:var(--sp-lg);background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-md);position:relative;padding-left:calc(var(--sp-md) + 4px);transition:border-color var(--duration)}
.section::before{content:'';position:absolute;left:0;top:var(--r-lg);bottom:var(--r-lg);width:4px;border-radius:0 4px 4px 0;background:var(--primary);opacity:.6;transition:opacity var(--duration)}
.section:hover{border-color:var(--border-hover)}
.section:hover::before{opacity:1}
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
.btn-approve{background:var(--success-muted);color:var(--success);transition:all var(--duration) var(--ease-out)}
.btn-approve:hover{background:rgba(52,211,153,.25);box-shadow:var(--shadow-sm),0 0 12px rgba(52,211,153,.15)}
.btn-export{background:var(--primary-muted);color:var(--primary);transition:all var(--duration) var(--ease-out)}
.btn-export:hover{background:rgba(167,139,250,.25);box-shadow:var(--shadow-sm),0 0 12px rgba(167,139,250,.15)}
.btn-reject{background:var(--danger-muted);color:var(--danger);transition:all var(--duration) var(--ease-out)}
.btn-reject:hover{background:rgba(248,113,113,.25);box-shadow:var(--shadow-sm),0 0 12px rgba(248,113,113,.15)}
.btn:disabled{opacity:.4;cursor:not-allowed;transform:none}
.btn:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(167,139,250,.3)}
kbd{font-family:var(--font-mono);font-size:.68rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--r-sm);padding:1px 5px;margin-left:4px;color:var(--ink-dim);font-weight:500}

/* ---- Dashboard ---- */
.dash-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;padding:0 var(--sp-md) var(--sp-md)}
@media(min-width:720px){.dash-grid{grid-template-columns:repeat(4,1fr)}}
.dash-card{background:var(--card);border-radius:var(--r-lg);padding:var(--sp-lg) var(--sp-md);border:1px solid var(--border);text-align:center;box-shadow:var(--shadow-xs);transition:all var(--duration) var(--ease-out);position:relative;overflow:hidden}
.dash-card::after{content:'';position:absolute;bottom:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--primary),var(--info));opacity:0;transition:opacity var(--duration)}
.dash-card:hover{border-color:var(--border-focus);box-shadow:var(--shadow-md);transform:translateY(-2px)}
.dash-card:hover::after{opacity:1}
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
.confirm-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.55);backdrop-filter:blur(8px);z-index:200;justify-content:center;align-items:center}
.confirm-overlay[style*="flex"]{animation:fadeIn var(--duration) var(--ease-out)}
.confirm-modal{background:var(--card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-lg);max-width:380px;width:90%;text-align:center;box-shadow:var(--shadow-xl);animation:fadeIn var(--duration) var(--ease-out);transform:scale(1)}
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
.search-bar input:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(167,139,250,.25),0 0 0 1px var(--primary)}
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

def _nav(*, active: str = "knowledge") -> str:
    links = [
        ("knowledge", "Knowledge", "/knowledge", _ICON_KNOWLEDGE),
        ("gallery", "Gallery", "/gallery", _ICON_GALLERY),
        ("security", "Security", "/security", _ICON_SECURITY),
        ("settings", "Settings", "/settings", _ICON_SETTINGS),
    ]
    desktop_items = []
    mobile_items = []
    for key, label, href, icon in links:
        cls = " active" if key == active else ""
        desktop_items.append(f'<a href="{href}" class="{cls.lstrip()}">{_html.escape(label)}</a>')
        mobile_items.append(f'<a href="{href}" class="{cls.lstrip()}">{icon} <span>{_html.escape(label)}</span></a>')

    return f"""<nav class="topnav">
  <a href="/knowledge" class="brand">🧠 Hermes</a>
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
    error_html = f'<div class="login-error">{_html.escape(error)}</div>' if error else ""
    body = f"""<div class="login-wrapper">
<div class="login-card">
  <div class="login-brand">
    <div class="login-logo">🧠</div>
    <h1 class="login-title">Hermes</h1>
    <p class="login-subtitle">Knowledge Management System</p>
  </div>
  {error_html}
  <form method="POST" action="/login" class="login-form">
    <label class="login-label">Username</label>
    <div class="login-input-wrap">
      <svg class="login-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      <input type="text" name="username" autocomplete="username" class="login-input" placeholder="Username" autofocus>
    </div>
    <label class="login-label">Password</label>
    <div class="login-input-wrap">
      <svg class="login-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
      <input type="password" name="password" autocomplete="current-password" class="login-input" placeholder="Password">
    </div>
    <button type="submit" class="login-btn">Sign In</button>
  </form>
  <p class="login-hint">
    API: <code>Authorization: Bearer &lt;token&gt;</code>
  </p>
</div>
</div>"""
    login_css = """
<style>
.login-wrapper{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:16px;background:radial-gradient(ellipse at 50% 0%,rgba(167,139,250,.08) 0%,transparent 60%)}
.login-card{background:var(--card);border-radius:var(--r-xl);padding:40px 32px;max-width:380px;width:100%;border:1px solid var(--border);box-shadow:var(--shadow-lg);animation:fadeIn .4s var(--ease-out)}
.login-brand{text-align:center;margin-bottom:28px}
.login-logo{font-size:2.4rem;margin-bottom:4px;animation:slideUp .4s var(--ease-out)}
.login-title{font-size:1.5rem;font-weight:700;margin:0;background:linear-gradient(135deg,var(--primary),var(--info));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.login-subtitle{font-size:.82rem;color:var(--ink-muted);margin-top:4px;letter-spacing:.02em}
.login-error{background:var(--danger-muted);color:var(--danger);padding:10px 14px;border-radius:var(--r-md);font-size:.88rem;text-align:center;margin-bottom:16px;border:1px solid var(--danger);animation:staggerFade .3s var(--ease-out)}
.login-form{display:flex;flex-direction:column;gap:4px}
.login-label{display:block;font-size:.82rem;color:var(--ink-muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:.06em;font-weight:500}
.login-input-wrap{position:relative;margin-bottom:14px}
.login-icon{position:absolute;left:12px;top:50%;transform:translateY(-50%);width:18px;height:18px;color:var(--ink-dim);pointer-events:none;transition:color var(--duration)}
.login-input{width:100%;padding:12px 12px 12px 40px;border:1px solid var(--border);border-radius:var(--r-md);background:var(--surface);color:var(--ink);font-size:.95rem;min-height:48px;outline:none;transition:border-color var(--duration),box-shadow var(--duration)}
.login-input:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(167,139,250,.2)}
.login-input:focus+.login-icon,.login-input:focus~.login-icon{color:var(--primary)}
.login-input-wrap:focus-within .login-icon{color:var(--primary)}
.login-btn{width:100%;padding:14px;border:none;border-radius:var(--r-md);background:linear-gradient(135deg,var(--primary),#818cf8);color:#fff;font-size:1rem;font-weight:600;cursor:pointer;min-height:48px;transition:all var(--duration) var(--ease-out);margin-top:4px;position:relative;overflow:hidden}
.login-btn:hover{box-shadow:var(--shadow-md),0 0 20px rgba(167,139,250,.25);transform:translateY(-1px)}
.login-btn:active{transform:translateY(1px);box-shadow:var(--shadow-sm)}
.login-hint{text-align:center;margin-top:20px;font-size:.72rem;color:var(--ink-dim);line-height:1.5}
.login-hint code{background:var(--surface);padding:2px 8px;border-radius:var(--r-sm);border:1px solid var(--border);font-size:.72rem;font-family:var(--font-mono)}
</style>
"""
    return _page("Hermes Login", login_css + body)


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

    # Category groups for cleaner filter UI (map tags → broad chart-type categories)
    _CATEGORY_GROUPS = {
        # tag → 图表类型大类
        "散点": "散点图", "差异表达": "散点图", "GWAS/QTL": "散点图", "富集": "散点图",
        "降维": "散点图", "位点标注": "散点图", "检验": "散点图", "配对比较": "散点图",
        "组成": "散点图", "3D": "散点图", "单细胞": "散点图", "APA": "散点图",

        "线图/曲线": "线图/曲线", "生存": "线图/曲线", "分类": "线图/曲线",

        "分布": "分布图", "箱线": "分布图", "云雨": "分布图", "山峦": "分布图",

        "热图": "热图", "聚类": "热图", "相关性": "热图", "脑区": "热图", "环状": "热图",

        "柱状图": "柱状图", "分组比较": "柱状图", "双向": "柱状图",
        "面积图": "柱状图",

        "网络/关系": "网络/关系图", "互作": "网络/关系图", "弦图": "网络/关系图",
        "冲积": "网络/关系图", "桑基": "网络/关系图",

        "集合": "集合图", "交集": "集合图",

        "圈图": "圈图", "基因组": "圈图",

        "基因组结构": "基因组图", "基因簇": "基因组图", "进化树": "基因组图",
        "共线性": "基因组图", "突变": "基因组图", "标注": "基因组图",

        "临床": "临床图", "森林图": "临床图", "预后": "临床图",

        "雷达图": "雷达图", "多维": "雷达图",
    }

    chart_cards = ""
    for c in _catalog.get("charts", []):
        name = c.get("name", "")
        title = c.get("title", name)
        desc = c.get("description", "")
        tags = c.get("tags", [])
        tier = c.get("tier", "P2")
        status = c.get("status", "planned")
        tpl_path = c.get("template", "")
        has_template = (
            _os.path.exists(_os.path.join(_plotting_dir, "templates", f"{name}.py"))
            or (tpl_path and _os.path.exists(_os.path.join(_plotting_dir, tpl_path)))
        )
        img_file = _demo_files.get(name)
        interactive_file = _interactive_files.get(name)

        # Map tags to broader categories for filtering
        categories = set()
        for t in tags:
            categories.add(_CATEGORY_GROUPS.get(t, "其他"))

        card_class = "has-demo" if img_file else "no-demo"
        status_icon = "✅" if status == "done" else "📋"
        badges_html = f'<div class="badge-row"><span class="tier-badge tier-{tier}">{tier}</span><span class="status-icon">{status_icon}</span></div>'
        if interactive_file:
            badges_html = f'<div class="badge-row"><span class="tier-badge tier-{tier}">{tier}</span><span class="status-icon">{status_icon}</span><span class="interactive-indicator">↗</span></div>'

        if img_file:
            img_url = f"/gallery/static/{img_file}"
            preview = f'<div class="card-img">{badges_html}<img src="{img_url}" onclick="openModal(this)" loading="lazy"></div>'
        else:
            preview = f'<div class="card-img" style="color:var(--ink-dim);font-size:13px;display:flex;align-items:center;justify-content:center;">{badges_html}<span class="planned-placeholder">📋 Planned</span></div>'

        tags_html = "".join(f'<span class="tag">{_html.escape(t)}</span>' for t in tags[:3])

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

        data_attrs = f'data-tags="{" ".join(tags)}" data-category="{" ".join(categories)}" data-tier="{tier}" data-status="{status}"'
        chart_cards += (
            f'<div class="gallery-card {card_class}" {data_attrs}>'
            f'{preview}'
            f'<div class="card-info"><h3>{_html.escape(title)}</h3>'
            f'<div class="desc">{_html.escape(desc[:100])}</div>'
            f'<div class="tags">{tags_html}</div></div>'
            f'{actions}'
            f'</div>'
        )

    # Filter by broad categories instead of raw tags
    _all_categories = sorted(set(
        _CATEGORY_GROUPS.get(t, "其他")
        for c in _catalog.get("charts", [])
        for t in c.get("tags", [])
    ))
    _tier_options = ["P0", "P1", "P2"]
    filter_btns = '<button class="filter-btn active" data-filter="all">All</button>'
    filter_btns += ' <span class="filter-sep">│</span>'
    filter_btns += '<span class="filter-label">Tier</span>'
    for t in _tier_options:
        tiers_class = f'tier-{t}'
        filter_btns += f' <button class="filter-btn {tiers_class}" data-filter="tier-{t}" data-tier="{t}">{t}</button>'
    filter_btns += ' <span class="filter-sep">│</span>'
    filter_btns += '<span class="filter-label">Type</span>'
    for cat in _all_categories:
        filter_btns += f' <button class="filter-btn cat-btn" data-filter="cat-{_html.escape(cat)}">{_html.escape(cat)}</button>'

    # NOTE: JS goes in extra_js, NOT in the body f-string,
    # so that curly braces are not mangled by Python's f-string escaping.
    gallery_css = '''
<style>
/* ── Gallery Layout ── */
.gallery-container { max-width: 1280px; margin: 0 auto; padding: var(--sp-lg) var(--sp-md); }
.gallery-header { text-align: center; margin-bottom: 28px; }
.gallery-header h1 { color: var(--ink); font-size: 28px; font-weight: 700; letter-spacing: -0.5px; margin: 0 0 6px; }
.gallery-header p { color: var(--ink-dim); font-size: 13px; margin: 0; }

/* ── Filter Bar ── */
.filter-bar { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; align-items: center; }
.filter-section { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.filter-label { color: var(--ink-dim); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-right: 2px; }
.filter-sep { color: var(--border); font-size: 14px; margin: 0 6px; opacity: 0.4; }
.filter-btn { background: var(--card); border: 1px solid var(--border-hover); color: var(--ink-muted); padding: 5px 14px; border-radius: var(--r-pill); cursor: pointer; font-size: 12px; transition: all var(--duration) var(--ease-out); }
.filter-btn:hover { background: var(--card-hover); border-color: var(--primary); color: var(--ink); }
.filter-btn.active { background: var(--primary); border-color: var(--primary); color: var(--bg); }
.tier-P0.active { background: var(--danger); border-color: var(--danger); color: var(--bg); }
.tier-P1.active { background: var(--primary); border-color: var(--primary); color: var(--bg); }
.tier-P2.active { background: var(--ink-dim); border-color: var(--ink-dim); color: var(--ink); }

/* ── Card Grid ── */
.gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--sp-md); margin-top: var(--sp-md); }
.gallery-card { background: var(--card); border: 1px solid var(--border-hover); border-radius: var(--r-md); overflow: hidden; transition: all var(--duration) var(--ease-out); position: relative; }
.gallery-card:hover { border-color: var(--primary); transform: translateY(-3px); box-shadow: var(--shadow-lg); }
.gallery-card.has-demo { border-left: 3px solid var(--success); }
.gallery-card.no-demo { border-left: 3px solid var(--ink-dim); opacity: 0.6; }
.gallery-card.no-demo:hover { opacity: 0.85; }

/* ── Card Image ── */
.card-img { background: var(--bg); min-height: 180px; display: flex; align-items: center; justify-content: center; padding: 10px; cursor: pointer; border-bottom: 1px solid var(--border); position: relative; }
.card-img img { max-width: 100%; max-height: 200px; object-fit: contain; transition: transform 0.2s; }
.gallery-card:hover .card-img img { transform: scale(1.02); }
.card-img .planned-placeholder { color: var(--ink-dim); font-size: 13px; text-align: center; }

/* ── Tier & Status Badges ── */
.badge-row { position: absolute; top: 8px; left: 8px; display: flex; gap: 4px; align-items: center; z-index: 2; }
.tier-badge { font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 3px; letter-spacing: 0.5px; }
.tier-badge.tier-P0 { background: var(--danger); color: var(--bg); }
.tier-badge.tier-P1 { background: var(--primary); color: var(--bg); }
.tier-badge.tier-P2 { background: var(--ink-dim); color: var(--ink-muted); }
.status-icon { font-size: 11px; filter: grayscale(0.2); }
.interactive-indicator { font-size: 10px; color: var(--info); }

/* ── Card Info ── */
.card-info { padding: 12px 14px 8px; }
.card-info h3 { font-size: 14px; color: var(--ink); margin: 0 0 4px; font-weight: 600; }
.card-info .desc { font-size: 12px; color: var(--ink-muted); margin-bottom: 8px; line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.card-info .tags { display: flex; gap: 4px; flex-wrap: wrap; }
.card-info .tag { font-size: 10px; background: var(--surface); border: 1px solid var(--border-hover); color: var(--ink-muted); padding: 1px 7px; border-radius: 10px; }

/* ── Action Buttons ── */
.btn-act { border: 1px solid var(--border-hover); border-radius: 4px; padding: 3px 10px; font-size: 11px; cursor: pointer; transition: all var(--duration) var(--ease-out); background: transparent; color: var(--ink-muted); }
.btn-ok:hover { background: var(--success-muted); border-color: var(--success); color: var(--success); }
.btn-edit:hover { background: var(--primary-muted); border-color: var(--primary); color: var(--primary); }
.btn-no:hover { background: var(--danger-muted); border-color: var(--danger); color: var(--danger); }
.btn-interactive { border-color: var(--primary); color: var(--primary); }
.btn-interactive:hover { background: var(--primary-muted); }

/* ── Suggest Input ── */
.suggest-input { margin: 4px 14px 10px; }
.suggest-input textarea { width: 100%; padding: 6px 8px; border-radius: 4px; border: 1px solid var(--border-hover); background: var(--bg); color: var(--ink); font-size: 12px; min-height: 50px; resize: vertical; box-sizing: border-box; }
.suggest-input textarea:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 2px var(--primary-muted); }
.suggest-input button { margin-top: 4px; padding: 4px 12px; border-radius: 4px; background: var(--primary); color: var(--bg); border: none; font-size: 11px; cursor: pointer; }

/* ── Modal ── */
.modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; justify-content: center; align-items: center; }
.modal-overlay.show { display: flex; }
.modal-overlay img { max-width: 92vw; max-height: 88vh; object-fit: contain; background: var(--card); border-radius: var(--r-md); box-shadow: var(--shadow-xl); }
.modal-overlay .close { position: absolute; top: 16px; right: 24px; color: var(--ink); font-size: 32px; cursor: pointer; opacity: 0.7; transition: opacity var(--duration); }
.modal-overlay .close:hover { opacity: 1; }
.iframe-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 1100; }
.iframe-modal.show { display: flex; flex-direction: column; }
.iframe-modal .iframe-header { display: flex; justify-content: space-between; align-items: center; padding: 8px var(--sp-md); background: var(--card); border-bottom: 1px solid var(--border-hover); }
.iframe-modal .iframe-header h3 { color: var(--ink); font-size: 14px; margin: 0; }
.iframe-modal .iframe-close { color: var(--ink-muted); font-size: 22px; cursor: pointer; padding: 0 8px; }
.iframe-modal .iframe-close:hover { color: var(--danger); }
.iframe-modal iframe { flex: 1; border: none; width: 100%; }

/* ── Toast ── */
.toast { position: fixed; bottom: 24px; right: 24px; padding: 10px 20px; border-radius: var(--r-md); color: var(--bg); font-size: 13px; font-weight: 500; z-index: 2000; opacity: 0; transition: opacity 0.3s; pointer-events: none; box-shadow: var(--shadow-md); }
.toast.show { opacity: 1; }
.toast.approve { background: var(--success); }
.toast.suggest { background: var(--primary); }
.toast.reject { background: var(--danger); }

/* ── Submit Figure ── */
.submit-bar { margin-bottom: 16px; text-align: center; }
.submit-toggle-btn { background: var(--card); border: 1px solid var(--border-hover); color: var(--ink-muted); padding: 6px 16px; border-radius: var(--r-pill); cursor: pointer; font-size: 12px; transition: all var(--duration) var(--ease-out); }
.submit-toggle-btn:hover { background: var(--card-hover); border-color: var(--primary); color: var(--primary); }
.submit-form { display: none; margin-top: 10px; }
.submit-form.open { display: block; }
.submit-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; max-width: 600px; margin: 0 auto; }
.submit-grid label, .submit-notes-row label { color: var(--ink-muted); font-size: 11px; display: block; margin-bottom: 2px; }
.submit-grid input[type="text"], .submit-grid input[type="file"] { width: 100%; padding: 6px 8px; border: 1px solid var(--border-hover); border-radius: 4px; background: var(--bg); color: var(--ink); font-size: 12px; box-sizing: border-box; }
.submit-grid input[type="file"] { padding: 4px; }
.submit-notes-row { max-width: 600px; margin: 6px auto 0; }
.submit-notes-row textarea { width: 100%; padding: 6px 8px; border: 1px solid var(--border-hover); border-radius: 4px; background: var(--bg); color: var(--ink); font-size: 12px; resize: vertical; box-sizing: border-box; min-height: 40px; }
.submit-actions { max-width: 600px; margin: 6px auto 0; text-align: right; }
.submit-go { padding: 6px 16px; border-radius: 4px; background: var(--primary); color: var(--bg); border: none; font-size: 12px; cursor: pointer; }

/* ── Card Actions: hover-reveal ── */
.card-actions { display: flex; gap: 5px; padding: 0 14px; max-height: 0; overflow: hidden; border-top: 0 solid var(--border); transition: max-height 0.2s ease, padding 0.2s ease, border-width 0.2s ease; }
.gallery-card:hover .card-actions { max-height: 36px; padding: 6px 14px 10px; border-top-width: 1px; }
</style>
'''

    body = (
        gallery_css +
        f'{_nav(active="gallery")}'
        '<div class="gallery-container">'
        '<div class="gallery-header"><h1>Sci-Fig Gallery</h1>'
        '<p>View charts, submit figures for analysis</p></div>'
        '<div class="submit-bar">'
        '<button class="submit-toggle-btn" onclick="toggleSubmitForm()">📎 Submit Figure</button>'
        '<div class="submit-form" id="submit-form">'
        '<div class="submit-grid">'
        '<div><label>Image URL</label><input type="text" id="submit-url" placeholder="https://..."></div>'
        '<div><label>Or Upload</label><input type="file" id="submit-file" accept="image/*"></div>'
        '</div>'
        '<div class="submit-notes-row"><label>Notes</label>'
        '<textarea id="submit-notes" rows="2" placeholder="Figure type, paper source, what you like..."></textarea></div>'
        '<div class="submit-actions"><button class="submit-go" onclick="submitFigure()">Submit</button></div>'
        '</div></div>'
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
// Submit figure for analysis
function toggleSubmitForm() {
  var form = document.getElementById('submit-form');
  form.classList.toggle('open');
}
function submitFigure() {
  var urlInput = document.getElementById('submit-url');
  var fileInput = document.getElementById('submit-file');
  var notesInput = document.getElementById('submit-notes');
  var url = urlInput.value.trim();
  var notes = notesInput.value.trim();
  var file = fileInput.files[0];

  if (!url && !file) {
    showToast('Provide an image URL or upload a file', 'reject');
    return;
  }

  var formData = new FormData();
  if (url) formData.append('image_url', url);
  if (file) formData.append('file', file);
  if (notes) formData.append('notes', notes);

  fetch('/api/gallery/submit_figure', {
    method: 'POST',
    body: formData
  }).then(function(r) {
    if (r.ok) { return r.json(); }
    throw new Error('Server error: ' + r.status);
  }).then(function(data) {
    if (data.ok) {
      showToast('Figure submitted for analysis ✓', 'approve');
      urlInput.value = '';
      notesInput.value = '';
      fileInput.value = '';
      document.getElementById('submit-form').classList.remove('open');
    } else {
      showToast(data.error || 'Error', 'reject');
    }
  }).catch(function(e) {
    showToast('Error: ' + e.message, 'reject');
  });
}
// Restore saved filter from localStorage
(function() {
  var saved = localStorage.getItem('gallery_filter');
  if (saved) {
    document.querySelectorAll('.filter-btn').forEach(function(b){ b.classList.remove('active'); });
    var btn = document.querySelector('.filter-btn[data-filter="' + saved + '"]');
    if (btn) {
      btn.classList.add('active');
      filterCards(saved);
    }
  }
})();
document.querySelectorAll('.filter-btn').forEach(function(btn){
  btn.addEventListener('click', function() {
    document.querySelectorAll('.filter-btn').forEach(function(b){ b.classList.remove('active'); });
    this.classList.add('active');
    var f = this.dataset.filter;
    localStorage.setItem('gallery_filter', f);
    filterCards(f);
  });
});
function filterCards(f) {
  document.querySelectorAll('.gallery-card').forEach(function(c){
    if (f === 'all') {
      c.style.display = '';
    } else if (f.startsWith('tier-')) {
      var tier = f.substring(5);
      c.style.display = (c.dataset.tier === tier) ? '' : 'none';
    } else if (f.startsWith('cat-')) {
      var cat = f.substring(4);
      c.style.display = (c.dataset.category && c.dataset.category.indexOf(cat) >= 0) ? '' : 'none';
    } else {
      c.style.display = (c.dataset.tags && c.dataset.tags.indexOf(f) >= 0) ? '' : 'none';
    }
  });
}
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
.sec-header{{display:flex;align-items:center;justify-content:space-between;padding:12px 16px 8px;border-bottom:1px solid var(--border);margin-bottom:8px}}
.sec-header h1{{font-size:1.2rem;margin:0;font-weight:700;color:var(--ink)}}
.sec-refresh{{font-size:.78rem;color:var(--ink-dim);display:flex;align-items:center;gap:6px}}
.sec-refresh-btn{{background:none;border:1px solid var(--border);border-radius:var(--r-sm);color:var(--ink-dim);padding:4px 10px;cursor:pointer;font-size:.82rem;margin-left:8px;transition:all var(--duration)}}
.sec-refresh-btn:hover{{background:var(--card-hover);color:var(--ink);border-color:var(--primary)}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.sec-kanban{{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:0 16px 16px}}
@media(max-width:720px){{.sec-kanban{{grid-template-columns:1fr}}}}
.sec-col{{min-width:0}}
.sec-col h3{{font-size:1rem;margin:12px 0 8px;color:var(--primary);display:flex;align-items:center;gap:8px;padding-bottom:6px;border-bottom:1px solid var(--border)}}
.sec-col h4{{font-size:.85rem;margin:12px 0 6px;color:var(--ink-muted);text-transform:uppercase;letter-spacing:.04em}}
.sec-card{{background:var(--card);border-radius:var(--r-lg);padding:12px 14px;margin-bottom:8px;border:1px solid var(--border);transition:all var(--duration);box-shadow:var(--shadow-xs)}}
.sec-card:hover{{border-color:var(--border-hover);box-shadow:var(--shadow-sm)}}
.sec-overview{{background:linear-gradient(135deg,var(--card),var(--surface));border:1px solid var(--primary-muted);border-left:3px solid var(--primary)}}
.sec-empty{{color:var(--ink-dim);font-size:.82rem;font-style:italic;padding:8px 0}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;box-shadow:0 0 4px rgba(0,0,0,.2)}}
.dot-green{{background:var(--success);box-shadow:0 0 6px rgba(52,211,153,.4)}}
.dot-red{{background:var(--danger);box-shadow:0 0 6px rgba(248,113,113,.4)}}
.sec-badge{{font-size:.7rem;padding:2px 8px;border-radius:var(--r-pill);background:var(--card-hover);color:var(--ink-muted);margin-left:6px;font-weight:500;letter-spacing:.02em}}
.sec-badge-red{{background:var(--danger-muted);color:var(--danger);font-weight:600}}
.sec-stat-row{{display:flex;justify-content:space-between;padding:6px 0;font-size:.88rem;border-bottom:1px solid var(--border)}}
.sec-stat-row:last-child{{border-bottom:none}}
.sec-bar-row{{display:flex;align-items:center;gap:8px;padding:3px 0;font-size:.82rem}}
.sec-ip{{min-width:130px;color:var(--ink-dim);font-family:monospace;font-size:.78rem}}
.sec-bar-bg{{flex:1;height:6px;background:var(--border-hover);border-radius:3px;overflow:hidden}}
.sec-bar-fill{{height:100%;background:var(--danger);border-radius:3px;transition:width .6s var(--ease-out)}}
.sec-cnt{{min-width:40px;text-align:right;color:var(--ink-dim);font-size:.78rem}}
.sec-ufw-row{{display:flex;align-items:center;gap:6px;padding:5px 0;font-size:.82rem;border-bottom:1px solid var(--border);transition:background var(--duration)}}
.sec-ufw-row:hover{{background:var(--card-hover)}}
.sec-ufw-row:last-child{{border-bottom:none}}
.sec-ufw-action{{min-width:48px;font-weight:600;font-size:.78rem}}
.sec-ufw-to{{min-width:90px;font-family:monospace;font-size:.78rem}}
.sec-ufw-comment{{color:var(--ink-dim);font-size:.75rem}}
.sec-inbound-card{{background:var(--card);border-radius:var(--r-lg);padding:12px 14px;margin-bottom:8px;border:1px solid var(--border);transition:all var(--duration);box-shadow:var(--shadow-xs)}}
.sec-inbound-card:hover{{border-color:var(--border-hover);box-shadow:var(--shadow-sm)}}
.sec-inbound-header{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.sec-inbound-name{{font-weight:600;font-size:.92rem}}
.sec-inbound-meta{{font-size:.78rem;color:var(--ink-dim);font-family:monospace}}
.sec-inbound-traffic{{font-size:.78rem;margin-left:auto;font-weight:500}}
.sec-inbound-clients{{margin-top:8px;padding-left:16px;border-left:2px solid var(--border)}}
.sec-client-row{{display:flex;align-items:center;gap:6px;padding:4px 0;font-size:.82rem;border-bottom:1px solid var(--border)}}
.sec-client-row:last-child{{border-bottom:none}}
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
  <h1 style="font-size:1.2rem;margin-bottom:16px;font-weight:700;letter-spacing:-.02em">⚙️ Settings</h1>

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

  <div class="settings-section" style="border-color:var(--danger-muted)">
    <h3 style="color:var(--danger)">🚪 Sign Out</h3>
    <p style="font-size:.88rem;color:var(--ink-muted);margin:0 0 12px">End your current session and return to the login page.</p>
    <a href="/logout" class="settings-btn-logout">{_ICON_LOGOUT} Sign Out</a>
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
.settings-btn-logout{{display:inline-flex;align-items:center;gap:8px;padding:12px 24px;border:1px solid var(--danger);border-radius:var(--r-md);background:var(--danger-muted);color:var(--danger);font-size:.95rem;font-weight:600;cursor:pointer;text-decoration:none;transition:all var(--duration) var(--ease-out);min-height:44px}}
.settings-btn-logout:hover{{background:rgba(248,113,113,.25);box-shadow:var(--shadow-sm)}}
.settings-btn-logout svg{{width:18px;height:18px}}
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

                uses_text = f"🔍 {retrieval_count}" if retrieval_count > 0 else ""

                group_cards += f"""<a href="/knowledge/{_html.escape(nid)}" class="card">
  <div class="card-top">{_stage_badge(stage)} {_kn_category_badge(category)} <span class="badge badge-rule" style="font-size:.65rem">{_html.escape(ndomain)}</span></div>
  <div class="card-preview">{_html.escape(preview)}</div>
  <div style="margin-top:8px;display:flex;align-items:center;gap:8px">
    {_confidence_bar(confidence)}
  </div>
  <div class="card-meta">
    <span>{_html.escape(created_at)}</span>
    {"<span>" + uses_text + "</span>" if uses_text else ""}
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

    body = f"""{_nav(active="knowledge")}
<h1 style="padding:16px 16px 0;font-size:1.2rem;font-weight:700;letter-spacing:-.02em">🌳 Knowledge Tree</h1>
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
<div style="padding:0 16px 8px;display:flex;gap:8px;flex-wrap:wrap">
  <button class="kn-action-btn" onclick="showAddModal()">+ Add Knowledge</button>
  <button class="kn-action-btn secondary" onclick="exportKnowledge()">⬇ Export MD</button>
  <button class="kn-action-btn secondary" onclick="retrospect()">🔄 Retrospect</button>
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
.kn-domain-header:hover{{background:var(--card-hover);border-color:var(--primary);box-shadow:0 0 0 1px var(--primary)}}
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
.kn-action-btn{{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border:1px solid var(--border);border-radius:var(--r-pill);background:var(--primary-muted);color:var(--primary);font-size:.84rem;font-weight:600;cursor:pointer;min-height:40px;transition:all var(--duration)}}
.kn-action-btn:hover{{background:rgba(167,139,250,.25);border-color:var(--border-focus)}}
.kn-action-btn.secondary{{background:var(--surface);color:var(--ink-muted);border-color:var(--border)}}
.kn-action-btn.secondary:hover{{color:var(--ink);border-color:var(--border-hover);background:var(--card)}}
.kn-modal-form textarea,.kn-modal-form input,.kn-modal-form select{{width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:var(--r-md);background:var(--surface);color:var(--ink);font-size:.84rem;margin-bottom:8px;min-height:40px;outline:none}}
.kn-modal-form textarea:focus,.kn-modal-form input:focus,.kn-modal-form select:focus{{border-color:var(--border-focus);box-shadow:0 0 0 3px rgba(167,139,250,.2)}}
.kn-modal-form textarea{{min-height:120px;resize:vertical}}
.kn-modal-form label{{display:block;font-size:.78rem;color:var(--ink-muted);margin-bottom:2px;text-transform:uppercase;letter-spacing:.04em}}
</style>
<div id="add-modal-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1000;align-items:center;justify-content:center">
  <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-lg);max-width:480px;width:90%;max-height:80vh;overflow-y:auto">
    <h2 style="margin-bottom:var(--sp-md);font-size:1.1rem">Add Knowledge</h2>
    <form class="kn-modal-form" id="add-knowledge-form" onsubmit="return submitKnowledge(event)">
      <label>Content *</label>
      <textarea id="kn-form-content" required placeholder="Enter knowledge content..."></textarea>
      <label>Source</label>
      <input type="text" id="kn-form-source" placeholder="e.g. conversation, manual, observation">
      <label>Category</label>
      <select id="kn-form-category">
        <option value="fact">fact</option>
        <option value="rule">rule</option>
        <option value="workflow_hint">workflow_hint</option>
        <option value="preference">preference</option>
      </select>
      <label>Domain</label>
      <input type="text" id="kn-form-domain" value="general" placeholder="general">
      <div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end">
        <button type="button" class="kn-action-btn secondary" onclick="hideAddModal()">Cancel</button>
        <button type="submit" class="kn-action-btn">Submit</button>
      </div>
    </form>
  </div>
</div>
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
function showAddModal() {{
  document.getElementById('add-modal-overlay').style.display = 'flex';
  document.getElementById('kn-form-content').focus();
}}
function hideAddModal() {{
  document.getElementById('add-modal-overlay').style.display = 'none';
  document.getElementById('add-knowledge-form').reset();
  document.getElementById('kn-form-domain').value = 'general';
}}
function submitKnowledge(e) {{
  e.preventDefault();
  var content = document.getElementById('kn-form-content').value.trim();
  if (!content) return false;
  var data = {{
    content: content,
    source: document.getElementById('kn-form-source').value.trim(),
    category: document.getElementById('kn-form-category').value,
    domain: document.getElementById('kn-form-domain').value.trim() || 'general'
  }};
  fetch('/api/knowledge/integrate', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(data)
  }})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      showToast(d.message || 'Knowledge added', 'approve');
      hideAddModal();
      setTimeout(function(){{ location.reload(); }}, 800);
    }})
    .catch(function(e) {{ showToast('Error: ' + e.message, 'reject'); }});
  return false;
}}
function exportKnowledge() {{
  fetch('/api/knowledge/export', {{method:'POST',headers:{{'Content-Type':'application/json'}}}})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{ showToast(d.message || 'Export complete', 'approve'); }})
    .catch(function(e) {{ showToast('Error: ' + e.message, 'reject'); }});
}}
function retrospect() {{
  fetch('/api/knowledge/retrospect?dry_run=false', {{method:'POST',headers:{{'Content-Type':'application/json'}}}})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{ showToast(d.message || 'Retrospect complete', 'approve'); }})
    .catch(function(e) {{ showToast('Error: ' + e.message, 'reject'); }});
}}
function showToast(msg, type) {{
  var t = document.createElement('div');
  t.className = 'toast toast-' + (type||'approve');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(function(){{ t.classList.add('show'); }},10);
  setTimeout(function(){{ t.classList.remove('show'); setTimeout(function(){{ t.remove(); }},300); }},2500);
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

    body = f"""{_nav(active="knowledge")}
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

.kn-timeline{{position:relative;padding-left:28px}}
.kn-tl-item{{position:relative;padding-bottom:20px}}
.kn-tl-item:last-child{{padding-bottom:0}}
.kn-tl-item::before{{
  content:'';position:absolute;left:-22px;top:24px;bottom:0;
  width:2px;background:linear-gradient(to bottom,var(--primary) 0%,var(--border) 100%);
  border-radius:1px
}}
.kn-tl-item:last-child::before{{display:none}}
.kn-tl-dot{{
  position:absolute;left:-26px;top:4px;width:14px;height:14px;
  border-radius:50%;border:2px solid var(--card);z-index:1;
  box-shadow:0 0 8px rgba(0,0,0,.3),0 0 0 3px var(--surface)
}}
.kn-tl-content{{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  padding:12px 16px;transition:border-color var(--duration),box-shadow var(--duration);
  position:relative;overflow:hidden
}}
.kn-tl-content::before{{
  content:'';position:absolute;left:0;top:8px;bottom:8px;width:3px;
  border-radius:2px;background:var(--primary);opacity:.4;transition:opacity var(--duration)
}}
.kn-tl-content:hover{{border-color:var(--primary);box-shadow:0 2px 12px rgba(167,139,250,.12)}}
.kn-tl-content:hover::before{{opacity:1}}
.kn-tl-header{{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}}
.kn-tl-time{{font-size:.72rem;color:var(--ink-dim);font-family:var(--font-mono)}}
.kn-tl-reasoning{{font-size:.84rem;color:var(--ink);margin-top:8px;line-height:1.6;white-space:pre-wrap;word-break:break-word}}
.kn-tl-meta{{display:flex;gap:16px;margin-top:8px;font-size:.75rem;color:var(--ink-muted)}}
</style>
"""
    return _page(f"Knowledge · {summary[:40]}", body, extra_js=_KN_ACTION_JS)

