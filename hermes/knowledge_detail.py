from __future__ import annotations

import html
import json
from collections.abc import Mapping, Sequence
from urllib.parse import quote

from hermes.templates import _page


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _node_url(node_id: object) -> str:
    return "/knowledge/" + quote(str(node_id), safe="")


def _json_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _relation_rows(label: str, nodes: Sequence[Mapping[str, object]]) -> str:
    if not nodes:
        return f'<div class="detail-empty"><strong>{_e(label)}</strong><span>None recorded</span></div>'
    rows = []
    for node in nodes:
        node_id = node.get("id", "")
        summary = node.get("summary") or node_id
        rows.append(
            '<a class="relation-row" href="{}">'
            '<span class="relation-kind">{}</span>'
            '<span class="relation-summary">{}</span>'
            '<span class="relation-stage">{}</span>'
            "</a>".format(
                _e(_node_url(node_id)),
                _e(label),
                _e(summary),
                _e(node.get("stage") or "unknown"),
            )
        )
    return "".join(rows)


def knowledge_detail_page(
    *,
    node: Mapping[str, object],
    thought_chains: Sequence[Mapping[str, object]],
    parent_node: Mapping[str, object] | None = None,
    child_nodes: Sequence[Mapping[str, object]] | None = None,
    supersedes_node: Mapping[str, object] | None = None,
    superseded_by: Sequence[Mapping[str, object]] | None = None,
    contradicts_nodes: Sequence[Mapping[str, object]] | None = None,
) -> str:
    """Render one knowledge node as an isolated Engram detail ledger."""
    node_id = node.get("id", "")
    canonical_url = _node_url(node_id)
    relations = "".join(
        [
            _relation_rows("Parent", [parent_node] if parent_node else []),
            _relation_rows("Child", list(child_nodes or [])),
            _relation_rows("Supersedes", [supersedes_node] if supersedes_node else []),
            _relation_rows("Superseded by", list(superseded_by or [])),
            _relation_rows("Contradicts", list(contradicts_nodes or [])),
        ]
    )
    history = "".join(
        '<article class="history-row"><div><strong>{}</strong><span>{}</span></div>'
        '<p>{}</p><p class="history-decision">{}</p></article>'.format(
            _e(chain.get("action") or "Decision"),
            _e(chain.get("created_at") or "Time unavailable"),
            _e(chain.get("reasoning") or "Reasoning unavailable"),
            _e(chain.get("decision") or "Decision unavailable"),
        )
        for chain in thought_chains
    ) or '<p class="detail-empty-copy">No reasoning history recorded.</p>'
    evidence_items = _json_list(node.get("evidence"))
    evidence = "".join(
        '<li><strong>{}</strong><span>{}</span><blockquote>{}</blockquote></li>'.format(
            _e(item.get("source_type") if isinstance(item, Mapping) else "Evidence"),
            _e(item.get("source_uri") if isinstance(item, Mapping) else ""),
            _e(item.get("quoted_excerpt") if isinstance(item, Mapping) else item),
        )
        for item in evidence_items
    ) or '<li class="detail-empty-copy">No evidence recorded.</li>'

    stage = str(node.get("stage") or "unknown")
    next_stage = {
        "draft": "refined",
        "refined": "verified",
        "verified": "canonized",
    }.get(stage)
    api_base = "/api/knowledge/" + quote(str(node_id), safe="")
    action_buttons = [
        '<button type="button" class="detail-action" data-detail-action="edit">Edit claim</button>'
    ]
    if next_stage:
        action_buttons.append(
            '<button type="button" class="detail-action detail-action-primary" '
            f'data-detail-action="stage" data-action-url="{_e(api_base + "/stage")}" '
            f'data-next-stage="{_e(next_stage)}">Promote to {_e(next_stage)}</button>'
        )
    if stage != "deprecated":
        action_buttons.append(
            '<button type="button" class="detail-action detail-action-warn" '
            f'data-detail-action="deprecate" data-action-url="{_e(api_base + "/stage")}">Deprecate</button>'
        )
    else:
        action_buttons.append(
            '<button type="button" class="detail-action detail-action-danger" '
            f'data-detail-action="delete" data-action-url="{_e(api_base)}">Delete permanently</button>'
        )
    for contradiction in contradicts_nodes or []:
        source_id = contradiction.get("id", "")
        merge_url = api_base + "/merge/" + quote(str(source_id), safe="")
        action_buttons.append(
            '<button type="button" class="detail-action" '
            f'data-detail-action="merge" data-action-url="{_e(merge_url)}">'
            f'Merge {_e(contradiction.get("summary") or source_id)}</button>'
        )
    actions = "".join(action_buttons)

    body = f"""
<a class="detail-skip" href="#knowledge-detail-main">Skip to knowledge detail</a>
<main class="engram-detail" id="knowledge-detail-main" tabindex="-1">
  <nav class="detail-breadcrumb" aria-label="Breadcrumb"><a href="/knowledge">Knowledge</a><span aria-hidden="true">/</span><span>Node detail</span></nav>
  <header class="detail-header">
    <div>
      <p class="detail-kicker">Knowledge ledger · {_e(node.get('category') or 'uncategorized')}</p>
      <h1>{_e(node.get('summary') or 'Untitled knowledge')}</h1>
      <p class="detail-content">{_e(node.get('content') or 'No claim content recorded.')}</p>
    </div>
    <div class="detail-stage" data-stage="{_e(node.get('stage') or 'unknown')}">
      <span>Stage</span><strong>{_e(node.get('stage') or 'unknown')}</strong>
    </div>
  </header>
  <div class="detail-actions" aria-label="Lifecycle actions">{actions}</div>
  <div class="detail-grid">
    <div class="detail-primary">
      <section class="detail-section" aria-labelledby="evidence-heading"><h2 id="evidence-heading">Evidence</h2><ul class="evidence-list">{evidence}</ul></section>
      <section class="detail-section" aria-labelledby="history-heading"><h2 id="history-heading">History</h2>{history}</section>
      <section class="detail-section" aria-labelledby="provenance-heading"><h2 id="provenance-heading">Provenance</h2>
        <dl class="detail-facts"><div><dt>Source</dt><dd>{_e(node.get('source') or 'Not recorded')}</dd></div><div><dt>Operation</dt><dd>{_e(node.get('operation') or 'Not recorded')}</dd></div><div><dt>Merged from</dt><dd>{_e(', '.join(map(str, _json_list(node.get('merged_from')))) or 'None recorded')}</dd></div><div><dt>Verified by</dt><dd>{_e(', '.join(map(str, _json_list(node.get('verified_by')))) or 'None recorded')}</dd></div></dl>
      </section>
      <section class="detail-section" aria-labelledby="relationships-heading"><h2 id="relationships-heading">Relationships</h2><div class="relation-list">{relations}</div></section>
    </div>
    <aside class="detail-rail" aria-label="Knowledge metadata">
      <h2>Ledger facts</h2>
      <dl class="detail-facts">
        <div><dt>ID</dt><dd><a class="detail-id" href="{_e(canonical_url)}">{_e(node_id)}</a></dd></div>
        <div><dt>Domain</dt><dd>{_e(node.get('domain') or 'Unassigned')}</dd></div>
        <div><dt>Confidence</dt><dd>{_e(node.get('confidence') if node.get('confidence') is not None else 'Not available')}</dd></div>
        <div><dt>Created</dt><dd>{_e(node.get('created_at') or 'Not available')}</dd></div>
        <div><dt>Refined</dt><dd>{_e(node.get('refined_at') or 'Not available')}</dd></div>
        <div><dt>Verified</dt><dd>{_e(node.get('verified_at') or 'Not available')}</dd></div>
        <div><dt>Retrieved</dt><dd>{_e(node.get('retrieval_count') if node.get('retrieval_count') is not None else 'Not available')}</dd></div>
        <div><dt>Outcomes</dt><dd>{_e(node.get('outcome_count') if node.get('outcome_count') is not None else 'Not available')}</dd></div>
      </dl>
    </aside>
  </div>
</main>
<div class="detail-dialog-backdrop" id="detail-dialog-backdrop" hidden>
  <section class="detail-dialog" id="detail-dialog" role="dialog" aria-modal="true" aria-labelledby="detail-dialog-title" tabindex="-1">
    <h2 id="detail-dialog-title">Confirm action</h2>
    <p id="detail-dialog-copy">Review this change before continuing.</p>
    <form id="detail-edit-form" hidden>
      <label>Summary<input id="detail-edit-summary" name="summary" value="{_e(node.get('summary') or '')}"></label>
      <label>Content<textarea id="detail-edit-content" name="content">{_e(node.get('content') or '')}</textarea></label>
      <label>Category<input id="detail-edit-category" name="category" value="{_e(node.get('category') or '')}"></label>
      <label>Domain<input id="detail-edit-domain" name="domain" value="{_e(node.get('domain') or '')}"></label>
    </form>
    <div class="detail-dialog-actions"><button type="button" id="detail-dialog-cancel">Cancel</button><button type="button" id="detail-dialog-confirm">Continue</button></div>
  </section>
</div>
<div class="detail-status" id="detail-status" role="status" aria-live="polite"></div>
<style>
.engram-detail{{--paper:#fff;--paper-soft:#faf8f3;--ink:#1d211d;--muted:#697069;--hair:#d9ddd5;--oxide:#9b4f32;max-width:1180px;margin:0 auto;padding:28px 24px 64px;color:var(--ink);background:var(--paper)}}
.detail-skip{{position:fixed;left:12px;top:8px;z-index:1000;transform:translateY(-160%);background:#fff;color:#111;border:2px solid #111;padding:10px 14px}}.detail-skip:focus{{transform:none}}
.detail-breadcrumb{{display:flex;gap:8px;align-items:center;font-size:13px;color:var(--muted);margin-bottom:24px}}.detail-breadcrumb a,.detail-id{{color:var(--oxide);text-decoration-thickness:1px;text-underline-offset:3px}}
.detail-header{{display:grid;grid-template-columns:minmax(0,1fr) 150px;gap:32px;padding:0 0 28px;border-bottom:1px solid var(--hair)}}.detail-kicker{{margin:0 0 8px;text-transform:uppercase;letter-spacing:.12em;font:600 11px/1.4 ui-monospace,monospace;color:var(--muted)}}.detail-header h1{{font:600 clamp(25px,4vw,42px)/1.08 Georgia,serif;margin:0;overflow-wrap:anywhere}}.detail-content{{font:400 16px/1.75 Georgia,serif;white-space:pre-wrap;overflow-wrap:anywhere;margin:18px 0 0;max-width:75ch}}.detail-stage{{align-self:start;border-top:3px solid var(--oxide);padding:12px 0}}.detail-stage span{{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em}}.detail-stage strong{{display:block;margin-top:4px;text-transform:capitalize}}
.detail-grid{{display:grid;grid-template-columns:minmax(0,1fr) 290px;gap:42px;margin-top:28px}}.detail-primary{{min-width:0}}.detail-section{{padding:0 0 28px;margin:0 0 28px;border-bottom:1px solid var(--hair)}}.detail-section h2,.detail-rail h2{{font:650 13px/1.3 ui-sans-serif,sans-serif;text-transform:uppercase;letter-spacing:.08em;margin:0 0 16px}}.detail-rail{{min-width:0;border-left:1px solid var(--hair);padding-left:24px}}
.detail-actions{{display:flex;flex-wrap:wrap;gap:8px;padding:18px 0;border-bottom:1px solid var(--hair)}}.detail-action{{min-height:44px;padding:9px 13px;border:1px solid var(--hair);background:#fff;color:var(--ink);font:600 13px/1.2 ui-sans-serif,sans-serif;cursor:pointer}}.detail-action-primary{{background:var(--ink);color:#fff;border-color:var(--ink)}}.detail-action-warn,.detail-action-danger{{color:#802f25;border-color:#b77c6c}}
.detail-facts{{margin:0}}.detail-facts>div{{display:grid;grid-template-columns:100px minmax(0,1fr);gap:12px;padding:9px 0;border-bottom:1px solid var(--hair)}}.detail-facts dt{{font-size:12px;color:var(--muted)}}.detail-facts dd{{margin:0;font:12px/1.5 ui-monospace,monospace;overflow-wrap:anywhere}}.evidence-list{{list-style:none;padding:0;margin:0}}.evidence-list li{{display:grid;gap:5px;padding:12px 0;border-top:1px solid var(--hair)}}.evidence-list span{{font:12px/1.4 ui-monospace,monospace;color:var(--muted);overflow-wrap:anywhere}}.evidence-list blockquote{{margin:0;font:14px/1.65 Georgia,serif;white-space:pre-wrap;overflow-wrap:anywhere}}
.history-row{{padding:13px 0;border-top:1px solid var(--hair)}}.history-row>div{{display:flex;justify-content:space-between;gap:16px}}.history-row span{{font-size:12px;color:var(--muted)}}.history-row p{{white-space:pre-wrap;overflow-wrap:anywhere}}.history-decision{{font-weight:600}}.relation-list{{display:grid}}.relation-row{{display:grid;grid-template-columns:105px minmax(0,1fr) 92px;gap:12px;padding:12px 0;border-top:1px solid var(--hair);color:var(--ink);text-decoration:none;min-width:0}}.relation-kind,.relation-stage{{font-size:12px;color:var(--muted)}}.relation-summary{{overflow-wrap:anywhere}}.detail-empty{{display:grid;grid-template-columns:105px 1fr;gap:12px;padding:10px 0;border-top:1px solid var(--hair);font-size:12px}}.detail-empty span,.detail-empty-copy{{color:var(--muted)}}
.detail-dialog-backdrop{{position:fixed;inset:0;z-index:1200;display:grid;place-items:center;padding:18px;background:rgba(25,24,20,.46)}}.detail-dialog-backdrop[hidden]{{display:none}}.detail-dialog{{width:min(560px,100%);max-height:90vh;overflow:auto;background:#fff;border:1px solid var(--hair);padding:22px}}.detail-dialog h2{{margin-top:0}}.detail-dialog label{{display:grid;gap:6px;margin:12px 0;font-size:13px}}.detail-dialog input,.detail-dialog textarea{{width:100%;box-sizing:border-box;border:1px solid var(--hair);padding:10px;font:inherit}}.detail-dialog textarea{{min-height:180px;resize:vertical}}.detail-dialog-actions{{display:flex;justify-content:flex-end;gap:8px;margin-top:18px}}.detail-dialog-actions button{{min-height:44px;padding:9px 14px}}.detail-status{{position:fixed;right:18px;bottom:18px;z-index:1300;max-width:360px;background:#fff;border:1px solid var(--hair);padding:12px 15px;transform:translateY(160%);transition:transform .15s ease}}.detail-status.is-visible{{transform:none}}.detail-status.is-error{{border-color:#a74336;color:#7b2b23}}
.engram-detail :focus-visible{{outline:3px solid var(--oxide);outline-offset:3px}}@media(max-width:760px){{.engram-detail{{padding:20px 16px 48px}}.detail-header,.detail-grid{{grid-template-columns:1fr}}.detail-header{{gap:16px}}.detail-grid{{gap:28px}}.detail-rail{{border-left:0;border-top:1px solid var(--hair);padding:22px 0 0}}.relation-row{{grid-template-columns:84px minmax(0,1fr)}}.relation-stage{{grid-column:2}}}}@media(max-width:380px){{.detail-facts>div{{grid-template-columns:1fr;gap:3px}}.relation-row{{grid-template-columns:1fr;gap:4px}}.relation-stage{{grid-column:auto}}}}@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{scroll-behavior:auto!important;transition:none!important}}}}
</style>
<script>
(function(){{
  var root=document.getElementById('knowledge-detail-main');
  var backdrop=document.getElementById('detail-dialog-backdrop');
  var dialog=document.getElementById('detail-dialog');
  var title=document.getElementById('detail-dialog-title');
  var copy=document.getElementById('detail-dialog-copy');
  var editForm=document.getElementById('detail-edit-form');
  var cancel=document.getElementById('detail-dialog-cancel');
  var confirm=document.getElementById('detail-dialog-confirm');
  var status=document.getElementById('detail-status');
  var pending=null;
  var opener=null;
  function focusableElements(){{return Array.from(dialog.querySelectorAll('button:not([disabled]),input:not([disabled]):not([hidden]),textarea:not([disabled]):not([hidden]),select:not([disabled]):not([hidden]),a[href],[tabindex]:not([tabindex="-1"])')).filter(function(element){{return !element.closest('[hidden]');}});}}
  function showStatus(message,isError){{status.textContent=message;status.classList.toggle('is-error',!!isError);status.classList.add('is-visible');setTimeout(function(){{status.classList.remove('is-visible');}},3500);}}
  function closeDialog(){{backdrop.hidden=true;pending=null;editForm.hidden=true;if(opener)opener.focus();}}
  function openDialog(button){{opener=button;var action=button.dataset.detailAction;pending={{action:action,url:button.dataset.actionUrl||'{_e(api_base)}',stage:button.dataset.nextStage||''}};editForm.hidden=action!=='edit';title.textContent=action==='edit'?'Edit claim':'Confirm '+action;copy.textContent=action==='edit'?'Update the claim fields.':'This lifecycle action changes durable knowledge state.';backdrop.hidden=false;var targets=focusableElements();if(targets.length)targets[0].focus();else dialog.focus();}}
  async function execute(){{if(!pending)return;confirm.disabled=true;var opts={{method:'POST',credentials:'same-origin',headers:{{'Content-Type':'application/json'}}}};if(pending.action==='edit'){{opts.method='PATCH';opts.body=JSON.stringify({{summary:document.getElementById('detail-edit-summary').value.trim(),content:document.getElementById('detail-edit-content').value.trim(),category:document.getElementById('detail-edit-category').value.trim(),domain:document.getElementById('detail-edit-domain').value.trim()||'general'}});}}else if(pending.action==='stage'){{opts.body=JSON.stringify({{stage:pending.stage}});}}else if(pending.action==='deprecate'){{opts.body=JSON.stringify({{stage:'deprecated'}});}}else if(pending.action==='delete'){{opts.method='DELETE';}}try{{var response=await fetch(pending.url,opts);var data=await response.json().catch(function(){{return {{}};}});if(!response.ok)throw new Error(data.detail||('Request failed ('+response.status+')'));confirm.disabled=false;closeDialog();showStatus('Knowledge updated.',false);setTimeout(function(){{location.reload();}},450);}}catch(error){{showStatus(error.message||'Request failed.',true);confirm.disabled=false;}}}}
  root.addEventListener('click',function(event){{var button=event.target.closest('[data-detail-action]');if(button)openDialog(button);}});
  cancel.addEventListener('click',closeDialog);confirm.addEventListener('click',execute);backdrop.addEventListener('click',function(event){{if(event.target===backdrop)closeDialog();}});document.addEventListener('keydown',function(event){{if(backdrop.hidden)return;if(event.key==='Escape'){{closeDialog();return;}}if(event.key==='Tab'){{var targets=focusableElements();if(!targets.length){{event.preventDefault();dialog.focus();return;}}var first=targets[0];var last=targets[targets.length-1];if(event.shiftKey&&document.activeElement===first){{event.preventDefault();last.focus();}}else if(!event.shiftKey&&document.activeElement===last){{event.preventDefault();first.focus();}}}}}});
}})();
</script>
"""
    return _page(
        f"Knowledge — {node.get('summary') or node_id}",
        body,
        nav_active="knowledge",
    )
