"""Portable Brain loop API and installable skill package routes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

from hermes.lane import assign_lane, lane_text
from hermes.proposals import ProposalWriter
from hermes.repository import HermesRepository
from hermes.feedback_attribution import feedback_metrics, validate_provenance, validate_verification

VALID_TASK_RESULTS = {"success", "failure", "partial", "unknown"}
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
        return repo.brain_protocol_health_report()

    @app.get("/api/v1/brain/metrics")
    def brain_protocol_metrics() -> dict[str, object]:
        # This is an owner-wide report; scoped agent tokens do not grant access.
        with repo._connect() as connection:
            return feedback_metrics(connection)

    @app.get('/api/v1/brain/environments')
    def brain_environment_inventory():
        from hermes.environment_scope import inventory
        with repo._connect() as connection:
            return inventory(connection)

    @app.get('/environments', response_class=HTMLResponse)
    def brain_environment_page(q: str = Query(default="", max_length=200),
                               view: str = Query(default="scope", pattern="^(scope|origin)$")):
        from hermes.environment_scope import page
        from hermes.review_notes import ReviewNotes
        notes = ReviewNotes(repo)
        report = brain_environment_inventory()
        # Join by literal identity: inventory group membership does not assert equivalence.
        proposals = {p["proposal_id"]: p for p in notes.attach("proposal", repo.list_proposals_ordered())}
        knowledge = {n["id"]: n for n in notes.attach("knowledge", [vars(n) for n in repo.list_knowledge_nodes(limit=10000)])}
        for group in report["applicability_groups"] + report["groups"]:
            group["proposals"] = [{**item, "editorial_review": proposals.get(item["proposal_id"], {}).get("editorial_review")} for item in group.get("proposals", [])]
            group["knowledge"] = [{**item, "editorial_review": knowledge.get(item["id"], {}).get("editorial_review")} for item in group.get("knowledge", [])]
        return page(report, query=q, view=view)

    @app.post('/api/v1/brain/environments/assign')
    async def brain_environment_assign(body: dict[str, Any]):
        from hermes.environment_scope import context, assign
        kind=body.get('entity_type')
        entity_id=body.get('entity_id')
        if kind not in ('proposal','knowledge') or not isinstance(entity_id,str):
            raise HTTPException(status_code=400,detail='entity_type and entity_id are required')
        try:
            environment=context(body.get('environment'))
            if kind=='proposal': repo.get_proposal(entity_id)
            elif repo.get_knowledge_node(entity_id) is None: raise KeyError(entity_id)
        except ValueError as error:
            raise HTTPException(status_code=400,detail=str(error)) from error
        except KeyError:
            raise HTTPException(status_code=404,detail='record not found') from None
        with repo._connect() as connection:
            assign(connection,kind,entity_id,environment)
            if kind=='proposal':
                linked=connection.execute('SELECT knowledge_id FROM proposal_knowledge_links WHERE proposal_id=?',(entity_id,)).fetchall()
                for row in linked:assign(connection,'knowledge',row[0],environment)
            else:
                linked=connection.execute('SELECT proposal_id FROM proposal_knowledge_links WHERE knowledge_id=?',(entity_id,)).fetchall()
                for row in linked:assign(connection,'proposal',row[0],environment)
        from hermes.exporter import ExportCompiler
        compiler=ExportCompiler(repo=repo,sync_root=sync_root)
        compiler.build_global_export()
        compiler.build_claude_md_export()
        compiler.build_knowledge_export()
        compiler.build_lane_exports()
        compiler.export_brain_context()
        from hermes.runtime import sync_proposal_to_brain_context
        sync_proposal_to_brain_context({},'',repo=repo)
        for project in repo.list_exportable_project_keys():
            compiler.build_project_export(project)
        return {'schema':1,'entity_type':kind,'entity_id':entity_id,'environment':environment}

    @app.post('/api/v1/brain/environment-export')
    async def brain_environment_export(body: dict[str, Any]):
        from hermes.environment_scope import context, get_scope, scope_matches
        try:
            current=context(body.get('environment'))
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        nodes=repo.list_knowledge_nodes(limit=5000)
        with repo._connect() as connection:
            nodes=[n for n in nodes if n.stage in ('canonized','verified','refined') and
                   get_scope(connection,'knowledge',n.id)['server_id'] and
                   scope_matches(get_scope(connection,'knowledge',n.id),current)]
        markdown='# Brain context: '+current['server_id']+' '+current['user_root']+'\n\n'
        markdown+='Historical experience; check current applicability before applying.\n\n'
        markdown+='\n\n'.join('## '+n.summary+'\n\n'+n.content for n in nodes)
        return {'schema':1,'environment':current,'node_ids':[n.id for n in nodes],'markdown':markdown}

    @app.post("/api/v1/brain/retrieve")
    async def brain_protocol_retrieve(body: dict[str, Any]) -> dict[str, object]:
        query = _text(body.get("query"), field="query", maximum=1000, required=True)
        agent = _text(body.get("agent", "portable-agent"), field="agent", maximum=120) or "portable-agent"
        host = _text(body.get("host_hash", "unknown"), field="host_hash", maximum=128) or "unknown"
        session_id = _text(body.get("session_id", ""), field="session_id", maximum=200)
        try:
            from hermes.environment_scope import context
            environment = context(body.get('environment'))
            traffic_kind, task_id = validate_provenance(
                body.get("traffic_kind", "unknown"), body.get("task_id", ""), session_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
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
            traffic_kind=traffic_kind,
            task_id=task_id,
            environment=environment,
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
                "environment": item.get('environment', {}),
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

        task_success = body.get("task_success", "unknown")
        if not isinstance(task_success, str) or task_success not in VALID_TASK_RESULTS:
            raise HTTPException(status_code=400, detail=f"task_success must be one of {sorted(VALID_TASK_RESULTS)}")
        user_validated = body.get("user_validated")
        if user_validated is not None and not isinstance(user_validated, bool):
            raise HTTPException(status_code=400, detail="user_validated must be a boolean or null")
        try:
            _, _, verification_note = validate_verification(
                task_success, user_validated, body.get("verification_note", ""),
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        pair = repo.record_outcome_pair(
            retrieval_id, node_id, status, used=status != "not_used", notes=note,
            task_success=task_success, user_validated=user_validated,
            verification_note=verification_note,
        )
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
    async def brain_protocol_propose(body: dict[str, Any]) -> JSONResponse:
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
        for index, entry in enumerate(evidence):
            if not isinstance(entry, dict):
                raise HTTPException(status_code=422, detail=f"evidence[{index}] must be an object")
            if not str(entry.get("source_type", "")).strip() or not str(entry.get("source_uri", "")).strip():
                raise HTTPException(
                    status_code=422,
                    detail=f"evidence[{index}] requires source_type and source_uri",
                )
        evidence_json = json.dumps(evidence, ensure_ascii=False)
        if len(evidence_json) > 8000:
            raise HTTPException(status_code=400, detail="evidence exceeds 8000 characters")

        writer = ProposalWriter(sync_root / "inbox" / "proposals")
        from hermes.environment_scope import context
        try:
            environment = context(body.get('environment'))
            origin_environment = context(body.get('origin_environment'))
        except ValueError as error:
            raise HTTPException(status_code=400,detail=str(error)) from error
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
            environment=environment,
            origin_environment=origin_environment,
        )
        return JSONResponse(status_code=202, content={
            "schema": 1,
            "status": "queued",
            "proposal_id": path.stem,
            "message": "Proposal queued for validation, deduplication, and integration.",
        })

    @app.get("/api/v1/brain/proposals/{proposal_id}")
    def brain_protocol_proposal_status(proposal_id: str) -> dict[str, object]:
        queued = sync_root / "inbox" / "proposals" / f"{proposal_id}.md"
        if queued.is_file():
            return {"schema": 1, "proposal_id": proposal_id, "status": "queued"}
        try:
            proposal = repo.get_proposal(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="proposal not found") from exc
        link = repo.get_proposal_knowledge_link(proposal_id)
        if link is not None:
            return {
                "schema": 1,
                "proposal_id": proposal_id,
                "status": "linked",
                "proposal_state": proposal["state"],
                "knowledge_id": link["knowledge_id"],
            }
        state = str(proposal["state"])
        status = {
            "pending": "ingested_pending",
            "approved_db_only": "approved",
            "approved_for_export": "approved",
            "rejected": "rejected",
            "superseded": "duplicate",
        }.get(state, state)
        return {
            "schema": 1,
            "proposal_id": proposal_id,
            "status": status,
            "proposal_state": state,
        }

    @app.get("/skills/brain-loop/{asset_path:path}", response_class=FileResponse)
    def brain_loop_skill_asset(asset_path: str) -> FileResponse:
        requested = (package_root / asset_path).resolve()
        if requested != package_root and package_root not in requested.parents:
            raise HTTPException(status_code=403, detail="access denied")
        if not requested.is_file():
            raise HTTPException(status_code=404, detail="skill asset not found")
        return FileResponse(requested, media_type="text/markdown" if requested.suffix == ".md" else "text/x-python")
