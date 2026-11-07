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
        name="retrieve_knowledge",
        description="Retrieve relevant Brain knowledge for a concrete task and return literal retrieval/node IDs for later outcome reporting.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Concrete task terms (required)"},
                "agent": {"type": "string", "default": "xiaohe"},
                "host_id": {"type": "string", "default": "control-plane"},
                "session_id": {"type": "string", "default": ""},
                "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                "category": {"type": "string"},
                "domain": {"type": "string"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="report_knowledge_outcome",
        description="Report whether one candidate returned by a Brain retrieval was applied, partially helpful, failed, contradicted, or not used.",
        inputSchema={
            "type": "object",
            "properties": {
                "retrieval_id": {"type": "string"},
                "node_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["applied", "partially_helped", "failed", "contradicted", "not_used"],
                },
                "note": {"type": "string", "default": ""},
            },
            "required": ["retrieval_id", "node_id", "status"],
        },
    ),
    Tool(
        name="finalize_knowledge_session",
        description="Audit one exact Brain session and report any retrieval candidates that still lack terminal outcomes.",
        inputSchema={
            "type": "object",
            "properties": {
                "agent": {"type": "string"},
                "host_id": {"type": "string"},
                "session_id": {"type": "string"},
            },
            "required": ["agent", "host_id", "session_id"],
        },
    ),
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


async def _execute_tool(repo: HermesRepository, name: str, arguments: dict) -> list[TextContent]:
    """Execute one MCP tool against ``repo`` (kept separate for real-code tests)."""
    if name == "retrieve_knowledge":
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        limit = max(1, min(int(arguments.get("limit", 5)), 20))
        event = repo.record_retrieval_for_query(
            query,
            agent=str(arguments.get("agent") or "xiaohe")[:120],
            host=str(arguments.get("host_id") or "control-plane")[:128],
            limit=limit,
            category=str(arguments.get("category") or "").strip() or None,
            domain=str(arguments.get("domain") or "").strip() or None,
            session_id=str(arguments.get("session_id") or "")[:200],
        )
        results = [
            {
                "node_id": item["id"],
                "summary": item["summary"],
                "content": item["content"],
                "category": item["category"],
                "domain": item["domain"],
                "stage": item["stage"],
                "confidence": item["confidence"],
                "score": item.get("score"),
            }
            for item in event.get("results", [])
            if isinstance(item, dict)
        ]
        payload = {
            "schema": 1,
            "retrieval_id": event["event_id"],
            "query": query,
            "results": results,
            "outcome_required": bool(results),
        }
        return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]

    if name == "report_knowledge_outcome":
        retrieval_id = str(arguments.get("retrieval_id") or "").strip()
        node_id = str(arguments.get("node_id") or "").strip()
        status = str(arguments.get("status") or "").strip()
        valid_statuses = {"applied", "partially_helped", "failed", "contradicted", "not_used"}
        if not retrieval_id or not node_id:
            raise ValueError("retrieval_id and node_id are required")
        if status not in valid_statuses:
            raise ValueError(f"status must be one of {sorted(valid_statuses)}")
        event = repo.get_retrieval_event(retrieval_id)
        if event is None:
            raise ValueError("retrieval not found")
        try:
            candidate_ids = set(json.loads(event.node_ids or "[]"))
        except (TypeError, json.JSONDecodeError):
            candidate_ids = set()
        if node_id not in candidate_ids:
            raise ValueError("node_id was not returned by this retrieval")
        pair = repo.record_outcome_pair(
            retrieval_id,
            node_id,
            status,
            notes=str(arguments.get("note") or "")[:1000],
            used=status != "not_used",
        )
        if pair["status"] == "conflict_unresolved":
            raise ValueError("outcome status conflict")
        if pair["status"] not in {"recorded", "duplicate_same_status"}:
            raise ValueError(str(pair["status"]))
        payload = {
            "schema": 1,
            "recorded": int(pair["recorded"]),
            "retrieval_id": retrieval_id,
            "node_id": node_id,
            "status": status,
            "proposal_recommended": status in {"failed", "contradicted"},
        }
        return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]

    if name == "finalize_knowledge_session":
        agent = str(arguments.get("agent") or "").strip()[:120]
        host_id = str(arguments.get("host_id") or "").strip()[:128]
        session_id = str(arguments.get("session_id") or "").strip()[:200]
        if not agent or not host_id or not session_id:
            raise ValueError("agent, host_id and session_id are required")
        payload = {
            "schema": 1,
            **repo.finalize_session(agent, host_id, session_id),
        }
        return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]

    if name == "list_proposals":
        state = arguments.get("state", "pending")
        limit = min(int(arguments.get("limit", 20)), 100)
        if state == "all":
            proposals = repo.list_proposals_ordered()
        else:
            proposals = repo.list_proposals_by_state(state)
        items = [_pick(p, DISPLAY_KEYS) for p in proposals[:limit]]
        payload = {"count": len(items), "state": state, "items": items}
    elif name == "get_proposal":
        pid = arguments["proposal_id"]
        try:
            payload = _pick(repo.get_proposal(pid), FULL_KEYS)
        except KeyError:
            payload = {"error": f"proposal {pid} not found"}
    elif name == "approve_db_only":
        pid = arguments["proposal_id"]
        repo.transition_state(pid, "approved_db_only")
        payload = {"proposal_id": pid, "state": "approved_db_only", "status": "ok"}
    elif name == "approve_for_export":
        pid = arguments["proposal_id"]
        proposal = repo.get_proposal(pid)
        repo.transition_state(pid, "approved_for_export")
        try:
            from hermes.exporter import ExportCompiler
            exporter = ExportCompiler(repo=repo, sync_root=Path(repo.db_path).parent)
            if proposal.get("project_key") == "global" or proposal.get("scope") == "global":
                exporter.build_global_export()
                exporter.build_claude_md_export()
            else:
                exporter.build_project_export(str(proposal.get("project_key", "")))
        except Exception as exc:
            logger.warning("export failed for %s: %s", pid, exc)
        payload = {"proposal_id": pid, "state": "approved_for_export", "status": "ok"}
    elif name == "reject_proposal":
        pid = arguments["proposal_id"]
        repo.transition_state(pid, "rejected")
        payload = {"proposal_id": pid, "state": "rejected", "status": "ok"}
    elif name == "proposal_stats":
        states = {
            state: len(repo.list_proposals_by_state(state))
            for state in ("pending", "approved_db_only", "approved_for_export", "rejected", "superseded")
        }
        payload = {"total": sum(states.values()), "by_state": states}
    else:
        payload = {"error": f"unknown tool: {name}"}
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


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
            return await _execute_tool(repo, name, arguments)

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
