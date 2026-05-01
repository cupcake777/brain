#!/usr/bin/env python3
"""
Generate cross-session context summary for Hermes prefill.

Reads recent sessions from other platforms and generates a JSON prefill
file injected into every new CLI session, providing continuity awareness.

Output: ~/.hermes/prefill.json (loaded by all new sessions)
Cron: */5 * * * * python3 /root/ops/brain/hermes/cross_session_context.py
"""

import json
import sqlite3
import time
import os
from pathlib import Path
from datetime import datetime

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
STATE_DB = HERMES_HOME / "state.db"
PREFILL_FILE = HERMES_HOME / "prefill.json"
MAX_SESSIONS = 5
MAX_AGE_HOURS = 48
MAX_SUMMARY_CHARS = 1000

# Sources to include in cross-session context (exclude current platform)
INTERESTING_SOURCES = ("telegram", "weixin")


def get_recent_sessions(current_source: str = "cli") -> list[dict]:
    """Get recent interesting sessions from other platforms."""
    if not STATE_DB.exists():
        return []

    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row

    cutoff = time.time() - (MAX_AGE_HOURS * 3600)
    placeholders = ",".join("?" * len(INTERESTING_SOURCES))

    # Get sessions with enough messages to be meaningful
    cur = conn.cursor()
    cur.execute(f"""
        SELECT id, source, started_at, title, message_count
        FROM sessions
        WHERE source IN ({placeholders})
          AND started_at > ?
          AND message_count > 5
        ORDER BY started_at DESC
        LIMIT ?
    """, (*INTERESTING_SOURCES, cutoff, MAX_SESSIONS + 5))

    sessions = []
    for row in cur.fetchall():
        s = dict(row)
        # Get first user message as topic hint
        cur2 = conn.cursor()
        cur2.execute(
            "SELECT content FROM messages WHERE session_id=? AND role='user' "
            "AND length(content) > 5 ORDER BY timestamp ASC LIMIT 1",
            (s["id"],)
        )
        first_user = cur2.fetchone()
        s["first_user_msg"] = first_user["content"][:120] if first_user else ""

        # Get last assistant message as outcome hint
        cur2.execute(
            "SELECT content FROM messages WHERE session_id=? AND role='assistant' "
            "AND length(content) > 10 ORDER BY timestamp DESC LIMIT 1",
            (s["id"],)
        )
        last_asst = cur2.fetchone()
        s["last_asst_msg"] = last_asst["content"][:120] if last_asst else ""

        sessions.append(s)

    conn.close()
    return sessions[:MAX_SESSIONS]


def format_age(started_at: float) -> str:
    """Format time elapsed since session start."""
    hours = int((time.time() - started_at) / 3600)
    if hours < 1:
        return f"{int((time.time() - started_at) / 60)}分钟前"
    if hours < 24:
        return f"{hours}小时前"
    return f"{hours // 24}天前"


def build_context_text(sessions: list[dict]) -> str:
    """Build a concise context summary from recent sessions."""
    if not sessions:
        return ""

    lines = ["[跨平台上下文] 你最近在其他平台的对话："]
    total_chars = len(lines[0])

    for s in sessions:
        source_name = {"telegram": "TG", "weixin": "微信"}.get(s["source"], s["source"])
        title = s.get("title") or "(无标题)"
        msg_count = s.get("message_count", 0)
        age = format_age(s["started_at"])

        line = f"【{source_name} {age}】{title} ({msg_count}条)"
        if s.get("last_asst_msg"):
            # Take first line of last assistant message as outcome
            outcome = s["last_asst_msg"].split("\n")[0][:80]
            line += f" → {outcome}"

        if total_chars + len(line) > MAX_SUMMARY_CHARS:
            break
        lines.append(line)
        total_chars += len(line)

    lines.append("用session_search可查详情")
    return "\n".join(lines)


def main():
    sessions = get_recent_sessions()

    if not sessions:
        # Clean up stale prefill
        if PREFILL_FILE.exists():
            PREFILL_FILE.unlink()
        return

    context_text = build_context_text(sessions)
    if not context_text:
        if PREFILL_FILE.exists():
            PREFILL_FILE.unlink()
        return

    # Format as prefill messages
    prefill_messages = [
        {
            "role": "user",
            "content": "[系统] 以下是你在Telegram/微信等平台的近期活动摘要，请据此保持跨平台上下文连贯。"
        },
        {
            "role": "assistant",
            "content": context_text
        }
    ]

    # Atomic write
    tmp_file = PREFILL_FILE.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(prefill_messages, f, ensure_ascii=False, indent=2)
    tmp_file.rename(PREFILL_FILE)


if __name__ == "__main__":
    main()