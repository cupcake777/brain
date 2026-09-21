#!/usr/bin/env python3
"""Cross-agent Brain adapter: durable hook capture and V2 upload."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import socket
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from outbox import DuplicateJobError, Job, Outbox, TransportResult  # noqa: E402

_SECRET_KEYS = frozenset({
    "api_key", "apikey", "authorization", "auth", "token", "password",
    "secret", "private_key", "session_token", "bearer", "content",
})
_SECRET_TEXT = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"\b(?:sk|ghp|hf)_[A-Za-z0-9_\-]{12,}\b"),
)
_ENV_OP = re.compile(r"\b(ssh|systemctl|rm|docker|kubectl|terraform)\b", re.I)


def _trim(text: str, limit: int = 1000) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _redact_text(text: str) -> str:
    result = text
    for pattern in _SECRET_TEXT:
        result = pattern.sub("[REDACTED]", result)
    return _trim(result)


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[TRUNCATED]"
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, item in list(value.items())[:50]:
            name = str(key)
            if name.lower() in _SECRET_KEYS:
                clean[name] = "[REDACTED]"
            else:
                clean[name] = _sanitize(item, depth=depth + 1)
        return clean
    if isinstance(value, (list, tuple)):
        return [_sanitize(item, depth=depth + 1) for item in list(value)[:50]]
    if isinstance(value, str):
        return _redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(repr(value))


def _read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("hook input must be a JSON object")
    return payload


def _project_from(cwd: str | None) -> str:
    override = os.environ.get("BRAIN_PROJECT", "").strip()
    if override:
        return override[:64]
    path = Path(cwd or os.getcwd()).resolve()
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate.name[:64] or "general"
    return path.name[:64] or "general"


def _outbox_path() -> Path:
    return Path(os.environ.get(
        "BRAIN_OUTBOX",
        str(Path.home() / ".local" / "state" / "brain-loop" / "outbox.sqlite3"),
    )).expanduser()


def _event_action(source: str, payload: dict[str, Any]) -> str:
    event = str(payload.get("hook_event_name") or payload.get("event") or source)
    tool = str(payload.get("tool_name") or payload.get("toolName") or "")
    state = "failed" if (
        payload.get("isError") is True
        or payload.get("hook_event_name") in {"PostToolUseFailure", "StopFailure"}
        or payload.get("error")
    ) else "completed"
    return _trim(f"{source} {event} {tool} {state}", 500)


def _event_result(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if error:
        return _trim(f"failed: {_redact_text(str(error))}", 2000)
    response = payload.get("tool_response", payload.get("result"))
    if isinstance(response, Mapping):
        keys = ",".join(sorted(str(k) for k in response)[:20])
        return f"completed; response fields: {keys}" if keys else "completed"
    return "completed"


def _stable_id(source: str, payload: dict[str, Any], action: str) -> str:
    session = str(payload.get("session_id") or payload.get("sessionId") or "")
    call_id = str(payload.get("tool_use_id") or payload.get("toolCallId") or "")
    material = "|".join((source, session, call_id, action))
    if not session and not call_id:
        material += f"|{time.time_ns()}"
    return str(uuid.UUID(bytes=hashlib.sha256(material.encode()).digest()[:16], version=4))


def capture(source: str, payload: dict[str, Any]) -> dict[str, Any]:
    cwd = str(payload.get("cwd") or os.getcwd())
    project = _project_from(cwd)
    action = _event_action(source, payload)
    event_id = _stable_id(source, payload, action)
    target = socket.gethostname() if _ENV_OP.search(action) else None
    event = {
        "id": event_id,
        "project_id": project,
        "agent_id": os.environ.get("BRAIN_AGENT", source),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "target_id": target,
        "action": action,
        "result": _event_result(payload),
        "source_refs": [],
        "capture": {
            "source": source,
            "host_hash": hashlib.sha256(
                f"{platform.node()}:{platform.system()}:{platform.machine()}".encode()
            ).hexdigest()[:24],
            "session_id": str(payload.get("session_id") or payload.get("sessionId") or "")[:128],
            "tool_name": str(payload.get("tool_name") or payload.get("toolName") or "")[:128],
            "input": _sanitize(payload.get("tool_input", payload.get("input", {}))),
        },
    }
    outbox = Outbox(_outbox_path())
    try:
        try:
            outbox.enqueue("execution", event, id=event_id, version=1)
            state = "enqueued"
        except DuplicateJobError:
            state = "duplicate"
        return {"status": state, "id": event_id, "project": project}
    finally:
        outbox.close()


def _token() -> str:
    token = os.environ.get("BRAIN_TOKEN", "").strip()
    if token:
        return token
    token_file = os.environ.get("BRAIN_TOKEN_FILE", "").strip()
    if token_file:
        return Path(token_file).expanduser().read_text(encoding="utf-8").strip()
    raise RuntimeError("BRAIN_TOKEN or BRAIN_TOKEN_FILE is required")


def _url() -> str:
    return os.environ.get("BRAIN_URL", "http://127.0.0.1:8083").rstrip("/")


def _event_wire_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = {key: payload.get(key) for key in (
        "id", "project_id", "agent_id", "occurred_at", "target_id",
        "action", "result", "source_refs",
    )}
    result["client_digest"] = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode()).hexdigest()
    return result


def upload(job: Job) -> TransportResult:
    payload = job.payload
    project = str(payload.get("project_id") or "general")
    client_digest = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode()).hexdigest()
    body = json.dumps(_event_wire_payload(payload), ensure_ascii=False).encode()
    request = urllib.request.Request(
        f"{_url()}/api/v2/brain/events",
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + _token(),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Brain-Project": project,
            "User-Agent": "brain-multi-agent-adapter/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        state = "conflict" if exc.code in {401, 403, 409, 422} else "retry"
        return TransportResult(state=state, error=f"http-{exc.code}: {_redact_text(detail)}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return TransportResult(state="dropped_response_unknown", error=type(exc).__name__)
    ack = result.get("version")
    if result.get("id") != payload.get("id") or type(ack) is not int:
        return TransportResult(state="conflict", error="invalid-exact-ack", response=result)
    receipt = dict(result)
    receipt["client_digest"] = client_digest
    return TransportResult(
        state="ok",
        acknowledged_version=ack,
        response=receipt,
    )


def lookup_exact(kind: str, identity: str, version: int) -> dict[str, Any] | None:
    if kind != "execution":
        return None
    outbox = Outbox(_outbox_path())
    try:
        job = outbox.get(identity)
        project = str(job.payload.get("project_id") or "general") if job else "general"
    finally:
        outbox.close()
    request = urllib.request.Request(
        f"{_url()}/api/v2/brain/events/{identity}/ack?version={version}",
        headers={
            "Authorization": "Bearer " + _token(),
            "Accept": "application/json",
            "X-Brain-Project": project,
            "User-Agent": "brain-multi-agent-adapter/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return None


def reconcile(limit: int = 25) -> dict[str, int]:
    outbox = Outbox(_outbox_path())
    counts = {"completed": 0, "pending": 0, "unknown": 0}
    try:
        rows = outbox._conn.execute(
            "SELECT id FROM jobs WHERE state='unknown' ORDER BY updated_at LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
        for row in rows:
            state = outbox.reconcile_unknown(row["id"], lookup_exact)
            counts[state] = counts.get(state, 0) + 1
        return counts
    finally:
        outbox.close()


def drain(limit: int) -> dict[str, Any]:
    outbox = Outbox(_outbox_path())
    try:
        counts = outbox.run_once(
            upload,
            owner=f"adapter-{os.getpid()}",
            lease_seconds=30,
            limit=max(1, min(limit, 100)),
        )
        result: dict[str, Any] = dict(counts)
        result["stats"] = outbox.stats()
        return result
    finally:
        outbox.close()


def flush(limit: int = 25) -> dict[str, Any]:
    """Serialize reconciliation and upload to avoid SessionEnd lock races."""
    import fcntl

    lock_path = _outbox_path().with_suffix(".flush.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        reconciled = reconcile(limit)
        drained = drain(limit)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {"reconcile": reconciled, "drain": drained}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    hook = sub.add_parser("hook")
    hook.add_argument("--source", required=True)
    hook.add_argument("--drain", action="store_true")
    drain_cmd = sub.add_parser("drain")
    drain_cmd.add_argument("--limit", type=int, default=25)
    reconcile_cmd = sub.add_parser("reconcile")
    reconcile_cmd.add_argument("--limit", type=int, default=25)
    flush_cmd = sub.add_parser("flush")
    flush_cmd.add_argument("--limit", type=int, default=25)
    sub.add_parser("stats")
    args = parser.parse_args()
    if args.command == "hook":
        result = capture(args.source, _read_stdin_json())
        if args.drain:
            result["drain"] = drain(5)
    elif args.command == "drain":
        result = drain(args.limit)
    elif args.command == "reconcile":
        result = reconcile(args.limit)
    elif args.command == "flush":
        result = flush(args.limit)
    else:
        outbox = Outbox(_outbox_path())
        try:
            result = outbox.stats()
        finally:
            outbox.close()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
