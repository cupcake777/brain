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
* ``BRAIN_CA_BUNDLE`` env, else the CA path stored in
  ``~/.config/brain/ca-bundle``, else inherited ``SSL_CERT_FILE``.

``~/.config/brain/token`` must be owner-only (0600); the launcher warns and
continues if it is not, but it never logs the token itself.
"""
from __future__ import annotations

import os
import subprocess
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
    if token_file:
        path = Path(token_file).expanduser()
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            print(f"BRAIN_TOKEN_FILE could not be read: {path}: {exc}", file=sys.stderr)
            return ""
        if value:
            return value
        print(f"BRAIN_TOKEN_FILE is empty: {path}", file=sys.stderr)
        return ""
    path = _config_dir() / "token"
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if value:
        if os.name != "nt" and path.stat().st_mode & 0o077:
            print(f"Brain token file should be owner-only (0600): {path}", file=sys.stderr)
        return value
    return ""


def _resolve_ca_bundle() -> str:
    value = _first_nonempty(
        os.environ.get("BRAIN_CA_BUNDLE", ""),
    )
    if not value:
        try:
            value = (_config_dir() / "ca-bundle").read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
    if not value:
        value = _first_nonempty(os.environ.get("SSL_CERT_FILE", ""))
    if not value:
        return ""
    path = Path(value).expanduser()
    if not path.is_file():
        print(f"Brain CA bundle is not a file: {path}", file=sys.stderr)
        return str(path)
    return str(path)


def resolve_credentials(host: str = "hermes") -> dict[str, str]:
    """Return agent endpoint, token and CA path; values may be empty."""
    agent = _first_nonempty(os.environ.get("BRAIN_AGENT", ""), host)
    url = _first_nonempty(os.environ.get("BRAIN_URL", ""))
    if not url:
        try:
            url = (_config_dir() / "url").read_text(encoding="utf-8").strip()
        except OSError:
            url = ""
    return {
        "agent": agent,
        "url": url,
        "token": _resolve_token(),
        "ca_bundle": _resolve_ca_bundle(),
    }


def _apply_credentials(host: str) -> None:
    creds = resolve_credentials(host)
    os.environ["BRAIN_AGENT"] = creds["agent"]
    if creds["url"]:
        os.environ["BRAIN_URL"] = creds["url"]
    if creds["token"]:
        os.environ["BRAIN_TOKEN"] = creds["token"]
    if creds["ca_bundle"]:
        os.environ["BRAIN_CA_BUNDLE"] = creds["ca_bundle"]
        os.environ["SSL_CERT_FILE"] = creds["ca_bundle"]


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "hook"
    if command not in {"hook", "flush", "flush-background"}:
        print("usage: brain_hook_launcher.py [hook <host> | flush | flush-background]", file=sys.stderr)
        return 2
    host = sys.argv[2] if command == "hook" and len(sys.argv) > 2 else "claude-code"
    _apply_credentials(host)
    if command == "hook":
        return adapter.main_argv(["hook", "--source", host, "--drain"])
    if command == "flush-background":
        # Codex hard-caps SessionEnd at three seconds. The outbox is durable;
        # detach the network flush so a slow upload cannot time out the hook.
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "flush"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        return 0
    return adapter.main_argv(["flush", "--limit", "25"])


if __name__ == "__main__":
    raise SystemExit(main())
