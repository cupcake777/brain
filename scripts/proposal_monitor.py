#!/usr/bin/env python3
"""Monitor agent proposal activity and alert if agents go silent.

Checks the Brain proposals DB for recent activity from each known agent.
If an agent hasn't produced any proposals in N days, sends a Telegram alert.
"""

import sqlite3
import json
import urllib.request
import os
import sys
from datetime import datetime, timedelta

DB_PATH = os.environ.get("BRAIN_DB", os.path.join(os.path.dirname(__file__), "..", "hermes.sqlite3"))
SILENCE_DAYS = int(os.environ.get("SILENCE_DAYS", "2"))

# Agents we expect to be active (source_agent: display_name)
# Note: Codex on Windows/codex submits as source_agent="codex", NOT "windows"
KNOWN_AGENTS = {
    "codex": "Codex (OpenAI)",
    "claude": "Claude Code",
    "hermes": "Hermes",
}

def send_telegram(text: str):
    """Send alert via Hermes webhook."""
    webhook_url = os.environ.get("HERMES_WEBHOOK")
    if not webhook_url:
        # Try sending via local hermes API
        try:
            data = json.dumps({"message": text}).encode()
            req = urllib.request.Request(
                "http://localhost:8080/api/notify",
                data=data,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {os.environ.get('HERMES_AUTH', '')}"},
            )
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception:
            pass
        print(text)
        return False
    try:
        data = json.dumps({"text": text}).encode()
        req = urllib.request.Request(webhook_url, data=data,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Failed to send via webhook: {e}")
        print(text)
        return False


def check_proposals():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    cutoff = (datetime.utcnow() - timedelta(days=SILENCE_DAYS)).isoformat()

    # Get latest proposal per agent
    cur.execute("""
        SELECT source_agent, MAX(created_at) as last_proposal, COUNT(*) as total
        FROM proposals
        GROUP BY source_agent
    """)
    agent_stats = {}
    for row in cur.fetchall():
        agent_stats[row["source_agent"]] = {
            "last": row["last_proposal"],
            "total": row["total"],
        }

    db.close()

    alerts = []

    from datetime import timezone

    # Check known agents
    for agent, display in KNOWN_AGENTS.items():
        stats = agent_stats.get(agent)
        if not stats:
            alerts.append(f"⚠️ {display}: 从未提交过proposal")
        elif stats["last"] < cutoff:
            last_dt = datetime.fromisoformat(stats["last"])
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            days_silent = (datetime.now(timezone.utc) - last_dt).days
            alerts.append(f"⚠️ {display}: 已{days_silent}天未学习/提交proposal（最后: {stats['last'][:10]}）")
        else:
            pass  # Active, no alert

    # Summary of active agents (within silence window)
    active_lines = []
    for agent, stats in agent_stats.items():
        display = KNOWN_AGENTS.get(agent, agent)
        if stats["last"] >= cutoff:
            active_lines.append(f"✅ {display}: 最近学习于 {stats['last'][:10]}（共{stats['total']}条）")

    # Unknown agents that are NOT test/debug entries
    TEST_PREFIXES = ("test", "hermes-test", "windows")
    for agent, stats in agent_stats.items():
        if agent not in KNOWN_AGENTS and agent not in TEST_PREFIXES and stats["last"] < cutoff:
            last_dt = datetime.fromisoformat(stats["last"])
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            days_silent = (datetime.now(timezone.utc) - last_dt).days
            alerts.append(f"⚠️ Unknown agent '{agent}': 已{days_silent}天未提交proposal")

    if not alerts:
        msg = f"🧠 Brain学习监控报告\n\n✅ 所有活跃agent在{SILENCE_DAYS}天内均有提交\n\n" + "\n".join(active_lines)
        print(msg)
        return

    msg = "🧠 Brain学习监控报告\n\n" + "\n".join(alerts)
    if active_lines:
        msg += "\n\n🟢 活跃:\n" + "\n".join(active_lines)
    msg += f"\n\n共{len(alerts)}个agent需要督促"
    send_telegram(msg)


if __name__ == "__main__":
    check_proposals()