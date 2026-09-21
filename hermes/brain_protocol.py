"""Portable Brain loop API and installable skill package routes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from hermes.lane import assign_lane, lane_text
from hermes.proposals import ProposalWriter
from hermes.repository import HermesRepository

VALID_OUTCOMES = {"applied", "partially_helped", "failed", "contradicted", "not_used"}
VALID_CATEGORIES = {"rule", "fact", "preference", "workflow_hint", "correction", "resource"}
VALID_RISKS = {"low", "medium", "high", "critical"}


def _text(value: Any, *, field: str, maximum: int, required: bool = False) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise HTTPException(status_code=400, detail=f"{field} is required")
    if len(result) > maximum:
        raise HTTPException(status_code=400, detail=f"{field} exceeds {maximum} characters")
    return result


def register_brain_protocol_routes(
    app: FastAPI,
    *,
    repo: HermesRepository,
    sync_root: Path,
    skill_root: Path | None = None,
) -> None:
    """Register the stable HTTP surface consumed by the portable brain-loop skill."""

    package_root = (
        skill_root
        or Path(os.environ.get("BRAIN_LOOP_SKILL_ROOT", str(Path(__file__).resolve().parents[1] / "skills" / "brain-loop")))
    ).resolve()

    @app.get("/api/v1/brain/health")
    def brain_protocol_health() -> dict[str, object]:
        stats = repo.knowledge_stats_full()
        return {
            "status": "ok",
            "schema": 1,
            "nodes": stats["total"],
            "retrievals": stats["total_retrievals"],
            "outcomes": stats["total_outcomes"],
        }

    @app.post("/api/v1/brain/retrieve")
    async def brain_protocol_retrieve(body: dict[str, Any]) -> dict[str, object]:
        query = _text(body.get("query"), field="query", maximum=1000, required=True)
        agent = _text(body.get("agent", "portable-agent"), field="agent", maximum=120) or "portable-agent"
        host = _text(body.get("host_hash", "unknown"), field="host_hash", maximum=128) or "unknown"
        session_id = _text(body.get("session_id", ""), field="session_id", maximum=200)
        category = _text(body.get("category", ""), field="category", maximum=80) or None
        domain = _text(body.get("domain", ""), field="domain", maximum=80) or None
        try:
            limit = max(1, min(int(body.get("limit", 5)), 20))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="limit must be an integer")

        event = repo.record_retrieval_for_query(
            query,
            agent=agent,
            host=host,
            limit=limit,
            category=category,
            domain=domain,
            session_id=session_id,
        )
        raw_results = event.get("results", [])
        if not isinstance(raw_results, list):
            raw_results = []
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
            for item in raw_results
            if isinstance(item, dict)
        ]
        return {
            "schema": 1,
            "retrieval_id": event["event_id"],
            "query": query,
            "results": results,
            "outcome_required": bool(results),
        }

    @app.post("/api/v1/brain/finalize")
    async def brain_protocol_finalize(body: dict[str, Any]) -> dict[str, object]:
        agent = _text(body.get("agent"), field="agent", maximum=120, required=True)
        host = _text(body.get("host_hash"), field="host_hash", maximum=128, required=True)
        session = _text(body.get("session_id"), field="session_id", maximum=200, required=True)
        return {"schema": 1, **repo.finalize_session(agent, host, session)}

    @app.post("/api/v1/brain/outcome")
    async def brain_protocol_outcome(body: dict[str, Any]) -> dict[str, object]:
        retrieval_id = _text(body.get("retrieval_id"), field="retrieval_id", maximum=128, required=True)
        node_id = _text(body.get("node_id"), field="node_id", maximum=128, required=True)
        status = _text(body.get("status"), field="status", maximum=40, required=True)
        note = _text(body.get("note", ""), field="note", maximum=1000)
        if status not in VALID_OUTCOMES:
            raise HTTPException(status_code=400, detail=f"status must be one of {sorted(VALID_OUTCOMES)}")

        event = repo.get_retrieval_event(retrieval_id)
        if event is None:
            raise HTTPException(status_code=404, detail="retrieval not found")
        try:
            candidate_ids = set(json.loads(event.node_ids or "[]"))
        except (TypeError, json.JSONDecodeError):
            candidate_ids = set()
        if node_id not in candidate_ids:
            raise HTTPException(status_code=400, detail="node_id was not returned by this retrieval")

        helpfulness = {
            "applied": "helpful",
            "partially_helped": "helpful",
            "failed": "neutral",
            "contradicted": "harmful",
            "not_used": "neutral",
        }[status]
        pair = repo.record_outcome_pair(retrieval_id, node_id, status, used=status != "not_used", notes=note)
        if pair["status"] == "conflict_unresolved":
            raise HTTPException(status_code=409, detail="outcome status conflict")
        if pair["status"] not in {"recorded", "duplicate_same_status"}:
            raise HTTPException(status_code=400, detail=str(pair["status"]))
        recorded = int(pair["recorded"])
        return {
            "schema": 1,
            "recorded": recorded,
            "retrieval_id": retrieval_id,
            "node_id": node_id,
            "status": status,
            "proposal_recommended": status in {"failed", "contradicted"},
        }

    @app.post("/api/v1/brain/propose")
    async def brain_protocol_propose(body: dict[str, Any]) -> dict[str, object]:
        summary = _text(body.get("summary"), field="summary", maximum=300, required=True)
        observation = _text(body.get("observation"), field="observation", maximum=4000, required=True)
        why = _text(body.get("why_it_matters"), field="why_it_matters", maximum=2000, required=True)
        memory = _text(body.get("suggested_memory"), field="suggested_memory", maximum=4000, required=True)
        project = _text(body.get("project", "global"), field="project", maximum=100) or "global"
        category = _text(body.get("category", "workflow_hint"), field="category", maximum=40)
        risk = _text(body.get("risk_level", "low"), field="risk_level", maximum=40)
        scope = _text(body.get("scope", "global"), field="scope", maximum=100) or "global"
        source_agent = _text(body.get("agent", "portable-agent"), field="agent", maximum=120) or "portable-agent"
        source_host = _text(body.get("host_hash", "unknown"), field="host_hash", maximum=128) or "unknown"
        domain = _text(body.get("domain", ""), field="domain", maximum=80)
        if category not in VALID_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"category must be one of {sorted(VALID_CATEGORIES)}")
        if risk not in VALID_RISKS:
            raise HTTPException(status_code=400, detail=f"risk_level must be one of {sorted(VALID_RISKS)}")

        evidence = body.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            raise HTTPException(status_code=400, detail="evidence must be a non-empty list")
        evidence_json = json.dumps(evidence, ensure_ascii=False)
        if len(evidence_json) > 8000:
            raise HTTPException(status_code=400, detail="evidence exceeds 8000 characters")

        writer = ProposalWriter(sync_root / "inbox" / "proposals")
        path = writer.write(
            source_agent=source_agent,
            source_host=source_host,
            project_key=project,
            category=category,
            risk_level=risk,
            summary=summary,
            observation=observation,
            why_it_matters=why,
            suggested_memory=memory,
            scope=scope,
            evidence=evidence_json,
            domain=assign_lane(hinted=domain, project_key=project, text=lane_text(summary, observation, memory)),
        )
        return {
            "schema": 1,
            "status": "submitted",
            "proposal_id": path.stem,
            "message": "Proposal queued for validation, deduplication, and integration.",
        }

    @app.get("/skills/brain-loop/{asset_path:path}", response_class=FileResponse)
    def brain_loop_skill_asset(asset_path: str) -> FileResponse:
        requested = (package_root / asset_path).resolve()
        if requested != package_root and package_root not in requested.parents:
            raise HTTPException(status_code=403, detail="access denied")
        if not requested.is_file():
            raise HTTPException(status_code=404, detail="skill asset not found")
        return FileResponse(requested, media_type="text/markdown" if requested.suffix == ".md" else "text/x-python")
