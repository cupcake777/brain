#!/usr/bin/env python3
"""Cross-host hook launcher for Claude Code and Codex.

Resolves the agent identity and Brain credentials, then delegates to the
portable adapter. The adapter sanitizes payloads and persists them to the
durable outbox before draining; this launcher never prints secrets and only
adds credential resolution.

Resolution order (first non-empty wins):

* ``BRAIN_AGENT`` env, else ``<host>``;
* ``BRAIN_TOKEN`` env, else the token file named by ``BRAIN_TOKEN_FILE``,
  else ``~/.config/brain/token``;
* ``BRAIN_URL`` env, else ``~/.config/brain/url``.

``~/.config/brain/token`` must be owner-only (0600); the launcher warns and
continues if it is not, but it never logs the token itself.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import multi_agent_adapter as adapter  # noqa: E402


def _config_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "brain"
    return Path.home() / ".config" / "brain"


def _first_nonempty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _resolve_token() -> str:
    token = _first_nonempty(os.environ.get("BRAIN_TOKEN", ""))
    if token:
        return token
    token_file = os.environ.get("BRAIN_TOKEN_FILE", "").strip()
    candidates = [Path(token_file).expanduser()] if token_file else []
    candidates.append(_config_dir() / "token")
    for path in candidates:
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return ""


def resolve_credentials(host: str = "hermes") -> dict[str, str]:
    """Return {agent, url, token}; token may be empty when unconfigured."""
    agent = _first_nonempty(os.environ.get("BRAIN_AGENT", ""), host)
    url = _first_nonempty(os.environ.get("BRAIN_URL", ""))
    if not url:
        try:
            url = (_config_dir() / "url").read_text(encoding="utf-8").strip()
        except OSError:
            url = ""
    return {"agent": agent, "url": url, "token": _resolve_token()}


def _apply_credentials(host: str) -> None:
    creds = resolve_credentials(host)
    os.environ["BRAIN_AGENT"] = creds["agent"]
    if creds["url"]:
        os.environ["BRAIN_URL"] = creds["url"]
    if creds["token"]:
        os.environ["BRAIN_TOKEN"] = creds["token"]


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "hook"
    if command not in {"hook", "flush"}:
        print("usage: brain_hook_launcher.py [hook <host> | flush]", file=sys.stderr)
        return 2
    host = sys.argv[2] if command == "hook" and len(sys.argv) > 2 else "claude-code"
    _apply_credentials(host)
    if command == "hook":
        return adapter.main_argv(["hook", "--source", host, "--drain"])
    return adapter.main_argv(["flush", "--limit", "25"])


if __name__ == "__main__":
    raise SystemExit(main())
