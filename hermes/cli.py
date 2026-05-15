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

    retrospect_parser = subparsers.add_parser("retrospect", help="Run knowledge node maintenance: auto-promote stages, recompute confidence, find merge candidates")
    retrospect_parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")

    reweight_parser = subparsers.add_parser("reweight", help="Recalculate proposal weights from category/risk/retrieval")
    reweight_parser.add_argument("--dry-run", action="store_true", help="Show what weights would change without writing")

    dedup_parser = subparsers.add_parser("dedup", help="Find and mark semantic duplicates in proposals")
    dedup_parser.add_argument("--dry-run", action="store_true", help="Show duplicates without modifying DB")

    dedup_v2_parser = subparsers.add_parser("dedup-v2", help="Find and deprecate duplicate knowledge nodes using embeddings")
    dedup_v2_parser.add_argument("--dry-run", action="store_true", help="Show duplicates without modifying DB")
    dedup_v2_parser.add_argument("--threshold", type=float, default=0.85, help="Embedding similarity threshold for auto-merge (default: 0.85)")
    dedup_v2_parser.add_argument("--review-threshold", type=float, default=0.70, help="Threshold for review candidates (default: 0.70)")

    remote_dedup_parser = subparsers.add_parser("remote-dedup", help="Run embedding dedup on HF Space (offloaded, for VPS OOM avoidance)")
    remote_dedup_parser.add_argument("--merge-threshold", type=float, default=0.85, help="Merge similarity threshold (default: 0.85)")
    remote_dedup_parser.add_argument("--review-threshold", type=float, default=0.55, help="Review similarity threshold (default: 0.55)")
    remote_dedup_parser.add_argument("--no-apply", action="store_true", help="Run dedup but don't apply deprecation / download updated DB")

    migrate_parser = subparsers.add_parser("migrate-v2", help="Migrate proposals to V2 knowledge_nodes table")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without writing")

    integrate_parser = subparsers.add_parser("integrate", help="Integrate a new knowledge entry into the V2 knowledge tree")
    integrate_parser.add_argument("--content", required=True, help="Knowledge content to integrate")
    integrate_parser.add_argument("--source", default="cli", help="Source of the knowledge (e.g., conversation:session_id, user_direct)")
    integrate_parser.add_argument("--category", default="fact", help="Category: rule/workflow/preference/fact")
    integrate_parser.add_argument("--domain", default="general", help="Domain: devops/network/apa/general/...")
    integrate_parser.add_argument("--parent", default=None, help="Parent node ID (for refine/debug operations)")

    export_v2_parser = subparsers.add_parser("export-v2", help="Export V2 knowledge nodes to KNOWLEDGE.md")
    export_v2_parser.add_argument("--dry-run", action="store_true", help="Show what would be exported without writing")

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
    if args.command == "retrospect":
        from hermes.integrate import retrospect as _retrospect
        if args.dry_run:
            result = _retrospect(runtime.repo, dry_run=True)
        else:
            result = _retrospect(runtime.repo, dry_run=False)
        print(f"Retrospect results: {result}", flush=True)
        if not args.dry_run:
            runtime.rebuild_exports()
            print("Exports rebuilt.", flush=True)
        return 0
    if args.command == "reweight":
        if args.dry_run:
            import sqlite3
            conn = sqlite3.connect(str(config.db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT proposal_id, summary, category, risk_level, weight, retrieval_count_30d FROM proposals")
            from hermes.weight import compute_weight
            for row in cur.fetchall():
                new_w = compute_weight(category=row["category"], risk_level=row["risk_level"], retrieval_count_30d=row["retrieval_count_30d"] or 0)
                old_w = row["weight"] or 0
                marker = " ← CHANGE" if abs(new_w - old_w) > 0.01 else ""
                print(f"{row['proposal_id'][:8]}… [{row['category']}/{row['risk_level']}] w={old_w}→{new_w} ret={row['retrieval_count_30d']} {row['summary'][:60]}{marker}")
            conn.close()
            return 0
        count = runtime.repo.recalculate_all_weights()
        print(f"Recalculated weights for {count} proposals")
        return 0
    if args.command == "dedup":
        import sqlite3
        from collections import defaultdict
        conn = sqlite3.connect(str(config.db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT proposal_id, summary, semantic_hash, state, semantic_duplicate_of FROM proposals ORDER BY inserted_at")
        rows = cur.fetchall()
        # Group by semantic_hash
        by_hash = defaultdict(list)
        for row in rows:
            h = row["semantic_hash"]
            if h:
                by_hash[h].append(dict(row))
        dupes_found = 0
        for h, group in by_hash.items():
            if len(group) <= 1:
                continue
            dupes_found += 1
            primary = group[0]
            for dup in group[1:]:
                if dup["semantic_duplicate_of"] is None and dup["state"] not in ("rejected", "superseded"):
                    if args.dry_run:
                        print(f"WOULD mark {dup['proposal_id'][:8]}… as duplicate of {primary['proposal_id'][:8]}… (hash={h[:12]}…)")
                    else:
                        cur.execute(
                            "UPDATE proposals SET semantic_duplicate_of = ?, state = 'rejected' WHERE proposal_id = ?",
                            (primary["proposal_id"], dup["proposal_id"]),
                        )
                    dupes_found += 1
        if not args.dry_run:
            conn.commit()
            print(f"Marked {dupes_found} duplicates")
        else:
            print(f"Found {dupes_found} duplicate groups (dry run, no changes)")
        conn.close()
        return 0

    if args.command == "dedup-v2":
        """Find and deprecate duplicate knowledge nodes using embedding similarity.

        Strategy:
        1. Batch embed all active node summaries using bge-small-en-v1.5
        2. Compute pairwise cosine similarity
        3. Auto-deprecate pairs above --threshold (default 0.85)
        4. Report pairs above --review-threshold (default 0.70) for manual review
        """
        import os as _os
        _os.environ.setdefault("ORT_LOGGING_LEVEL", "3")
        import numpy as np
        from datetime import datetime, timezone
        from hermes.repository import HermesRepository as _HRepo
        from hermes.embedding import embed_texts
        from hermes.integrate import _text_similarity

        v2_repo = _HRepo(config.db_path)
        nodes = v2_repo.list_knowledge_nodes(limit=10000)
        active = [n for n in nodes if n.stage != "deprecated"]
        merge_threshold = args.threshold
        review_threshold = args.review_threshold

        if not active:
            print("No active nodes found.")
            return 0

        print(f"Scanning {len(active)} active nodes for duplicates...")
        summaries = [n.summary for n in active]

# Embed all summaries
        print("Loading embedding model...")
        try:
            embs = embed_texts(summaries)
        except Exception as e:
            print(f"Embedding failed ({e}), falling back to text similarity only.")
            embs = None

        if embs is not None:
            # Embedding-based: compute full pairwise similarity matrix
            emb_matrix = np.array(embs)
            norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1
            emb_matrix = emb_matrix / norms

            merge_pairs = []
            review_pairs = []

            for i in range(len(active)):
                for j in range(i + 1, len(active)):
                    sim = float(emb_matrix[i] @ emb_matrix[j])
                    if sim > merge_threshold:
                        merge_pairs.append((sim, i, j))
                    elif sim > review_threshold:
                        review_pairs.append((sim, i, j))
        else:
            # Text-only fallback: compute pairwise text similarity
            merge_threshold = 0.55  # Lower thresholds for text-only mode
            review_threshold = 0.35
            print(f"Using text-only mode with lower thresholds: merge={merge_threshold}, review={review_threshold}")
            merge_pairs = []
            review_pairs = []

            for i in range(len(active)):
                for j in range(i + 1, len(active)):
                    sim = max(
                        _text_similarity(active[i].summary, active[j].summary),
                        _text_similarity(active[i].content, active[j].content),
                    )
                    if sim > merge_threshold:
                        merge_pairs.append((sim, i, j))
                    elif sim > review_threshold:
                        review_pairs.append((sim, i, j))

        merge_pairs.sort(key=lambda x: x[0], reverse=True)
        review_pairs.sort(key=lambda x: x[0], reverse=True)

        # Auto-deprecate merge pairs (keep the one with higher confidence)
        deprecated_count = 0
        seen = set()  # Track already-deprecated IDs to avoid double-counting
        now = datetime.now(timezone.utc).isoformat()

        print(f"\n=== MERGE candidates (emb sim > {merge_threshold}): {len(merge_pairs)} ===")
        for sim, i, j in merge_pairs:
            a, b = active[i], active[j]
            # Keep the node with higher confidence
            keep, drop = (a, b) if a.confidence >= b.confidence else (b, a)
            print(f"  sim={sim:.3f}  KEEP [{keep.stage}] c={keep.confidence:.2f} {keep.summary[:70]}")
            print(f"  {'':14s}DROP [{drop.stage}] c={drop.confidence:.2f} {drop.summary[:70]}")
            if drop.id not in seen:
                seen.add(drop.id)
                if not args.dry_run:
                    v2_repo.update_knowledge_node(drop.id, stage="deprecated", deprecated_at=now)
                deprecated_count += 1

        print(f"\n=== REVIEW candidates (emb sim {review_threshold}-{merge_threshold}): {len(review_pairs)} ===")
        for sim, i, j in review_pairs[:15]:
            a, b = active[i], active[j]
            print(f"  sim={sim:.3f}")
            print(f"    [{a.stage}] c={a.confidence:.2f} {a.summary[:70]}")
            print(f"    [{b.stage}] c={b.confidence:.2f} {b.summary[:70]}")

        if args.dry_run:
            print(f"\nDry run: would deprecate {deprecated_count} nodes. No changes made.")
        else:
            print(f"\nDeprecated {deprecated_count} duplicate nodes.")
            remaining = [n for n in v2_repo.list_knowledge_nodes(limit=10000) if n.stage != "deprecated"]
            print(f"Remaining active nodes: {len(remaining)}")
        return 0

    if args.command == "remote-dedup":
        """Run embedding-based dedup on HuggingFace Space."""
        from hermes.remote_dedup import remote_dedup

        result = remote_dedup(
            db_path=str(config.db_path),
            merge_threshold=args.merge_threshold,
            review_threshold=args.review_threshold,
            apply=not args.no_apply,
            timeout=300,
        )
        if result.error:
            print(f"Remote dedup failed: {result.error}", flush=True)
            return 1
        print(f"Remote dedup complete.", flush=True)
        print(f"  Merge pairs: {result.merge_count}", flush=True)
        print(f"  Review pairs: {result.review_count}", flush=True)
        print(f"  Deprecated: {result.deprecated_count} nodes", flush=True)
        if result.log:
            print(f"  Log (tail):\n{result.log[-500:]}", flush=True)
        return 0

    if args.command == "migrate-v2":
        from hermes.repository import HermesRepository
        from hermes.integrate import compute_confidence
        v2_repo = HermesRepository(config.db_path)
        if args.dry_run:
            import sqlite3
            conn = sqlite3.connect(str(config.db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT proposal_id, state, category, risk_level, weight, summary FROM proposals ORDER BY inserted_at")
            rows = cur.fetchall()
            stage_map = {"approved_for_export": "canonized", "approved_db_only": "canonized", "pending": "draft", "superseded": "deprecated"}
            for row in rows:
                state = str(row["state"])
                if state == "rejected":
                    print(f"  SKIP (rejected): {row['summary'][:60]}")
                    continue
                new_stage = stage_map.get(state, "draft")
                conf = round(float(row["weight"] or 1.0) / 5.0, 2)
                print(f"  {row['proposal_id'][:8]}… [{state}→{new_stage}] conf={conf} cat={row['category']} | {row['summary'][:60]}")
            conn.close()
            return 0
        result = v2_repo.migrate_proposals_to_knowledge_nodes()
        print(f"Migrated {result['migrated']} proposals, skipped {result['skipped']}")
        counts = v2_repo.count_knowledge_nodes_by_stage()
        print(f"Stage distribution: {counts}")
        return 0

    if args.command == "integrate":
        # Integrate a new knowledge entry from CLI
        import json as _json
        from hermes.repository import HermesRepository as _HRepo
        from hermes.integrate import integrate as _integrate
        v2_repo = _HRepo(config.db_path)
        content = args.content
        source = args.source
        category = args.category
        domain = args.domain
        parent_id = args.parent
        result = _integrate(
            content=content,
            source=source,
            category=category,
            domain=domain,
            parent_id=parent_id,
            repo=v2_repo,
        )
        print(f"Action: {result.action}")
        print(f"Node ID: {result.node_id}")
        print(f"Stage: {result.stage}")
        print(f"Confidence: {result.confidence:.3f}")
        if result.merged_from:
            print(f"Merged from: {result.merged_from}")
        if result.superseded:
            print(f"Superseded: {result.superseded}")
        return 0
    if args.command == "export-v2":
        from hermes.repository import HermesRepository as _HRepo
        from hermes.exporter import ExportCompiler as _Exporter
        v2_repo = _HRepo(config.db_path)
        exporter = _Exporter(repo=v2_repo, sync_root=config.sync_root)
        path = exporter.build_knowledge_export()
        print(f"Exported to: {path}")
        if args.dry_run:
            print(f"(dry-run mode — file was still written, check content)")
        print(f"Size: {path.stat().st_size} bytes")
        return 0
    if args.command == "serve":
        if args.reload:
            # Dev mode: use uvicorn reload with factory pattern
            os.environ["HERMES_SYNC_ROOT"] = str(runtime.config.sync_root)
            uvicorn.run(
                "hermes._app_factory:create_app",
                host=args.host, port=args.port,
                reload=True,
                reload_dirs=[os.path.join(os.path.dirname(__file__))],
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
