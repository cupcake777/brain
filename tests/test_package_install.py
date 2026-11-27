"""Regression: the project must be pip-installable and the MCP server must
run from an arbitrary cwd.

Root cause being locked down: `python -m hermes.mcp_server` only worked when
cwd happened to be the repo (import resolved via sys.path[0]) and the `mcp`
package was an undeclared, manually-installed venv dependency. Installing the
project into an isolated venv must be enough to import and launch it.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALL_TIMEOUT = 300


def _mcp_entrypoint_name() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    for name, target in data["project"].get("scripts", {}).items():
        if str(target).split(":")[0] == "hermes.mcp_server":
            return name
    pytest.fail("[project.scripts] has no hermes.mcp_server console entrypoint")


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, timeout=INSTALL_TIMEOUT
    )


def test_install_into_isolated_venv_runs_mcp_server_from_any_cwd(tmp_path: Path) -> None:
    uv = shutil.which("uv") or shutil.which("uvx")
    if not uv:
        pytest.skip("uv not available for isolated-venv install")

    venv_dir = tmp_path / "isolated-venv"
    create = _run([uv, "venv", str(venv_dir)], cwd=tmp_path)
    assert create.returncode == 0, create.stderr
    venv_python = venv_dir / "bin" / "python"

    # Run from an unrelated cwd: the repo must not be on sys.path.
    install = _run([uv, "pip", "install", "--python", str(venv_python), str(ROOT)], cwd=tmp_path)
    assert install.returncode == 0, (
        f"uv pip install of the project failed:\n{install.stderr[-3000:]}"
    )

    imported = _run(
        [str(venv_python), "-c", "import hermes.mcp_server"],
        cwd=tmp_path,
    )
    assert imported.returncode == 0, f"import hermes.mcp_server failed:\n{imported.stderr}"

    cli = _run([str(venv_python), "-m", "hermes.mcp_server", "--help"], cwd=tmp_path)
    assert cli.returncode == 0, f"python -m hermes.mcp_server --help failed:\n{cli.stderr}"
    assert "--sync-root" in cli.stdout

    entrypoint = venv_dir / "bin" / _mcp_entrypoint_name()
    assert entrypoint.is_file(), f"console entrypoint {entrypoint} was not installed"
    script = _run([str(entrypoint), "--help"], cwd=tmp_path)
    assert script.returncode == 0, f"{entrypoint.name} --help failed:\n{script.stderr}"
    assert "--sync-root" in script.stdout
