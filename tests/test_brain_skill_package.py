from pathlib import Path
import importlib.util
import json
import re
import pytest

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'skills'/'brain-loop'

def load():
    spec=importlib.util.spec_from_file_location('portable_brain',PACKAGE/'scripts'/'brain.py')
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_pyproject_declares_installable_mcp_runtime_contract():
    """pyproject must make the MCP server installable and runnable from any cwd.

    Regression for: `python -m hermes.mcp_server` only worked when cwd was the
    repo (import via sys.path[0]) and `mcp` was an undeclared venv dependency.
    """
    import tomllib

    data = tomllib.loads((ROOT / 'pyproject.toml').read_text())

    build = data.get('build-system', {})
    assert build.get('build-backend'), 'pyproject must declare a PEP 517 build backend'

    deps = data['project']['dependencies']
    dep_names = {re.split(r'[<>=!~;,\[]', d.strip())[0] for d in deps}
    assert 'mcp' in dep_names, f'mcp must be a declared runtime dependency (got {sorted(dep_names)})'

    scripts = data['project'].get('scripts', {})
    assert any(
        str(target).split(':')[0] == 'hermes.mcp_server'
        for target in scripts.values()
    ), f'[project.scripts] must expose a hermes.mcp_server console entrypoint (got {scripts})'

    packages = data.get('tool', {}).get('setuptools', {}).get('packages')
    assert packages and 'hermes' in packages, (
        'setuptools package discovery must be pinned to the hermes package '
        '(flat-layout auto-discovery fails on this repo)'
    )


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
    prompt = ctx.prompt_sections[0][1]
    assert callable(prompt)
    rendered = prompt({'session_id': 'session-real-1', 'platform': 'telegram'})
    assert 'brain:brain-loop' in rendered
    assert 'session-real-1' in rendered
    assert 'retrieve_knowledge' in rendered
    assert 'report_knowledge_outcome' in rendered
    assert 'finalize_knowledge_session' in rendered
    assert 'Do not retrieve for trivial tasks' in rendered
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
    monkeypatch.setattr(c, 'config_dir', lambda: Path('/nonexistent-brain-config'))
    assert c.api_url()=='http://127.0.0.1:8083'


def test_client_accepts_owner_only_token_file(monkeypatch, tmp_path):
    c=load()
    token_file=tmp_path/'token'
    token_file.write_text('file-secret\n')
    token_file.chmod(0o600)
    monkeypatch.delenv('BRAIN_TOKEN',raising=False)
    monkeypatch.setenv('BRAIN_TOKEN_FILE',str(token_file))
    monkeypatch.setattr(c.urllib.request,'urlopen',lambda request,timeout: (_ for _ in ()).throw(RuntimeError(request.headers['Authorization'])))
    with pytest.raises(RuntimeError,match='Bearer file-secret'):
        c.request('/api/test',payload={},write=True)


def test_plugin_manifest_uses_token_file_without_copying_secret_into_env():
    text=(ROOT/'plugin.yaml').read_text()
    assert 'name: BRAIN_TOKEN_FILE' in text
    assert 'name: BRAIN_TOKEN\n' not in text


def test_client_reads_url_token_and_ca_from_config(monkeypatch, tmp_path):
    c = load()
    cfg = tmp_path / 'brain'
    cfg.mkdir()
    (cfg / 'url').write_text('https://brain.example\n')
    (cfg / 'token').write_text('scoped-token\n')
    ca = tmp_path / 'ca-bundle.crt'
    ca.write_text('test-ca')
    (cfg / 'ca-bundle').write_text(f'{ca}\n')
    for name in ('BRAIN_URL', 'BRAIN_TOKEN', 'BRAIN_TOKEN_FILE', 'BRAIN_CA_BUNDLE', 'SSL_CERT_FILE'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(c, 'config_dir', lambda: cfg)
    monkeypatch.setattr(c.urllib.request, 'urlopen', lambda *_a, **_k: pytest.fail('stop after config resolution'))

    assert c.api_url() == 'https://brain.example'
    assert c.resolve_token() == 'scoped-token'
    assert c.resolve_ca_bundle() == ca


def test_config_ca_overrides_inherited_ssl_cert_file(monkeypatch, tmp_path):
    c = load()
    cfg = tmp_path / 'brain'
    cfg.mkdir()
    configured_ca = tmp_path / 'configured-ca.crt'
    configured_ca.write_text('configured-ca')
    inherited_ca = tmp_path / 'inherited-ca.crt'
    inherited_ca.write_text('inherited-ca')
    (cfg / 'ca-bundle').write_text(f'{configured_ca}\n')
    monkeypatch.delenv('BRAIN_CA_BUNDLE', raising=False)
    monkeypatch.setenv('SSL_CERT_FILE', str(inherited_ca))
    monkeypatch.setattr(c, 'config_dir', lambda: cfg)

    assert c.resolve_ca_bundle() == configured_ca


def test_http_request_ignores_stale_ca_config(monkeypatch, tmp_path):
    c = load()
    cfg = tmp_path / 'brain'
    cfg.mkdir()
    (cfg / 'ca-bundle').write_text(f'{tmp_path / "missing-ca.crt"}\n')
    monkeypatch.setenv('BRAIN_URL', 'http://127.0.0.1:8083')
    monkeypatch.delenv('BRAIN_CA_BUNDLE', raising=False)
    monkeypatch.delenv('SSL_CERT_FILE', raising=False)
    monkeypatch.setattr(c, 'config_dir', lambda: cfg)
    captured = {}

    class Reply:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self): return b'{"status":"ok"}'

    def urlopen(req, **kwargs):
        captured['authorization'] = req.get_header('Authorization')
        captured['kwargs'] = kwargs
        return Reply()

    monkeypatch.setattr(c.urllib.request, 'urlopen', urlopen)
    assert c.command_health(None) == {'status': 'ok'}
    assert captured == {'authorization': None, 'kwargs': {'timeout': 20}}


def test_explicit_missing_token_file_does_not_fall_back(monkeypatch, tmp_path):
    c = load()
    cfg = tmp_path / 'brain'
    cfg.mkdir()
    (cfg / 'token').write_text('unexpected-fallback-token\n')
    missing = tmp_path / 'missing-token'
    monkeypatch.delenv('BRAIN_TOKEN', raising=False)
    monkeypatch.setenv('BRAIN_TOKEN_FILE', str(missing))
    monkeypatch.setattr(c, 'config_dir', lambda: cfg)

    with pytest.raises(RuntimeError, match='BRAIN_TOKEN_FILE'):
        c.resolve_token()


def test_client_passes_explicit_ssl_context(monkeypatch, tmp_path):
    c = load()
    ca = tmp_path / 'ca-bundle.crt'
    ca.write_text('test-ca')
    monkeypatch.setenv('BRAIN_URL', 'https://brain.example')
    monkeypatch.setenv('BRAIN_TOKEN', 'scoped-token')
    monkeypatch.setenv('BRAIN_CA_BUNDLE', str(ca))
    context_marker = object()
    monkeypatch.setattr(c.ssl, 'create_default_context', lambda *, cafile: context_marker if cafile == str(ca) else None)
    captured = {}

    class Reply:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self): return b'{"status":"ok"}'

    def urlopen(_req, **kwargs):
        captured.update(kwargs)
        return Reply()

    monkeypatch.setattr(c.urllib.request, 'urlopen', urlopen)
    assert c.command_health(None) == {'status': 'ok'}
    assert captured['context'] is context_marker


def test_uppercase_https_scheme_still_uses_tls_context_and_optional_auth(monkeypatch, tmp_path):
    c = load()
    ca = tmp_path / 'ca-bundle.crt'
    ca.write_text('test-ca')
    monkeypatch.setenv('BRAIN_URL', 'HTTPS://brain.example')
    monkeypatch.setenv('BRAIN_TOKEN', 'scoped-token')
    monkeypatch.setenv('BRAIN_CA_BUNDLE', str(ca))
    context_marker = object()
    monkeypatch.setattr(c.ssl, 'create_default_context', lambda *, cafile: context_marker)
    captured = {}

    class Reply:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self): return b'{"status":"ok"}'

    def urlopen(req, **kwargs):
        captured['authorization'] = req.get_header('Authorization')
        captured['context'] = kwargs.get('context')
        return Reply()

    monkeypatch.setattr(c.urllib.request, 'urlopen', urlopen)
    assert c.command_health(None) == {'status': 'ok'}
    assert captured == {
        'authorization': 'Bearer scoped-token',
        'context': context_marker,
    }

def test_finalize_uses_auth_and_minimal_payload(monkeypatch):
    c=load();calls=[]
    monkeypatch.setattr(c,'request',lambda p,**k:calls.append((p,k)) or {})
    args=c.parser().parse_args(['finalize','--session-id','session-1'])
    args.handler(args)
    assert calls[0][0]=='/api/v1/brain/finalize'
    assert calls[0][1]['write'] is True
    assert set(calls[0][1]['payload'])=={'agent','host_hash','session_id'}


def test_health_uses_optional_authenticated_get(monkeypatch):
    c=load();calls=[]
    monkeypatch.setattr(c,'request',lambda p,**k:calls.append((p,k)) or {'status':'ok'})
    args=c.parser().parse_args(['health'])
    assert args.handler(args)=={'status':'ok'}
    assert calls==[('/api/v1/brain/health',{'optional_auth':True})]

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


@pytest.mark.parametrize('explicit,brain_session,codex_session,expected', [
    ('explicit-session', 'brain-session', 'codex-session', 'explicit-session'),
    ('', 'brain-session', 'codex-session', 'brain-session'),
    ('', '  ', 'codex-session', 'codex-session'),
    ('', '', '', ''),
])
def test_retrieve_and_finalize_share_real_session_resolution(monkeypatch, explicit, brain_session, codex_session, expected):
    c = load()
    calls = []
    monkeypatch.setenv('BRAIN_SESSION_ID', brain_session)
    monkeypatch.setenv('CODEX_THREAD_ID', codex_session)
    monkeypatch.setattr(c, 'request', lambda path, **kwargs: calls.append((path, kwargs)) or {})
    flags = ['--session-id', explicit] if explicit else []
    retrieve = c.parser().parse_args(['retrieve', 'session attribution', *flags])
    retrieve.handler(retrieve)
    assert calls[0][1]['payload']['session_id'] == expected
    assert calls[0][1]['optional_auth'] is True
    finalize = c.parser().parse_args(['finalize', *flags])
    if expected:
        finalize.handler(finalize)
        assert calls[1][1]['payload']['session_id'] == expected
    else:
        with pytest.raises(RuntimeError, match='session_id is required'):
            finalize.handler(finalize)
        assert len(calls) == 1


def test_retrieve_attaches_configured_token_over_https(monkeypatch, tmp_path):
    c = load()
    monkeypatch.setenv('BRAIN_URL', 'https://brain.example')
    monkeypatch.setenv('BRAIN_TOKEN', 'scoped-test-token')
    monkeypatch.setattr(c, 'resolve_ca_bundle', lambda: None)
    captured = {}

    class Reply:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self): return b'{"results":[]}'

    def urlopen(req, **kwargs):
        captured['authorization'] = req.get_header('Authorization')
        captured['payload'] = json.loads(req.data)
        return Reply()

    monkeypatch.setattr(c.urllib.request, 'urlopen', urlopen)
    args = c.parser().parse_args(['retrieve', 'Brain feedback'])
    assert args.handler(args) == {'results': []}
    assert captured['authorization'] == 'Bearer scoped-test-token'
    assert captured['payload']['query'] == 'Brain feedback'


def test_token_file_takes_precedence_over_legacy_environment(monkeypatch, tmp_path):
    c = load()
    token_file = tmp_path / 'token'
    token_file.write_text('file-fixture')
    monkeypatch.setenv('BRAIN_TOKEN_FILE', str(token_file))
    monkeypatch.setenv('BRAIN_TOKEN', 'env-fixture')
    assert c.resolve_token() == 'file-fixture'
