"""Tests for Task 4 capture: stable, sanitized, no-replay capture from post_tool_call.

The capture layer is independent of the existing outbox: tests inject a
fake persist/enqueue callback, so capture never imports the real outbox.
The hook adapter wraps ``post_tool_call`` so a Python plugin can register
capture via ``register(ctx)`` with no global state.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "brain-loop" / "scripts"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import agent_capture as capture_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeSink:
    """In-memory replacement for the persist/enqueue callback."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self.errors: list[Exception] = []

    def __call__(self, record: dict[str, Any]) -> None:
        self.records.append(record)

    @property
    def fail_next(self) -> "_FailNextSink":
        return _FailNextSink(self)


class _FailNextSink:
    def __init__(self, parent: FakeSink) -> None:
        self.parent = parent

    def __call__(self, record: dict[str, Any]) -> None:
        if not self.parent.errors:
            self.parent.errors.append(RuntimeError("boom"))
            raise self.parent.errors[0]
        self.parent.records.append(record)


def _ctx(
    *,
    invocation_id: str | None = "inv-1",
    session_id: str | None = "sess-1",
    occurred_at: float | None = 1700000000.0,
    project_id: str | None = "proj-7",
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = {
        "tool_name": "terminal",
        "args": {"command": "ls"},
        "result": "file1\nfile2\n",
        "error": None,
        "invocation_id": invocation_id,
        "session_id": session_id,
        "occurred_at": occurred_at,
        "project_id": project_id,
    }
    if extras:
        ctx.update(extras)
    return ctx


# ---------------------------------------------------------------------------
# Stable dedup
# ---------------------------------------------------------------------------


def test_capture_emits_stable_uuid_from_trusted_context() -> None:
    sink = FakeSink()
    cap = capture_mod.AgentCapture(sink=sink)

    ctx = _ctx(invocation_id="inv-A", session_id="sess-X", occurred_at=12345.0)
    a = cap.handle_post_tool_call(ctx)
    b = cap.handle_post_tool_call(ctx)

    assert a == b  # same trusted identity -> same capture id
    assert len(sink.records) == 2
    assert sink.records[0]["id"] == sink.records[1]["id"]


def test_capture_id_is_uuid() -> None:
    sink = FakeSink()
    cap = capture_mod.AgentCapture(sink=sink)
    rec_id = cap.handle_post_tool_call(_ctx())
    # Recover the actual stored id (sink stores one record per call)
    assert sink.records
    assert sink.records[0]["id"] == rec_id
    uuid.UUID(sink.records[0]["id"])  # must parse as a real UUID


def test_capture_id_varies_with_invocation() -> None:
    sink = FakeSink()
    cap = capture_mod.AgentCapture(sink=sink)
    cap.handle_post_tool_call(_ctx(invocation_id="inv-A"))
    cap.handle_post_tool_call(_ctx(invocation_id="inv-B"))
    ids = {r["id"] for r in sink.records}
    assert len(ids) == 2


# ---------------------------------------------------------------------------
# Tolerate missing/nullable trusted context
# ---------------------------------------------------------------------------


def test_capture_handles_missing_occurred_at_and_project() -> None:
    sink = FakeSink()
    cap = capture_mod.AgentCapture(sink=sink, clock=lambda: 999.0)
    rec_id = cap.handle_post_tool_call(_ctx(occurred_at=None, project_id=None))
    assert sink.records
    rec = sink.records[0]
    assert rec["id"] == rec_id
    # occurred_at must be filled in deterministically from the injected clock
    assert rec["occurred_at"] == 999.0
    assert rec["project_id"] is None


def test_capture_handles_missing_invocation_id_without_raising() -> None:
    sink = FakeSink()
    cap = capture_mod.AgentCapture(sink=sink)
    rec_id = cap.handle_post_tool_call(_ctx(invocation_id=None))
    assert sink.records
    assert sink.records[0]["id"] == rec_id


# ---------------------------------------------------------------------------
# Targeted context only — no transcripts / model / network
# ---------------------------------------------------------------------------


def test_capture_record_does_not_contain_transcript_or_model_or_network() -> None:
    sink = FakeSink()
    cap = capture_mod.AgentCapture(sink=sink)
    ctx = _ctx(
        extras={
            "messages": [{"role": "user", "content": "secret prompt"}],
            "model": "gpt-5.5",
            "api_key": "sk-LIVE",
            "network": {"endpoint": "https://api.openai.com"},
        }
    )
    cap.handle_post_tool_call(ctx)
    rec = sink.records[0]
    # Serialize and grep everywhere
    blob = json.dumps(rec, default=str)
    for forbidden in ("messages", "model", "api_key", "network",
                      "secret prompt", "sk-LIVE", "openai.com"):
        assert forbidden not in blob, f"capture leaked: {forbidden}"


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------


def test_capture_redacts_secrets_in_args_and_result() -> None:
    sink = FakeSink()
    cap = capture_mod.AgentCapture(sink=sink, redact_keys={"api_key", "token"})
    ctx = _ctx(
        extras={
            "args": {"command": "curl -H 'X-API-Key: ABC123' ", "api_key": "sk-LIVE"},
            "result": "ok token=XYZ987 next-line",
        }
    )
    cap.handle_post_tool_call(ctx)
    rec = sink.records[0]
    assert rec["args"]["api_key"] == "[REDACTED]"
    assert rec["args"]["command"].startswith("curl")
    assert "ABC123" in rec["args"]["command"]  # free-text secrets not auto-redacted,
    # but the structured api_key IS removed. That is the contract.
    assert rec["result"].startswith("ok token=")
    # Token value in plain text is preserved unless caller passes a custom
    # regex; the default is structured redaction. Document via test.


# ---------------------------------------------------------------------------
# Interrupted / unknown result
# ---------------------------------------------------------------------------


def test_interrupted_or_unknown_result_is_recorded_not_replayed() -> None:
    sink = FakeSink()
    cap = capture_mod.AgentCapture(sink=sink)
    # Agent interrupted mid-tool: result is None, error is None
    ctx = _ctx(extras={"result": None, "error": None, "interrupted": True})
    cap.handle_post_tool_call(ctx)
    rec = sink.records[0]
    assert rec["result_state"] == "interrupted"
    # Unknown result: result is None but no error and not flagged interrupted
    ctx2 = _ctx(extras={"result": None, "error": None}, invocation_id="inv-2")
    cap.handle_post_tool_call(ctx2)
    rec2 = sink.records[1]
    assert rec2["result_state"] == "unknown"
    # Neither path should raise or auto-retry
    assert len(sink.records) == 2


# ---------------------------------------------------------------------------
# Tool errors captured honestly
# ---------------------------------------------------------------------------


def test_capture_records_tool_error_honestly() -> None:
    sink = FakeSink()
    cap = capture_mod.AgentCapture(sink=sink)
    ctx = _ctx(extras={"result": None, "error": "PermissionError: nope"})
    cap.handle_post_tool_call(ctx)
    rec = sink.records[0]
    assert rec["result_state"] == "error"
    assert rec["error"] == "PermissionError: nope"


# ---------------------------------------------------------------------------
# Sink failure must not crash capture
# ---------------------------------------------------------------------------


def test_sink_failure_does_not_crash_capture() -> None:
    sink = FakeSink()
    cap = capture_mod.AgentCapture(sink=sink.fail_next)
    # First call raises inside the sink; capture must swallow and still
    # report the id without raising into the plugin framework.
    rec_id = cap.handle_post_tool_call(_ctx(invocation_id="inv-X"))
    assert rec_id  # got an id back even though persist failed
    # Subsequent call succeeds
    cap.handle_post_tool_call(_ctx(invocation_id="inv-Y"))
    assert len(sink.records) == 1
    assert sink.records[0]["id"] != rec_id  # second record has its own id


# ---------------------------------------------------------------------------
# Portable hook adapter
# ---------------------------------------------------------------------------


def test_hook_adapter_registers_post_tool_call_callback_only() -> None:
    registered: dict[str, Any] = {}
    adapter = capture_mod.HookAdapter(capture=capture_mod.AgentCapture(sink=FakeSink()))

    class _StubCtx:
        def __init__(self) -> None:
            self.calls: list[tuple[str, Any]] = []

        def register_hook(self, name: str, cb: Any) -> None:
            self.calls.append((name, cb))
            registered[name] = cb

    stub = _StubCtx()
    adapter.register(stub)
    assert [n for n, _ in stub.calls] == ["post_tool_call"]
    # Calling the registered callback must hit capture and not raise even
    # with minimal context (the adapter normalizes / tolerates missing fields).
    # The hook contract is "observer"; return value is ignored by the runtime.
    cb = registered["post_tool_call"]
    assert cb({"tool_name": "terminal", "args": {}, "result": "ok"}) is None  # observer hook
