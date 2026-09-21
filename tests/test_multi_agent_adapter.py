from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "brain-loop" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("multi_agent_adapter", SCRIPTS / "multi_agent_adapter.py")
assert spec and spec.loader
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
from outbox import Outbox, TransportResult


def test_capture_redacts_content_and_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAIN_OUTBOX", str(tmp_path / "outbox.sqlite3"))
    monkeypatch.setenv("BRAIN_PROJECT", "paper")
    monkeypatch.delenv("BRAIN_URL", raising=False)
    assert adapter._url() == "http://127.0.0.1:8083"
    payload = {
        "session_id": "session-1",
        "tool_use_id": "tool-1",
        "cwd": str(tmp_path),
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/private/paper.md",
            "content": "unpublished manuscript",
            "api_key": "secret-value",
        },
        "tool_response": {"filePath": "/private/paper.md", "type": "create"},
    }
    first = adapter.capture("claude-code", payload)
    second = adapter.capture("claude-code", payload)
    assert first["status"] == "enqueued"
    assert second["status"] == "duplicate"
    outbox = Outbox(tmp_path / "outbox.sqlite3")
    try:
        job = outbox.get(first["id"])
        assert job is not None
        assert job.payload["project_id"] == "paper"
        captured = job.payload["capture"]["input"]
        assert captured["content"] == "[REDACTED]"
        assert captured["api_key"] == "[REDACTED]"
        assert "unpublished manuscript" not in json.dumps(job.payload)
    finally:
        outbox.close()


def test_capture_environment_operation_sets_target(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAIN_OUTBOX", str(tmp_path / "outbox.sqlite3"))
    result = adapter.capture("codex", {
        "session_id": "s",
        "tool_use_id": "t",
        "hook_event_name": "PostToolUse",
        "tool_name": "systemctl restart brain",
        "tool_response": {"exit_code": 0},
        "cwd": str(tmp_path),
    })
    outbox = Outbox(tmp_path / "outbox.sqlite3")
    try:
        assert outbox.get(result["id"]).payload["target_id"]
    finally:
        outbox.close()


def test_drain_uses_exact_ack(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAIN_OUTBOX", str(tmp_path / "outbox.sqlite3"))
    captured = adapter.capture("hermes", {
        "session_id": "s",
        "tool_use_id": "t",
        "hook_event_name": "post_tool_call",
        "tool_name": "terminal",
        "result": {"exit_code": 0},
        "cwd": str(tmp_path),
    })
    def fake_upload(job):
        return TransportResult(
            state="ok",
            acknowledged_version=job.version,
            response={"id": job.id, "version": job.version, "digest": "d" * 64},
        )
    monkeypatch.setattr(adapter, "upload", fake_upload)
    result = adapter.drain(5)
    assert result["completed"] == 1
    outbox = Outbox(tmp_path / "outbox.sqlite3")
    try:
        assert outbox.get(captured["id"]).state == "completed"
    finally:
        outbox.close()


def test_hook_cli_accepts_json(tmp_path):
    env = os.environ.copy()
    env["BRAIN_OUTBOX"] = str(tmp_path / "outbox.sqlite3")
    process = subprocess.run(
        [sys.executable, str(SCRIPTS / "multi_agent_adapter.py"), "hook", "--source", "codex"],
        input=json.dumps({
            "session_id": "s",
            "tool_use_id": "t",
            "hook_event_name": "PostToolUse",
            "tool_name": "shell",
            "tool_response": {"exit_code": 0},
            "cwd": str(tmp_path),
        }),
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    assert json.loads(process.stdout)["status"] == "enqueued"


def test_concurrent_flushes_are_serialized(tmp_path, monkeypatch):
    import threading
    monkeypatch.setenv("BRAIN_OUTBOX", str(tmp_path / "outbox.sqlite3"))
    results = []
    errors = []
    def run():
        try:
            results.append(adapter.flush(2))
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert errors == []
    assert len(results) == 2


def test_brain_plugin_translates_hermes_payload_and_captures(tmp_path, monkeypatch):
    plugin_path = SCRIPTS / "brain_plugin.py"
    spec = importlib.util.spec_from_file_location("brain_plugin_adapter", plugin_path)
    assert spec and spec.loader
    brain_plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(brain_plugin)
    monkeypatch.setenv("BRAIN_OUTBOX", str(tmp_path / "hermes.sqlite3"))
    monkeypatch.setenv("BRAIN_AGENT", "hermes-test")

    result = brain_plugin.capture_post_tool_call(
        tool_name="terminal",
        args={"command": "printf ok", "api_key": "secret-value"},
        result={"output": "ok", "exit_code": 0},
        status="ok",
        session_id="session-1",
        tool_call_id="call-1",
    )
    assert result["status"] == "enqueued"
    outbox = Outbox(tmp_path / "hermes.sqlite3")
    try:
        job = outbox.get(result["id"])
        assert job is not None
        assert job.payload["agent_id"] == "hermes-test"
        assert job.payload["capture"]["input"]["api_key"] == "[REDACTED]"
        assert "secret-value" not in json.dumps(job.payload)
    finally:
        outbox.close()


def test_brain_plugin_finalize_flushes_without_raising(monkeypatch):
    plugin_path = SCRIPTS / "brain_plugin.py"
    spec = importlib.util.spec_from_file_location("brain_plugin_finalize", plugin_path)
    assert spec and spec.loader
    brain_plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(brain_plugin)
    called = []
    monkeypatch.setattr(brain_plugin.adapter, "flush", lambda limit=25: called.append(limit) or {})
    brain_plugin.flush_session()
    assert called == [25]


def test_flush_degrades_gracefully_without_fcntl(tmp_path, monkeypatch):
    import builtins
    monkeypatch.setenv("BRAIN_OUTBOX", str(tmp_path / "outbox.sqlite3"))
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "fcntl":
            raise ImportError("fcntl unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = adapter.flush(5)
    assert set(result) == {"reconcile", "drain"}
    assert isinstance(result["drain"], dict)
