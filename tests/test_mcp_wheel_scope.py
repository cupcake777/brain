"""Build and inspect the promised stdio MCP wheel, without source-cwd imports."""
from pathlib import Path
import subprocess
import sys
import zipfile
import tomllib


def test_wheel_contains_mcp_runtime_and_declares_scope(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['uv', 'build', '--wheel', '--out-dir', str(tmp_path), str(root)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    wheel, = tmp_path.glob('*.whl')
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        for name in ('hermes/mcp_server.py', 'hermes/repository.py', 'hermes/knowledge_store.py', 'hermes/event_store.py'):
            assert name in names
        assert not any(n.startswith(('backups/', 'scripts/', 'tests/')) or n.endswith(('.db', '.sqlite3', '.env', '.key')) for n in names)
        archive.extractall(tmp_path / 'installed')
    result = subprocess.run([sys.executable, '-c', "import sys; sys.path.insert(0, 'installed'); import hermes.mcp_server"], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    project = tomllib.loads((root / 'pyproject.toml').read_text())['project']
    assert project['requires-python'] == '>=3.13'
    assert 'MCP server' in project['description']
