from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from hermes.app import create_app
from hermes.auth import TLSConfig
from hermes.config import HermesConfig
from hermes.repository import HermesRepository
from hermes.runtime import HermesRuntime


def build_config(*, sync_root: str | Path) -> HermesConfig:
    """Build HermesConfig from sync_root plus optional env vars."""
    root = Path(sync_root)
    return HermesConfig(
        sync_root=root,
        db_path=root / "hermes.sqlite3",
        auth_token=os.environ.get("HERMES_AUTH_TOKEN") or None,
        auth_username=os.environ.get("HERMES_USERNAME") or None,
        auth_password=os.environ.get("HERMES_PASSWORD") or None,
        csrf_secret=os.environ.get("HERMES_CSRF_SECRET") or None,
        tls_cert=os.environ.get("HERMES_TLS_CERT") or None,
        tls_key=os.environ.get("HERMES_TLS_KEY") or None,
        telegram_bot_token=os.environ.get("HERMES_TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.environ.get("HERMES_TELEGRAM_CHAT_ID") or None,
    )


def build_runtime(*, sync_root: str | Path) -> HermesRuntime:
    config = build_config(sync_root=sync_root)
    repo = HermesRepository(config.db_path)
    return HermesRuntime(config=config, repo=repo)


def build_app(*, sync_root: str | Path):
    runtime = build_runtime(sync_root=sync_root)
    return create_app(
        repo=runtime.repo,
        sync_root=runtime.config.sync_root,
        config=runtime.config,
        exporter=runtime.exporter,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes")
    parser.add_argument("--sync-root", default=".", help="Syncthing-shared root directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="Run one inbox ingestion/status cycle")
    subparsers.add_parser("rebuild-exports", help="Rebuild export snapshots from approved records")
    subparsers.add_parser("watch", help="Run the polling watcher loop")
    subparsers.add_parser("evict", help="Run export eviction / budget pressure check")

    serve_parser = subparsers.add_parser("serve", help="Run the Hermes FastAPI server")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8080)
    serve_parser.add_argument("--auth-token", default=None, help="Bearer token for API auth (or set HERMES_AUTH_TOKEN)")
    serve_parser.add_argument("--csrf-secret", default=None, help="CSRF secret (or set HERMES_CSRF_SECRET)")
    serve_parser.add_argument("--tls-cert", default=None, help="Path to TLS certificate PEM (or set HERMES_TLS_CERT)")
    serve_parser.add_argument("--tls-key", default=None, help="Path to TLS private key PEM (or set HERMES_TLS_KEY)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload on file changes (dev mode)")

    args = parser.parse_args(argv)

    # Build config, merging CLI args over env vars
    config = build_config(sync_root=args.sync_root)
    if getattr(args, "auth_token", None):
        object.__setattr__(config, "auth_token", args.auth_token)
    if getattr(args, "csrf_secret", None):
        object.__setattr__(config, "csrf_secret", args.csrf_secret)
    if getattr(args, "tls_cert", None):
        object.__setattr__(config, "tls_cert", args.tls_cert)
    if getattr(args, "tls_key", None):
        object.__setattr__(config, "tls_key", args.tls_key)

    runtime = HermesRuntime(config=config)

    if args.command == "scan":
        runtime.run_scan_cycle()
        return 0
    if args.command == "rebuild-exports":
        runtime.rebuild_exports()
        return 0
    if args.command == "watch":
        runtime.watch()
        return 0
    if args.command == "evict":
        result = runtime.run_eviction_cycle()
        print(f"Evicted: {result.evicted_count}, Flagged rebuild: {result.flagged_for_rebuild_count}")
        return 0
    if args.command == "serve":
        if args.reload:
            # Dev mode: use uvicorn reload with factory pattern
            os.environ["HERMES_SYNC_ROOT"] = str(runtime.config.sync_root)
            uvicorn.run(
                "hermes._app_factory:create_app",
                host=args.host, port=args.port,
                reload=True,
                reload_dirs=["/root/ops/brain/hermes"],
                factory=True,
            )
        else:
            # Production mode: create app directly
            app = create_app(
                repo=runtime.repo,
                sync_root=runtime.config.sync_root,
                config=runtime.config,
                exporter=runtime.exporter,
            )
            tls = TLSConfig(cert_path=config.tls_cert, key_path=config.tls_key)
            if tls.enabled:
                uvicorn.run(app, host=args.host, port=args.port, ssl_certfile=tls.cert_path, ssl_keyfile=tls.key_path)
            else:
                uvicorn.run(app, host=args.host, port=args.port)
        return 0
    return 1
