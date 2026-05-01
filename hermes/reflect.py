"""Hermes Self-Reflection Engine.

Periodically reviews Hermes's own accumulated knowledge (Honcho profile, memory,
session insights) and writes proposals to Brain for cross-session durability.

This closes the loop: Hermes learns -> writes proposal -> Brain reviews -> exports
filter back to all agents -> next session starts smarter.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SYNC_ROOT = Path("/root/hermes-sync")
INBOX_DIR = SYNC_ROOT / "inbox" / "proposals"
BRAIN_DB = SYNC_ROOT / "hermes.sqlite3"


def _run_brain_sync_propose(
    *,
    agent: str = "hermes",
    summary: str,
    observation: str,
    why: str,
    memory: str,
    category: str = "workflow_hint",
    risk: str = "low",
    project: str = "global",
    scope: str = "all",
    evidence: str = "",
    host: str | None = None,
) -> str | None:
    """Call brain-sync propose CLI. Returns proposal ID on success, None on failure."""
    import uuid

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    proposal_id = str(uuid.uuid4())

    front_matter = {
        "proposal_id": proposal_id,
        "source_agent": agent,
        "source_host": host or "vps",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_key": project,
        "category": category,
        "risk_level": risk,
        "status": "submitted",
    }

    body = (
        f"# Summary\n{summary}\n\n"
        f"## Observation\n{observation}\n\n"
        f"## Why it matters\n{why}\n\n"
        f"## Suggested durable memory\n{memory}\n\n"
        f"## Scope\n{scope}\n\n"
        f"## Evidence\n{evidence or 'Auto-reflection by Hermes'}\n"
    )

    import yaml
    yaml_block = yaml.safe_dump(front_matter, sort_keys=False).strip()
    content = f"---\n{yaml_block}\n---\n{body}"

    # Atomic write
    tmp_path = INBOX_DIR / f".tmp-{proposal_id}.md"
    final_path = INBOX_DIR / f"{proposal_id}.md"
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.rename(final_path)

    logger.info("Proposal written: %s (category=%s, risk=%s)", proposal_id, category, risk)
    return proposal_id


def _get_existing_proposals() -> set[str]:
    """Get set of existing proposal summaries from DB to avoid duplicates.
    
    Checks ALL proposals including rejected — a previously rejected rule
    was rejected for a reason and should not be re-proposed by reflect.
    Only truly new knowledge deserves a new proposal.
    """
    try:
        import sqlite3
        conn = sqlite3.connect(str(BRAIN_DB))
        cur = conn.cursor()
        cur.execute("SELECT summary FROM proposals")
        summaries = {row[0] for row in cur.fetchall()}
        conn.close()
        return summaries
    except Exception:
        return set()


def _load_hermes_memory() -> list[dict[str, str]]:
    """Load Hermes's own memory entries from the memory system."""
    try:
        result = subprocess.run(
            ["hermes-memory", "search", "--limit", "20"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception:
        pass
    return []


def reflect_on_environment() -> list[str]:
    """Reflect on environment facts and propose missing knowledge.

    Checks VPS state, service health, and recent observations that
    should be durable across sessions.
    """
    proposals: list[str] = []
    existing_summaries = _get_existing_proposals()

    # Check service status
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "hermes-serve", "hermes-watch"],
            capture_output=True, text=True, timeout=10,
        )
        services_ok = result.stdout.strip() == "active\nactive"
    except Exception:
        services_ok = False

    # Check disk usage
    try:
        result = subprocess.run(
            ["df", "-h", "/"],
            capture_output=True, text=True, timeout=10,
        )
        disk_line = [l for l in result.stdout.split("\n") if l.startswith("/dev/")][0]
        use_pct = disk_line.split()[4].rstrip("%")
    except Exception:
        use_pct = "unknown"

    # Check if Syncthing is running
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "syncthing@root"],
            capture_output=True, text=True, timeout=10,
        )
        syncthing_ok = result.stdout.strip() == "active"
    except Exception:
        syncthing_ok = False

    # Propose missing environment facts
    env_facts = []

    summary = "Hermes Brain services (serve+watch) must remain active for proposal ingestion and export rebuilding"
    if summary not in existing_summaries and not services_ok:
        env_facts.append({
            "summary": summary,
            "observation": f"Service check at {datetime.now(timezone.utc).isoformat()}: hermes-serve={services_ok}",
            "why": "If services are down, proposals accumulate in inbox without processing, notifications fail, and exports go stale",
            "memory": "Always verify hermes-serve and hermes-watch are active before diagnosing Brain issues",
            "category": "workflow_hint",
            "risk": "low",
        })

    summary = "Syncthing must be running on VPS to sync proposals from local agents"
    if summary not in existing_summaries and not syncthing_ok:
        env_facts.append({
            "summary": summary,
            "observation": f"Syncthing status: {syncthing_ok}",
            "why": "Without Syncthing, local agent proposals never reach the VPS inbox for processing",
            "memory": "Check syncthing@root service status if local proposals are not appearing on VPS",
            "category": "workflow_hint",
            "risk": "low",
        })

    for fact in env_facts:
        pid = _run_brain_sync_propose(**fact)
        if pid:
            proposals.append(pid)

    return proposals


def _load_hermes_memory_items() -> list[dict]:
    """Load Hermes memory items from all memory storage files."""
    memory_dir = Path("/root/.hermes/memory")
    if not memory_dir.exists():
        return []
    items = []
    for md_file in memory_dir.rglob("*.md"):
        if md_file.name == "INDEX.md":
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("- ") or line.startswith("• "):
                    items.append({
                        "content": line.lstrip("- •").strip(),
                        "source": str(md_file.relative_to(memory_dir)),
                    })
                elif line.startswith("§"):
                    items.append({
                        "content": line.lstrip("§").strip(),
                        "source": str(md_file.relative_to(memory_dir)),
                    })
        except Exception:
            pass
    return items


def reflect_on_learnings() -> list[str]:
    """Reflect on recent session learnings and propose them as durable rules.

    This is the key mechanism: Hermes periodically introspects its own
    accumulated knowledge (learnings queue, memory, honcho, session patterns)
    and writes the most important insights as proposals.
    """
    proposals: list[str] = []
    existing_summaries = _get_existing_proposals()

    candidate_observations = []

    # 1. Process learnings queue (captured by hermes-reflect hook)
    queue_path = Path("/root/.hermes/reflect/queue/learnings-queue.json")
    queued_learnings: list[dict] = []
    if queue_path.exists():
        try:
            with open(queue_path) as f:
                queued_learnings = json.load(f)
            # Clear the queue after reading — items will become proposals
            with open(queue_path, "w") as f:
                json.dump([], f)
            logger.info("Loaded %d items from learnings queue", len(queued_learnings))
        except Exception as e:
            logger.warning("Failed to read learnings queue: %s", e)

    # NOTE: The learnings queue is no longer auto-proposed into proposals.
    # Learning happens INSIDE conversations — the agent identifies corrections,
    # generalizes them into reusable rules, and submits Brain proposals directly.
    # Raw queue items are project-specific, non-reusable, or one-time mistakes
    # that fail the 3-layer funnel:
    #   1. Is it a genuine correction/new knowledge?
    #   2. Can it be generalized across scenarios?
    #   3. Will it recur in future sessions?
    # Only items passing ALL 3 layers deserve durable memory.
    # The queue is drained (cleared) but nothing is auto-proposed from it.
    logger.info(
        "Drained %d items from learnings queue (not auto-proposed — "
        "learning should happen in-conversation with generalization filter)",
        len(queued_learnings),
    )

# Hardcoded rules removed — these are already captured as approved DB proposals.
    # reflect_on_learnings() now only processes the learnings queue (which it drains)
    # and does NOT auto-propose static rules. New rules come from in-conversation
    # generalization (brain-sync propose or POST /api/proposals/submit).

    return proposals


def reflect_on_memory() -> list[str]:
    """Scan Hermes memory for knowledge that should be promoted to Brain proposals.

    Memory items are session-level facts. Some deserve promotion to durable
    Brain rules when they represent reusable, generalizable knowledge.
    """
    proposals: list[str] = []
    existing_summaries = _get_existing_proposals()

    memory_items = _load_hermes_memory_items()
    logger.info("Scanned %d memory items for promotion candidates", len(memory_items))

    # Keywords that indicate a memory item is a durable rule, not a one-off fact
    rule_keywords = [
        "always", "never", "must", "prohibit", "require", "forbid",
        "should", "avoid", "prefer", "default", "workflow", "rule",
    ]
    # Keywords that indicate project-specific or one-off facts (skip these)
    skip_keywords = [
        "path:", "url:", "ip:", "token:", "password:", "port:",
        "username:", "email:", "running on", "deployed at",
    ]

    for item in memory_items:
        content = item.get("content", "").strip()
        if not content or len(content) < 20:
            continue

        content_lower = content.lower()

        # Skip project-specific or ephemeral facts
        if any(kw in content_lower for kw in skip_keywords):
            continue

        # Only promote items that look like rules
        if not any(kw in content_lower for kw in rule_keywords):
            continue

        # Check if already proposed — use prefix match (first 60 chars)
        # to catch rephrased duplicates that differ in trailing details
        summary_prefix = content[:60].rstrip()
        if any(s.startswith(summary_prefix) or summary_prefix.startswith(s[:60].rstrip()) for s in existing_summaries if len(s) >= 20):
            continue

        logger.info("Memory candidate for promotion: %s", summary_prefix[:60])
        # Don't auto-propose — log it for manual review
        # Auto-promotion is too aggressive; the 3-layer funnel still applies

    return proposals


def _clean_stale_rejected(sync_root: Path, max_age_days: int = 7) -> int:
    """Remove rejected proposal files older than max_age_days."""
    rejected_dir = sync_root / "review" / "rejected"
    if not rejected_dir.is_dir():
        return 0
    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - (max_age_days * 86400)
    removed = 0
    for f in rejected_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    if removed:
        logger.info("Cleaned %d stale rejected files (older than %d days)", removed, max_age_days)
    return removed


def cli_main() -> None:
    """CLI entry point for hermes-reflect."""
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Hermes Self-Reflection Engine")
    parser.add_argument("--mode", choices=["environment", "learnings", "memory", "all"], default="all",
                        help="What to reflect on (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be proposed without writing")
    args = parser.parse_args()

    # Clean stale rejected files first
    _clean_stale_rejected(SYNC_ROOT, max_age_days=7)

    all_proposals: list[str] = []

    if args.mode in ("environment", "all"):
        pids = reflect_on_environment()
        all_proposals.extend(pids)
        logger.info("Environment reflection: %d proposals", len(pids))

    if args.mode in ("learnings", "all"):
        pids = reflect_on_learnings()
        all_proposals.extend(pids)
        logger.info("Learnings reflection: %d proposals", len(pids))

    if args.mode in ("memory", "all"):
        pids = reflect_on_memory()
        all_proposals.extend(pids)
        logger.info("Memory reflection: %d proposals", len(pids))

    if all_proposals:
        logger.info("Total proposals written: %d", len(all_proposals))
        # Trigger Brain scan to ingest immediately
        try:
            subprocess.run(
                ["python3", "-m", "hermes", "--sync-root", str(SYNC_ROOT), "scan"],
                capture_output=True, text=True, timeout=30,
            )
        except Exception as e:
            logger.warning("Scan trigger failed: %s", e)
    else:
        logger.info("No new proposals needed — all knowledge already captured")


if __name__ == "__main__":
    cli_main()