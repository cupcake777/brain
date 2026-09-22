"""Tests for the cross-host hook launcher (Claude Code / Codex)."""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "brain-loop" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("brain_hook_launcher", SCRIPTS / "brain_hook_launcher.py")
assert spec and spec.loader
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

import multi_agent_adapter as adapter  # noqa: E402
from outbox import Outbox  # noqa: E402


def test_credentials_prefer_env(monkeypatch):
    monkeypatch.setenv("BRAIN_AGENT", "env-agent")
    monkeypatch.setenv("BRAIN_URL", "https://env.example")
    monkeypatch.setenv("BRAIN_TOKEN", "env-token")
    creds = launcher.resolve_credentials("claude-code")
    assert creds == {"agent": "env-agent", "url": "https://env.example", "token": "env-token"}


def test_credentials_fall_back_to_config_file(monkeypatch, tmp_path):
    cfg = tmp_path / "brain"
    cfg.mkdir()
    (cfg / "url").write_text("https://file.example\n")
    (cfg / "token").write_text("file-token\n")
    for var in ("BRAIN_AGENT", "BRAIN_URL", "BRAIN_TOKEN", "BRAIN_TOKEN_FILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(launcher, "_config_dir", lambda: cfg)
    creds = launcher.resolve_credentials("codex")
    assert creds == {"agent": "codex", "url": "https://file.example", "token": "file-token"}


def test_missing_credentials_return_empty_token(monkeypatch, tmp_path):
    for var in ("BRAIN_AGENT", "BRAIN_URL", "BRAIN_TOKEN", "BRAIN_TOKEN_FILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(launcher, "_config_dir", lambda: tmp_path / "nonexistent")
    creds = launcher.resolve_credentials("claude-code")
    assert creds == {"agent": "claude-code", "url": "", "token": ""}


def test_token_file_preferred_over_default_config(monkeypatch, tmp_path):
    token_file = tmp_path / "token.txt"
    token_file.write_text("explicit-token\n")
    cfg = tmp_path / "brain"
    cfg.mkdir()
    (cfg / "token").write_text("config-token\n")
    monkeypatch.delenv("BRAIN_TOKEN", raising=False)
    monkeypatch.setenv("BRAIN_TOKEN_FILE", str(token_file))
    monkeypatch.setattr(launcher, "_config_dir", lambda: cfg)
    creds = launcher.resolve_credentials("claude-code")
    assert creds["token"] == "explicit-token"


def test_hook_captures_into_outbox(monkeypatch, tmp_path):
    """The launcher delegates hook+flush to the adapter with resolved creds."""
    monkeypatch.setenv("BRAIN_OUTBOX", str(tmp_path / "outbox.sqlite3"))
    monkeypatch.setenv("BRAIN_AGENT", "codex")
    monkeypatch.delenv("BRAIN_URL", raising=False)
    monkeypatch.delenv("BRAIN_TOKEN", raising=False)
    monkeypatch.setattr(launcher, "_config_dir", lambda: tmp_path / "nonexistent")

    captured = adapter.capture("codex", {
        "session_id": "s",
        "tool_use_id": "t",
        "hook_event_name": "PostToolUse",
        "tool_name": "shell",
        "tool_input": {"api_key": "secret-value"},
        "tool_response": {"exit_code": 0},
        "cwd": str(tmp_path),
    })
    assert captured["status"] == "enqueued"
    outbox = Outbox(tmp_path / "outbox.sqlite3")
    try:
        row = outbox._conn.execute("SELECT payload_json FROM jobs").fetchone()
        assert row is not None
        assert "secret-value" not in row[0]
        assert "[REDACTED]" in row[0]
    finally:
        outbox.close()


def test_codex_manifest_uses_own_source_and_bounded_session_end():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert manifest["version"] == "1.2.1"
    hooks = json.loads((ROOT / manifest["hooks"]).read_text())["hooks"]
    for event in ("PostToolUse", "PostToolUseFailure"):
        handler = hooks[event][0]["hooks"][0]
        assert handler["command"].endswith(" hook codex")
        assert handler["async"] is True
    ending = hooks["SessionEnd"][0]["hooks"][0]
    assert ending["timeout"] <= 3
    assert ending["command"].endswith(" flush-background")
    claude = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert claude["hooks"] != manifest["hooks"]
    claude_hooks = json.loads((ROOT / claude["hooks"]).read_text())["hooks"]
    assert claude_hooks["PostToolUse"][0]["hooks"][0]["command"].endswith(" hook claude-code")


def test_codex_hook_records_codex_identity(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAIN_OUTBOX", str(tmp_path / "outbox.sqlite3"))
    monkeypatch.delenv("BRAIN_AGENT", raising=False)
    monkeypatch.setattr(launcher, "_config_dir", lambda: tmp_path / "missing")
    monkeypatch.setattr(adapter, "drain", lambda limit: {})
    monkeypatch.setattr(sys, "argv", ["brain_hook_launcher.py", "hook", "codex"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "session_id": "s", "tool_use_id": "t", "hook_event_name": "PostToolUse",
        "tool_name": "Bash", "cwd": str(tmp_path),
    })))
    assert launcher.main() == 0
    outbox = Outbox(tmp_path / "outbox.sqlite3")
    try:
        payload = json.loads(outbox._conn.execute("SELECT payload_json FROM jobs").fetchone()[0])
        assert payload["agent_id"] == "codex"
        assert payload["action"] == "codex PostToolUse Bash completed"
    finally:
        outbox.close()


def test_session_end_detaches_flush(monkeypatch):
    calls = []
    monkeypatch.setattr(launcher, "_apply_credentials", lambda host: None)
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", ["brain_hook_launcher.py", "flush-background"])
    assert launcher.main() == 0
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0][2] == "flush"
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.DEVNULL
