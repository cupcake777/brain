"""Hermes Brain V2: Remote dedup via Hugging Face Space.

Offloads embedding computation to a HuggingFace Space (16GB RAM, free CPU),
since the VPS (2GB RAM) cannot run fastembed without OOM.

Usage from watch cycle or CLI:
    from hermes.remote_dedup import remote_dedup
    result = remote_dedup(db_path)
    # result.deprecated_count == 113  etc.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

HF_SPACE = os.environ.get("BRAIN_DEDUP_SPACE", "")


@dataclass
class RemoteDedupResult:
    """Result from remote embedding dedup."""
    deprecated_count: int = 0
    merge_count: int = 0       # pairs above merge threshold
    review_count: int = 0      # pairs above review threshold
    log: str = ""
    error: str | None = None


def remote_dedup(
    db_path: str | Path,
    merge_threshold: float = 0.85,
    review_threshold: float = 0.55,
    apply: bool = True,
    timeout: int = 300,
) -> RemoteDedupResult:
    """Run embedding-based dedup on the HF Space.

    1. Upload current DB to HF Space
    2. Run dedup with fastembed (16GB RAM)
    3. Optionally apply deprecation & download updated DB

    Returns RemoteDedupResult with counts.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return RemoteDedupResult(error=f"DB not found: {db_path}")

    try:
        from gradio_client import Client, handle_file
    except ImportError:
        return RemoteDedupResult(error="gradio_client not installed")

    # Pre-run count
    conn = sqlite3.connect(str(db_path))
    pre_count = conn.execute(
        "SELECT COUNT(*) FROM knowledge_nodes WHERE stage != 'deprecated'"
    ).fetchone()[0]
    conn.close()

    try:
        logger.info("remote_dedup: Connecting to HF Space %s ...", HF_SPACE)
        client = Client(HF_SPACE, token=os.environ.get("HF_TOKEN"), verbose=False)

        # Step 1: Upload DB and run embedding dedup
        logger.info("remote_dedup: Uploading DB (%d active nodes) + running embedding dedup ...", pre_count)
        log, results_md = client.predict(
            file=handle_file(str(db_path)),
            mode="Embedding (fastembed)",
            merge=merge_threshold,
            review=review_threshold,
            api_name="/on_run",
        )

        logger.info("remote_dedup: Dedup run complete. Log tail: %s",
                     log[-300:] if log else "(empty)")

        # Parse counts from log
        merge_count = 0
        review_count = 0
        if log:
            # Pattern: "Deprecated N duplicate nodes" or "merge, M review"
            merge_match = re.search(r"(\d+)\s+merge", log)
            review_match = re.search(r"(\d+)\s+review", log)
            if merge_match:
                merge_count = int(merge_match.group(1))
            if review_match:
                review_count = int(review_match.group(1))

        result = RemoteDedupResult(
            merge_count=merge_count,
            review_count=review_count,
            log=log or "",
        )

        if not apply:
            return result

        # Step 2: Apply deprecation on HF Space and download updated DB
        logger.info("remote_dedup: Applying deprecation on remote ...")
        apply_result, updated_db_path = client.predict(api_name="/on_apply")

        logger.info("remote_dedup: Apply result: %s", apply_result)

        if updated_db_path:
            # Backup and replace local DB
            backup_path = db_path.with_suffix(".sqlite3.bak")
            shutil.copy2(db_path, backup_path)

            shutil.copy2(updated_db_path, db_path)
            logger.info("remote_dedup: Updated DB downloaded, backup at %s", backup_path)

            # Verify
            conn = sqlite3.connect(str(db_path))
            post_count = conn.execute(
                "SELECT COUNT(*) FROM knowledge_nodes WHERE stage != 'deprecated'"
            ).fetchone()[0]
            conn.close()

            result.deprecated_count = max(0, pre_count - post_count)
            logger.info("remote_dedup: %d active → %d active, %d deprecated",
                        pre_count, post_count, result.deprecated_count)

            # Clean up backup
            backup_path.unlink(missing_ok=True)
        else:
            logger.warning("remote_dedup: No updated DB returned from Space")

        return result

    except Exception as e:
        logger.error("remote_dedup: Failed: %s", e)
        return RemoteDedupResult(error=str(e))


def remote_dedup_available() -> bool:
    """Check if remote dedup HF Space is reachable."""
    try:
        from gradio_client import Client
        client = Client(HF_SPACE, token=os.environ.get("HF_TOKEN"), verbose=False)
        return True
    except Exception:
        return False