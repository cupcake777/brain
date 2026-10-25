from pathlib import Path
import importlib.util
import json
import pytest

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'skills'/'brain-loop'

def load():
    spec=importlib.util.spec_from_file_location('portable_brain',PACKAGE/'scripts'/'brain.py')
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_packaged_skill_and_dependencies_exist():
    for p in [
        'SKILL.md',
        'scripts/brain.py',
        'scripts/brain-sync-hpc.sh',
        'scripts/brain_plugin.py',
        'references/protocol.md',
        'references/codex-workflow.md',
        'templates/proposal.json',
    ]:
        assert (PACKAGE/p).is_file()
    assert (ROOT/'plugin.yaml').is_file()
    assert (ROOT/'__init__.py').is_file()
    assert (ROOT/'.claude-plugin'/'plugin.json').is_file()
    assert (ROOT/'.claude-plugin'/'marketplace.json').is_file()
    assert (ROOT/'.codex-plugin'/'plugin.json').is_file()
    assert (ROOT/'hooks'/'claude-codex-hooks.json').is_file()
    assert (PACKAGE/'scripts'/'brain_hook_launcher.py').is_file()
    text=(PACKAGE/'SKILL.md').read_text()
    assert 'finalize' in text and 'source-retrieve' in text
    assert 'hermes plugins install' in text
    assert 'brain.bioinfo.pro' not in text and '/root/' not in text


def test_hpc_sync_uses_canonical_json_client_not_legacy_markdown():
    script=(PACKAGE/'scripts'/'brain-sync-hpc.sh').read_text()
    assert '"$CLIENT" propose "$proposal" --wait' in script
    assert '/api/proposals/submit' not in script
    assert 'propose-file /path/to/lesson.json' in script


def test_codex_workflow_describes_real_governance_states():
    text=(PACKAGE/'references'/'codex-workflow.md').read_text()
    assert 'ingested_pending' in text
    assert 'proposal-status' in text
    assert 'auto-approve' not in text.lower()
    assert 'bare Markdown' not in text
    assert 'source_type' in text and 'source_uri' in text


def test_native_plugin_registers_skill_and_lifecycle_hooks(monkeypatch):
    root_init = ROOT / '__init__.py'
    spec = importlib.util.spec_from_file_location('brain_plugin_root', root_init)
    assert spec and spec.loader
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)

    class Context:
        def __init__(self):
            self.skills = []
            self.hooks = []
            self.prompt_sections = []

        def register_skill(self, name, path, **kwargs):
            self.skills.append((name, Path(path)))

        def register_system_prompt_section(self, ident, content, **kwargs):
            self.prompt_sections.append((ident, content, kwargs))

        def register_hook(self, name, callback):
            self.hooks.append((name, callback))

    ctx = Context()
    plugin.register(ctx)
    assert ctx.skills == [('brain-loop', PACKAGE/'SKILL.md')]
    assert len(ctx.prompt_sections) == 1
    assert ctx.prompt_sections[0][0] == 'brain-loop'
    assert 'brain:brain-loop' in ctx.prompt_sections[0][1]
    assert {name for name, _ in ctx.hooks} == {
        'post_tool_call', 'on_session_finalize', 'on_session_reset'
    }

def test_service_defaults_to_repository_skill(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from hermes.app import create_app
    from hermes.config import HermesConfig
    from hermes.repository import HermesRepository
    monkeypatch.delenv('BRAIN_LOOP_SKILL_ROOT',raising=False)
    config=HermesConfig(sync_root=tmp_path,db_path=tmp_path/'brain.db')
    c=TestClient(create_app(repo=HermesRepository(config.db_path),sync_root=tmp_path,config=config))
    assert c.get('/skills/brain-loop/SKILL.md').text==(PACKAGE/'SKILL.md').read_text()


def test_client_defaults_local_not_private_server(monkeypatch):
    c=load();monkeypatch.delenv('BRAIN_URL',raising=False)
    assert c.api_url()=='http://127.0.0.1:8083'

def test_finalize_uses_auth_and_minimal_payload(monkeypatch):
    c=load();calls=[]
    monkeypatch.setattr(c,'request',lambda p,**k:calls.append((p,k)) or {})
    args=c.parser().parse_args(['finalize','--session-id','session-1'])
    args.handler(args)
    assert calls[0][0]=='/api/v1/brain/finalize'
    assert calls[0][1]['write'] is True
    assert set(calls[0][1]['payload'])=={'agent','host_hash','session_id'}

def test_invalid_url_rejected_before_dispatch(monkeypatch):
    c=load();monkeypatch.setenv('BRAIN_URL','https://name:secret@example.org')
    with pytest.raises(RuntimeError):c.api_url()


def test_proposal_template_is_complete_and_not_a_submittable_placeholder():
    payload = json.loads((PACKAGE/'templates'/'proposal.json').read_text())
    assert set(payload) == {
        'summary', 'observation', 'why_it_matters', 'suggested_memory',
        'project', 'category', 'risk_level', 'scope', 'domain', 'evidence',
    }
    assert all(value.startswith('<') and value.endswith('>') for value in (
        payload['summary'], payload['observation'], payload['why_it_matters'],
        payload['suggested_memory'], payload['project'], payload['scope'], payload['domain'],
    ))
    assert payload['evidence'] == [{
        'source_type': '<file|command|url|test>',
        'source_uri': '<literal non-secret source URI>',
        'quoted_excerpt': '<exact sanitized excerpt proving the observation>',
    }]


def test_client_rejects_incomplete_or_placeholder_proposal_before_network(monkeypatch, tmp_path):
    c=load(); calls=[]
    monkeypatch.setattr(c,'request',lambda *a,**k:calls.append((a,k)) or {})

    incomplete = tmp_path/'incomplete.json'
    incomplete.write_text(json.dumps({'summary':'A valid summary long enough'}))
    with pytest.raises(RuntimeError, match='missing required fields'):
        c.parser().parse_args(['propose',str(incomplete)]).handler(
            c.parser().parse_args(['propose',str(incomplete)])
        )

    placeholder = tmp_path/'placeholder.json'
    placeholder.write_text((PACKAGE/'templates'/'proposal.json').read_text())
    with pytest.raises(RuntimeError, match='replace placeholder'):
        c.parser().parse_args(['propose',str(placeholder)]).handler(
            c.parser().parse_args(['propose',str(placeholder)])
        )
    assert calls == []


def test_client_rejects_duplicated_core_fields_before_network(monkeypatch, tmp_path):
    c=load(); calls=[]
    monkeypatch.setattr(c,'request',lambda *a,**k:calls.append((a,k)) or {})
    payload = {
        'summary':'A reusable proposal summary',
        'observation':'The exact same paragraph was copied into every semantic field.',
        'why_it_matters':'The exact same paragraph was copied into every semantic field.',
        'suggested_memory':'Use a distinct portable rule after recording a verified observation.',
        'project':'global', 'category':'workflow_hint', 'risk_level':'low',
        'scope':'global', 'domain':'operations',
        'evidence':[{'source_type':'test','source_uri':'test://proposal/schema','quoted_excerpt':'Verified fixture'}],
    }
    path=tmp_path/'duplicate.json'; path.write_text(json.dumps(payload))
    args=c.parser().parse_args(['propose',str(path)])
    with pytest.raises(RuntimeError, match='must be semantically distinct'):
        args.handler(args)
    assert calls == []


def test_client_submits_valid_proposal_with_explicit_identity(monkeypatch, tmp_path):
    c=load(); calls=[]
    monkeypatch.setattr(c,'request',lambda p,**k:calls.append((p,k)) or {'status':'queued'})
    monkeypatch.setenv('BRAIN_AGENT','xiaohe')
    payload = {
        'summary':'Reject prose-only proposals at the client boundary',
        'observation':'A fixture confirmed that copied prose can populate unrelated fields without client validation.',
        'why_it_matters':'Malformed proposals create manual review work and conceal the actual reusable rule.',
        'suggested_memory':'Validate every proposal field and reject placeholders or duplicated core sections before upload.',
        'project':'brain', 'category':'workflow_hint', 'risk_level':'low',
        'scope':'project', 'domain':'agent-infrastructure',
        'evidence':[{'source_type':'test','source_uri':'test://proposal/schema','quoted_excerpt':'The malformed fixture was rejected before request().'}],
    }
    path=tmp_path/'valid.json'; path.write_text(json.dumps(payload))
    args=c.parser().parse_args(['propose',str(path)])
    assert args.handler(args)=={'status':'queued'}
    sent=calls[0][1]['payload']
    assert sent['agent']=='xiaohe'
    assert sent['host_hash']
    assert sent['domain']=='agent-infrastructure'


def test_propose_waits_until_durable_status(monkeypatch, tmp_path):
    c=load();calls=[]
    responses=iter([
        {'schema':1,'status':'queued','proposal_id':'proposal-1'},
        {'schema':1,'status':'queued','proposal_id':'proposal-1'},
        {'schema':1,'status':'ingested_pending','proposal_id':'proposal-1'},
    ])
    monkeypatch.setattr(c,'request',lambda p,**k:calls.append((p,k)) or next(responses))
    monkeypatch.setattr(c.time,'sleep',lambda _seconds:None)
    proposal=tmp_path/'lesson.json'
    proposal.write_text(json.dumps({
        'summary':'Reuse the verified rule',
        'observation':'A complete structured fixture was accepted by the client.',
        'why_it_matters':'Durable receipt must be distinguished from queue acceptance.',
        'suggested_memory':'Wait until the server reports ingested_pending before claiming durable receipt.',
        'project':'brain', 'category':'workflow_hint', 'risk_level':'low',
        'scope':'project', 'domain':'agent-infrastructure',
        'evidence':[{'source_type':'test','source_uri':'test://client/wait','quoted_excerpt':'The server returned ingested_pending.'}],
    }))

    args=c.parser().parse_args(['propose',str(proposal),'--wait','--timeout','5'])
    result=args.handler(args)

    assert result['status']=='ingested_pending'
    assert [p for p,_ in calls]==[
        '/api/v1/brain/propose',
        '/api/v1/brain/proposals/proposal-1',
        '/api/v1/brain/proposals/proposal-1',
    ]


def test_propose_rejects_malformed_evidence_before_request(monkeypatch, tmp_path):
    c=load();calls=[]
    monkeypatch.setattr(c,'request',lambda *a,**k:calls.append((a,k)) or {})
    proposal=tmp_path/'bad.json'
    proposal.write_text(json.dumps({
        'summary':'Reject malformed evidence',
        'observation':'The evidence fixture omits its provenance fields.',
        'why_it_matters':'Untraceable claims cannot support durable shared knowledge.',
        'suggested_memory':'Require source provenance and an exact sanitized excerpt for every evidence item.',
        'project':'brain', 'category':'workflow_hint', 'risk_level':'low',
        'scope':'project', 'domain':'agent-infrastructure',
        'evidence':[{'note':'missing provenance'}],
    }))

    args=c.parser().parse_args(['propose',str(proposal)])
    with pytest.raises(RuntimeError,match='source_type'):
        args.handler(args)
    assert calls==[]


def test_proposal_status_uses_authenticated_get(monkeypatch):
    c=load();calls=[]
    monkeypatch.setattr(c,'request',lambda p,**k:calls.append((p,k)) or {'status':'linked'})
    args=c.parser().parse_args(['proposal-status','literal-id'])

    result=args.handler(args)

    assert result['status']=='linked'
    assert calls==[('/api/v1/brain/proposals/literal-id',{'write':True})]


def test_propose_wait_raises_on_rejected_status(monkeypatch, tmp_path):
    c=load()
    responses=iter([
        {'schema':1,'status':'queued','proposal_id':'proposal-1'},
        {'schema':1,'status':'rejected','proposal_id':'proposal-1','proposal_state':'rejected'},
    ])
    monkeypatch.setattr(c,'request',lambda _path,**_kwargs:next(responses))
    proposal=tmp_path/'lesson.json'
    proposal.write_text(json.dumps({
        'summary':'Surface rejected proposal status',
        'observation':'The server returned a rejected terminal lifecycle status.',
        'why_it_matters':'A rejected proposal must never be reported as durable accepted knowledge.',
        'suggested_memory':'Raise an explicit error whenever proposal polling returns rejected.',
        'project':'brain', 'category':'workflow_hint', 'risk_level':'low',
        'scope':'project', 'domain':'agent-infrastructure',
        'evidence':[{'source_type':'test','source_uri':'test://client/rejected','quoted_excerpt':'The fixture returned status rejected.'}],
    }))
    args=c.parser().parse_args(['propose',str(proposal),'--wait'])

    with pytest.raises(RuntimeError,match='proposal rejected'):
        args.handler(args)


def test_propose_wait_rejects_nonpositive_polling_arguments(tmp_path):
    c=load()
    proposal=tmp_path/'lesson.json'
    proposal.write_text('{"summary":"Reusable rule","observation":"Observed verified behavior","why_it_matters":"It recurs","suggested_memory":"Apply the verified rule","evidence":[{"source_type":"test","source_uri":"test://client"}]}')

    with pytest.raises(SystemExit):
        c.parser().parse_args(['propose',str(proposal),'--wait','--timeout','0'])
    with pytest.raises(SystemExit):
        c.parser().parse_args(['propose',str(proposal),'--wait','--poll-interval','0'])
