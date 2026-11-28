#!/usr/bin/env python3
"""Zero-dependency client for the Hermes Brain shared-learning loop."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_URL = "http://127.0.0.1:8083"
PROPOSAL_TEXT_FIELDS = (
    "summary", "observation", "why_it_matters", "suggested_memory",
    "project", "scope", "domain",
)
PROPOSAL_CATEGORIES = {"rule", "fact", "preference", "workflow_hint", "correction", "resource"}
PROPOSAL_RISKS = {"low", "medium", "high", "critical"}


def config_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "brain"
    return Path.home() / ".config" / "brain"


def _read_config(name: str) -> str:
    try:
        return (config_dir() / name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _first_nonempty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def resolve_token() -> str:
    token_file = os.environ.get("BRAIN_TOKEN_FILE", "").strip()
    if token_file:
        try:
            token = Path(token_file).expanduser().read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"BRAIN_TOKEN_FILE could not be read: {token_file}") from exc
        if token:
            return token
        raise RuntimeError(f"BRAIN_TOKEN_FILE is empty: {token_file}")
    return _first_nonempty(os.environ.get("BRAIN_TOKEN", ""), _read_config("token"))


def resolve_ca_bundle() -> Path | None:
    value = _first_nonempty(
        os.environ.get("BRAIN_CA_BUNDLE", ""),
        _read_config("ca-bundle"),
        os.environ.get("SSL_CERT_FILE", ""),
    )
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_file():
        raise RuntimeError(f"configured Brain CA bundle is not a file: {path}")
    return path


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return number



def api_url() -> str:
    from urllib.parse import urlparse
    value = _first_nonempty(os.environ.get("BRAIN_URL", ""), _read_config("url"), DEFAULT_URL).rstrip("/")
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


def request(
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    write: bool = False,
    optional_auth: bool = False,
) -> dict[str, Any]:
    from urllib.parse import urlparse

    origin = api_url()
    use_tls = urlparse(origin).scheme.casefold() == "https"
    headers = {"Accept": "application/json", "User-Agent": "brain-loop-skill/1.0"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode()
    if write:
        token = resolve_token()
        if not token:
            raise RuntimeError("BRAIN_TOKEN is required for protected source retrieval or outcome/proposal writes")
        headers["Authorization"] = f"Bearer {token}"
    elif optional_auth:
        token = resolve_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{origin}{path}", data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        kwargs: dict[str, Any] = {"timeout": 20}
        if use_tls:
            ca_bundle = resolve_ca_bundle()
            if ca_bundle is not None:
                kwargs["context"] = ssl.create_default_context(cafile=str(ca_bundle))
        with urllib.request.urlopen(req, **kwargs) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        raise RuntimeError(f"Brain HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Brain unavailable: {exc.reason}") from exc


def command_health(_: argparse.Namespace) -> dict[str, Any]:
    return request("/api/v1/brain/health", optional_auth=True)


def resolve_session_id(explicit: str = "") -> str:
    return _first_nonempty(
        explicit,
        os.environ.get("BRAIN_SESSION_ID", ""),
        os.environ.get("CODEX_THREAD_ID", ""),
    )


def environment_context(args=None) -> dict[str, str]:
    return {
        "server_id": getattr(args, 'server_id', '') or os.environ.get('BRAIN_SERVER_ID', '') or _read_config('server-id') or platform.node(),
        "user_root": getattr(args, 'user_root', '') or os.environ.get('BRAIN_USER_ROOT', '') or _read_config('user-root') or str(Path.home()),
        "project_root": getattr(args, 'project_root', '') or os.environ.get('BRAIN_PROJECT_ROOT', '') or str(Path.cwd()),
    }


def command_retrieve(args: argparse.Namespace) -> dict[str, Any]:
    session_id = resolve_session_id(args.session_id)
    if not session_id:
        raise RuntimeError("session_id is required; pass --session-id or configure the actual agent session ID")
    return request("/api/v1/brain/retrieve", optional_auth=True, payload={
        "query": args.query,
        "limit": args.limit,
        "category": args.category,
        "domain": args.domain,
        "agent": os.environ.get("BRAIN_AGENT", "brain-loop-skill"),
        "host_hash": host_hash(),
        "session_id": session_id,
        "traffic_kind": args.traffic_kind,
        "task_id": args.task_id or os.environ.get("BRAIN_TASK_ID", ""),
        "environment": environment_context(args),
    })


def command_context_export(args: argparse.Namespace) -> dict[str, Any]:
    result=request('/api/v1/brain/environment-export',optional_auth=True,
                   payload={'environment':environment_context(args)})
    if args.output:
        destination=Path(args.output).expanduser()
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_name(destination.name+'.tmp')
        temporary.write_text(result['markdown'],encoding='utf-8')
        temporary.replace(destination)
        return {'status':'written','path':str(destination),'node_count':len(result['node_ids'])}
    return result


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
        "verification_note": args.verification_note,
    })


def command_propose(args: argparse.Namespace) -> dict[str, Any]:
    payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("proposal file must contain a JSON object")
    required = {*PROPOSAL_TEXT_FIELDS, "category", "risk_level", "evidence"}
    missing = sorted(required.difference(payload))
    if missing:
        raise RuntimeError(f"proposal missing required fields: {', '.join(missing)}")
    for field in PROPOSAL_TEXT_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"proposal {field} must be a non-empty string")
        if value.strip().startswith("<") and value.strip().endswith(">"):
            raise RuntimeError(f"replace placeholder in proposal {field}")
    if payload.get("category") not in PROPOSAL_CATEGORIES:
        raise RuntimeError(f"proposal category must be one of {sorted(PROPOSAL_CATEGORIES)}")
    if payload.get("risk_level") not in PROPOSAL_RISKS:
        raise RuntimeError(f"proposal risk_level must be one of {sorted(PROPOSAL_RISKS)}")
    normalized_core = [
        " ".join(str(payload[field]).casefold().split())
        for field in ("observation", "why_it_matters", "suggested_memory")
    ]
    if len(set(normalized_core)) != len(normalized_core):
        raise RuntimeError(
            "proposal observation, why_it_matters, and suggested_memory must be semantically distinct"
        )
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise RuntimeError("proposal evidence must be a non-empty list")
    for index, entry in enumerate(evidence):
        if not isinstance(entry, dict):
            raise RuntimeError(f"evidence[{index}] must be an object")
        if not str(entry.get("source_type", "")).strip() or not str(entry.get("source_uri", "")).strip():
            raise RuntimeError(f"evidence[{index}] requires source_type and source_uri")
        for field in ("source_type", "source_uri", "quoted_excerpt"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(f"evidence[{index}] requires {field}")
            if value.strip().startswith("<") and value.strip().endswith(">"):
                raise RuntimeError(f"replace placeholder in evidence[{index}].{field}")
    payload.setdefault("agent", os.environ.get("BRAIN_AGENT", "brain-loop-skill"))
    payload.setdefault("host_hash", host_hash())
    payload.setdefault("origin_environment", environment_context())
    result = request("/api/v1/brain/propose", write=True, payload=payload)
    if not args.wait:
        return result
    proposal_id = str(result.get("proposal_id", "")).strip()
    if not proposal_id:
        raise RuntimeError("proposal response did not include proposal_id")
    deadline = time.monotonic() + args.timeout
    # ``--wait`` means wait for durable server receipt, not governance approval.
    # ingested_pending is therefore terminal: the proposal is in SQLite and can
    # be reviewed later, while approved/linked represent later lifecycle states.
    terminal_statuses = {"ingested_pending", "approved", "linked", "duplicate", "rejected"}
    while time.monotonic() < deadline:
        current = request(f"/api/v1/brain/proposals/{proposal_id}", write=True)
        if current.get("status") in terminal_statuses:
            if current.get("status") == "rejected":
                raise RuntimeError(f"proposal rejected: {current}")
            return current
        time.sleep(args.poll_interval)
    raise RuntimeError(f"timed out waiting for proposal {proposal_id} durable status")


def command_proposal_status(args: argparse.Namespace) -> dict[str, Any]:
    return request(f"/api/v1/brain/proposals/{args.proposal_id}", write=True)


def command_finalize(args: argparse.Namespace) -> dict[str, Any]:
    """Finalize a session: tell the server the session is done so it can flush
    any deferred per-session aggregations (e.g. outcome rollups, no-experience
    backfill) and emit the session summary.

    Body is exactly `agent`, `host_hash`, `session_id` — no other fields, per
    the v1 finalize contract. Requires Brain authentication on protected deployments.
    """
    session_id = resolve_session_id(args.session_id)
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

    metrics = sub.add_parser("metrics")
    metrics.set_defaults(handler=lambda _: request("/api/v1/brain/metrics", optional_auth=True))

    scoped=sub.add_parser('context-export')
    scoped.add_argument('--server-id',default='')
    scoped.add_argument('--user-root',default='')
    scoped.add_argument('--project-root',default='')
    scoped.add_argument('--output',default='')
    scoped.set_defaults(handler=command_context_export)

    retrieve = sub.add_parser("retrieve")
    retrieve.add_argument("query")
    retrieve.add_argument("--limit", type=int, default=5)
    retrieve.add_argument("--category", default="")
    retrieve.add_argument("--domain", default="")
    retrieve.add_argument("--traffic-kind", choices=["task", "audit", "probe", "evaluation", "unknown"],
                          default=os.environ.get("BRAIN_TRAFFIC_KIND", "task"))
    retrieve.add_argument("--task-id", default="")
    retrieve.add_argument('--server-id', default='')
    retrieve.add_argument('--user-root', default='')
    retrieve.add_argument('--project-root', default='')
    retrieve.add_argument("--session-id", default="",
                          help="Session identifier; defaults to BRAIN_SESSION_ID or CODEX_THREAD_ID")
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
    outcome.add_argument("--verification-note", default="", help="Actual acceptance check and its observed result")
    outcome.set_defaults(handler=command_outcome)

    propose = sub.add_parser("propose")
    propose.add_argument("file")
    propose.add_argument("--wait", action="store_true")
    propose.add_argument("--timeout", type=positive_float, default=90.0)
    propose.add_argument("--poll-interval", type=positive_float, default=1.0)
    propose.set_defaults(handler=command_propose)

    proposal_status = sub.add_parser("proposal-status")
    proposal_status.add_argument("proposal_id")
    proposal_status.set_defaults(handler=command_proposal_status)

    finalize = sub.add_parser("finalize")
    finalize.add_argument("--session-id", default="",
                          help="Session identifier to finalize; defaults to BRAIN_SESSION_ID or CODEX_THREAD_ID")
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
