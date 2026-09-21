from pathlib import Path
import importlib.util
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
        'scripts/brain_plugin.py',
        'references/protocol.md',
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
