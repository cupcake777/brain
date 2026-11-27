"""Optional integration against the actual installed Hermes Agent, without mocks."""
import os
from pathlib import Path
import subprocess

import pytest


def test_actual_hermes_callable_receives_session_id():
    root = Path(os.environ.get('HERMES_AGENT_ROOT', '/root/hermes-agent'))
    python = root / '.venv/bin/python'
    if not python.exists():
        pytest.skip('installed Hermes Agent integration environment absent')
    plugin = Path(__file__).resolve().parents[1] / '__init__.py'
    code = '''
import importlib.util
from hermes_cli.plugins import PluginManager, PluginContext, PluginManifest
spec = importlib.util.spec_from_file_location('brain_plugin', PLUGIN)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
manager = PluginManager()
ctx = PluginContext(PluginManifest(name='brain', key='brain', source='user'), manager)
module.register(ctx)
sections = manager.render_system_prompt_sections({'session_id': 'actual-framework-session'})
assert any('session_id="actual-framework-session"' in s.content for s in sections)
'''.replace('PLUGIN', repr(str(plugin)))
    result = subprocess.run([str(python), '-c', code], cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr[-2000:]
