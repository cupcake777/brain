#!/usr/bin/env python3
"""Brain Proposal MCP Server — direct DB access for proposal review/approval.

Requires read/write access to the configured sync-root database.
Ensure the configured command runs as a user that can access that database.

Hermes config:
    mcp_servers:
      brain-proposals:
        command: "python"
        args: ["-m", "hermes.mcp_server", "--sync-root", "~/hermes-sync"]
        timeout: 30
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from hermes.repository import HermesRepository

logger = logging.getLogger("brain-proposal-mcp")

# ── tool definitions ──────────────────────────────────────────────────────

TOOLS = [
    Tool(
        name="list_proposals",
        description="List proposals, optionally filtered by state. Returns id, category, risk, summary, state, created_at.",
        inputSchema={
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "Filter: pending, approved_db_only, approved_for_export, rejected, superseded, or 'all'",
                    "default": "pending",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 20, max 100)",
                    "default": 20,
                },
            },
        },
    ),
    Tool(
        name="get_proposal",
        description="Get full details of a single proposal by its UUID.",
        inputSchema={
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "description": "Proposal UUID"},
            },
            "required": ["proposal_id"],
        },
    ),
    Tool(
        name="approve_db_only",
        description="Approve proposal for DB-only storage (no knowledge export).",
        inputSchema={
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "description": "Proposal UUID"},
            },
            "required": ["proposal_id"],
        },
    ),
    Tool(
        name="approve_for_export",
        description="Approve proposal AND export to knowledge base.",
        inputSchema={
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "description": "Proposal UUID"},
            },
            "required": ["proposal_id"],
        },
    ),
    Tool(
        name="reject_proposal",
        description="Reject a proposal.",
        inputSchema={
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "description": "Proposal UUID"},
            },
            "required": ["proposal_id"],
        },
    ),
    Tool(
        name="proposal_stats",
        description="Get proposal counts by state.",
        inputSchema={"type": "object", "properties": {}},
    ),
]

# ── helpers ───────────────────────────────────────────────────────────────

DISPLAY_KEYS = [
    "proposal_id", "state", "category", "risk_level", "summary",
    "source_agent", "created_at", "project_key", "scope",
]
FULL_KEYS = DISPLAY_KEYS + [
    "observation", "why_it_matters", "suggested_memory",
    "evidence", "semantic_hash", "reviewer_priority", "weight",
]


def _pick(d: dict, keys: list[str]) -> dict:
    return {k: d.get(k) for k in keys if k in d}


# ── server ────────────────────────────────────────────────────────────────

def create_server(db_path: str) -> Server:
    repo = HermesRepository(db_path)
    server = Server("brain-proposals")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            if name == "list_proposals":
                state = arguments.get("state", "pending")
                limit = min(int(arguments.get("limit", 20)), 100)
                if state == "all":
                    proposals = repo.list_proposals_ordered()
                else:
                    proposals = repo.list_proposals_by_state(state)
                items = [_pick(p, DISPLAY_KEYS) for p in proposals[:limit]]
                return [TextContent(type="text", text=json.dumps(
                    {"count": len(items), "state": state, "items": items},
                    ensure_ascii=False, indent=2))]

            elif name == "get_proposal":
                pid = arguments["proposal_id"]
                try:
                    p = repo.get_proposal(pid)
                except KeyError:
                    return [TextContent(type="text",
                            text=json.dumps({"error": f"proposal {pid} not found"}))]
                return [TextContent(type="text", text=json.dumps(
                    _pick(p, FULL_KEYS), ensure_ascii=False, indent=2))]

            elif name == "approve_db_only":
                pid = arguments["proposal_id"]
                repo.transition_state(pid, "approved_db_only")
                return [TextContent(type="text", text=json.dumps(
                    {"proposal_id": pid, "state": "approved_db_only", "status": "ok"}))]

            elif name == "approve_for_export":
                pid = arguments["proposal_id"]
                p = repo.get_proposal(pid)
                repo.transition_state(pid, "approved_for_export")
                try:
                    from hermes.exporter import ExportCompiler
                    ex = ExportCompiler(repo=repo, sync_root=Path(db_path).parent)
                    if p.get("project_key") == "global" or p.get("scope") == "global":
                        ex.build_global_export()
                        ex.build_claude_md_export()
                    else:
                        ex.build_project_export(str(p.get("project_key", "")))
                except Exception as exc:
                    logger.warning("export failed for %s: %s", pid, exc)
                return [TextContent(type="text", text=json.dumps(
                    {"proposal_id": pid, "state": "approved_for_export", "status": "ok"}))]

            elif name == "reject_proposal":
                pid = arguments["proposal_id"]
                repo.transition_state(pid, "rejected")
                return [TextContent(type="text", text=json.dumps(
                    {"proposal_id": pid, "state": "rejected", "status": "ok"}))]

            elif name == "proposal_stats":
                states = {}
                for s in ("pending", "approved_db_only", "approved_for_export", "rejected", "superseded"):
                    states[s] = len(repo.list_proposals_by_state(s))
                return [TextContent(type="text", text=json.dumps(
                    {"total": sum(states.values()), "by_state": states},
                    ensure_ascii=False, indent=2))]

            else:
                return [TextContent(type="text",
                        text=json.dumps({"error": f"unknown tool: {name}"}))]

        except Exception as exc:
            logger.exception("tool %s failed", name)
            return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]

    return server


def main():
    parser = argparse.ArgumentParser(description="Brain Proposal MCP Server")
    parser.add_argument("--sync-root", default=str(Path.home() / "hermes-sync"))
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()

    sync_root = Path(args.sync_root)
    db_path = args.db_path or str(sync_root / "hermes.sqlite3")

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    server = create_server(db_path)

    import asyncio
    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
