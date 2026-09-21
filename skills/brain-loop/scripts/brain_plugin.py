"""Native Hermes hook bridge for the portable Brain adapter.

The callbacks stay fail-open and return immediately. Capture writes to the
local durable outbox first; upload runs in a daemon worker so Brain/network
latency never blocks Hermes tool execution.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

_spec = importlib.util.spec_from_file_location(
    "brain_multi_agent_adapter", SCRIPT_DIR / "multi_agent_adapter.py"
)
if _spec is None or _spec.loader is None:
    raise RuntimeError("Brain multi-agent adapter could not be loaded")
adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adapter)


def _ensure_defaults() -> None:
    os.environ.setdefault("BRAIN_AGENT", "hermes")
    os.environ.setdefault(
        "BRAIN_OUTBOX",
        str(Path.home() / ".local" / "state" / "brain-loop" / "hermes-outbox.sqlite3"),
    )


def capture_post_tool_call(**kwargs: Any) -> dict[str, Any]:
    """Translate the Hermes observer payload and persist one sanitized event."""
    _ensure_defaults()
    status = str(kwargs.get("status") or "")
    error = kwargs.get("error_message") or (
        status if status in {"error", "blocked", "cancelled"} else None
    )
    payload = {
        "session_id": kwargs.get("session_id"),
        "tool_use_id": kwargs.get("tool_call_id"),
        "cwd": kwargs.get("cwd") or os.getcwd(),
        "hook_event_name": "post_tool_call",
        "tool_name": kwargs.get("tool_name"),
        "tool_input": kwargs.get("args") or {},
        "tool_response": kwargs.get("result"),
        "result": kwargs.get("result"),
        "error": error,
    }
    return adapter.capture("hermes", payload)


def _drain() -> None:
    try:
        adapter.drain(5)
    except Exception as exc:
        logger.warning("Brain upload deferred: %s", type(exc).__name__)


def post_tool_call(**kwargs: Any) -> None:
    """Capture synchronously to local SQLite, then upload asynchronously."""
    try:
        capture_post_tool_call(**kwargs)
    except Exception as exc:
        logger.warning("Brain capture unavailable: %s", type(exc).__name__)
        return
    threading.Thread(target=_drain, name="brain-upload", daemon=True).start()


def flush_session() -> None:
    _ensure_defaults()
    try:
        adapter.flush(25)
    except Exception as exc:
        logger.warning("Brain session flush deferred: %s", type(exc).__name__)


def on_session_finalize(**_: Any) -> None:
    flush_session()


def on_session_reset(**_: Any) -> None:
    flush_session()
