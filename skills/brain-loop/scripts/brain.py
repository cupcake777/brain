#!/usr/bin/env python3
"""Zero-dependency client for the Hermes Brain shared-learning loop."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_URL = "http://127.0.0.1:8083"


def api_url() -> str:
    from urllib.parse import urlparse
    value = os.environ.get("BRAIN_URL", DEFAULT_URL).rstrip("/")
    try:
        parsed = urlparse(value)
        local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path or (parsed.scheme == "http" and not local)):
            raise ValueError
        _ = parsed.port
    except ValueError:
        raise RuntimeError("BRAIN_URL must be an HTTPS origin (HTTP is allowed only on loopback), without credentials/path/query") from None
    return value


def host_hash() -> str:
    seed = f"{platform.node()}:{platform.system()}:{platform.machine()}"
    return hashlib.sha256(seed.encode()).hexdigest()[:24]


def request(path: str, *, payload: dict[str, Any] | None = None, write: bool = False) -> dict[str, Any]:
    headers = {"Accept": "application/json", "User-Agent": "brain-loop-skill/1.0"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode()
    if write:
        token = os.environ.get("BRAIN_TOKEN", "").strip()
        if not token:
            raise RuntimeError("BRAIN_TOKEN is required for protected source retrieval or outcome/proposal writes")
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{api_url()}{path}", data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        raise RuntimeError(f"Brain HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Brain unavailable: {exc.reason}") from exc


def command_health(_: argparse.Namespace) -> dict[str, Any]:
    return request("/api/v1/brain/health")


def command_retrieve(args: argparse.Namespace) -> dict[str, Any]:
    return request("/api/v1/brain/retrieve", payload={
        "query": args.query,
        "limit": args.limit,
        "category": args.category,
        "domain": args.domain,
        "agent": os.environ.get("BRAIN_AGENT", "brain-loop-skill"),
        "host_hash": host_hash(),
        "session_id": os.environ.get("BRAIN_SESSION_ID", ""),
    })


def command_source_retrieve(args: argparse.Namespace) -> dict[str, Any]:
    return request("/api/v1/brain/sources/retrieve", write=True, payload={
        "query": args.query, "source": args.source,
        "dataset": args.dataset, "limit": args.limit,
    })


def command_outcome(args: argparse.Namespace) -> dict[str, Any]:
    return request("/api/v1/brain/outcome", write=True, payload={
        "retrieval_id": args.retrieval_id,
        "node_id": args.node_id,
        "status": args.status,
        "note": args.note,
        "task_success": args.task_success,
        "user_validated": True if args.user_validated else None,
    })


def command_propose(args: argparse.Namespace) -> dict[str, Any]:
    payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("proposal file must contain a JSON object")
    payload.setdefault("agent", os.environ.get("BRAIN_AGENT", "brain-loop-skill"))
    payload.setdefault("host_hash", host_hash())
    return request("/api/v1/brain/propose", write=True, payload=payload)


def command_finalize(args: argparse.Namespace) -> dict[str, Any]:
    """Finalize a session: tell the server the session is done so it can flush
    any deferred per-session aggregations (e.g. outcome rollups, no-experience
    backfill) and emit the session summary.

    Body is exactly `agent`, `host_hash`, `session_id` — no other fields, per
    the v1 finalize contract. Requires Brain authentication on protected deployments.
    """
    session_id = (args.session_id or os.environ.get("BRAIN_SESSION_ID", "")).strip()
    if not session_id:
        raise RuntimeError("session_id is required (pass --session-id or set BRAIN_SESSION_ID)")
    return request("/api/v1/brain/finalize", write=True, payload={
        "agent": os.environ.get("BRAIN_AGENT", "brain-loop-skill"),
        "host_hash": host_hash(),
        "session_id": session_id,
    })


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Hermes Brain shared-learning client")
    sub = root.add_subparsers(dest="command", required=True)
    health = sub.add_parser("health")
    health.set_defaults(handler=command_health)

    retrieve = sub.add_parser("retrieve")
    retrieve.add_argument("query")
    retrieve.add_argument("--limit", type=int, default=5)
    retrieve.add_argument("--category", default="")
    retrieve.add_argument("--domain", default="")
    retrieve.set_defaults(handler=command_retrieve)

    source = sub.add_parser("source-retrieve")
    source.add_argument("--query", required=True)
    source.add_argument("--source", choices=["dify"], default="dify")
    source.add_argument("--dataset", default="literature")
    source.add_argument("--limit", type=int, choices=range(1, 11), default=5)
    source.set_defaults(handler=command_source_retrieve)

    outcome = sub.add_parser("outcome")
    outcome.add_argument("retrieval_id")
    outcome.add_argument("node_id")
    outcome.add_argument("status", choices=["applied", "partially_helped", "failed", "contradicted", "not_used"])
    outcome.add_argument("--note", default="")
    outcome.add_argument("--task-success", choices=["success", "failure", "partial", "unknown"], default="unknown")
    outcome.add_argument("--user-validated", action="store_true")
    outcome.set_defaults(handler=command_outcome)

    propose = sub.add_parser("propose")
    propose.add_argument("file")
    propose.set_defaults(handler=command_propose)

    finalize = sub.add_parser("finalize")
    finalize.add_argument("--session-id", default="",
                          help="Session identifier to finalize; falls back to $BRAIN_SESSION_ID")
    finalize.set_defaults(handler=command_finalize)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        result = args.handler(args)
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
