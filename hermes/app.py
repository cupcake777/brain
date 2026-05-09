from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import asdict as _asdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

from fastapi import FastAPI, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from hermes.auth import CSRFMiddleware, DBFailClosedMiddleware, TokenAuthMiddleware
from hermes.config import HermesConfig
from hermes.exporter import ExportCompiler
from hermes.repository import HermesRepository
from hermes.status import StatusPublisher
from hermes.templates import (
    gallery_page,
    knowledge_detail_page,
    knowledge_tree_page as knowledge_page,
    login_page,
    review_detail_page,
    review_queue_page,
    security_page,
    settings_page,
)


def create_app(
    *,
    repo: HermesRepository,
    sync_root: str | Path,
    config: HermesConfig | None = None,
    exporter: ExportCompiler | None = None,
) -> FastAPI:
    sync_root = Path(sync_root)
    config = config or HermesConfig(sync_root=sync_root, db_path=sync_root / "hermes.sqlite3")
    exporter = exporter or ExportCompiler(repo=repo, sync_root=sync_root)
    status_publisher = StatusPublisher(repo=repo, sync_root=sync_root)
    app = FastAPI(title="Hermes MVP")

    # -- auth helpers (must be defined before middleware) ----------------------
    auth_enabled = bool(config.auth_token or config.auth_username)
    _AUTH_COOKIE = "hermes_auth"
    _session_secret: str = secrets.token_hex(16)  # random per startup for cookie signing

    def _valid_login(username: str, password: str) -> bool:
        """Check username/password against config."""
        if config.auth_username and config.auth_password:
            return username == config.auth_username and password == config.auth_password
        # Fallback: if only auth_token set, accept token as password with any username
        if config.auth_token:
            return password == config.auth_token
        return False

    def _make_cookie_value() -> str:
        """Generate a cookie value that proves successful auth."""
        payload = f"{_session_secret}:{config.auth_token or ''}:{config.auth_username or ''}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def _has_valid_cookie(request: Request) -> bool:
        """Check if the request carries a valid auth cookie."""
        if not config.auth_token and not config.auth_username:
            return True  # auth disabled
        cookie_val = request.cookies.get(_AUTH_COOKIE)
        return cookie_val == _make_cookie_value()

    def _set_auth_cookie(response: Response) -> Response:
        """Set the auth cookie on a response (login success)."""
        response.set_cookie(_AUTH_COOKIE, _make_cookie_value(), httponly=True, samesite="lax", max_age=86400 * 30)
        return response

    # -- middleware stack (outermost first) ------------------------------------
    app.add_middleware(DBFailClosedMiddleware)
    if config.csrf_secret is not None or auth_enabled:
        app.add_middleware(CSRFMiddleware, auth_token=config.auth_token, csrf_secret=config.csrf_secret)
    if auth_enabled:
        app.add_middleware(TokenAuthMiddleware, auth_token=config.auth_token, auth_enabled=auth_enabled, session_cookie_value=_make_cookie_value())

    # -- login routes ----------------------------------------------------------

    @app.get("/login", response_class=HTMLResponse, response_model=None)
    def login_get(request: Request):
        if not config.auth_token and not config.auth_username:
            return RedirectResponse("/knowledge", status_code=303)
        if _has_valid_cookie(request):
            return RedirectResponse("/knowledge", status_code=303)
        return login_page()

    @app.post("/login", response_model=None)
    def login_post(request: Request, username: str = Form(""), password: str = Form("")):
        if not config.auth_token and not config.auth_username:
            return RedirectResponse("/knowledge", status_code=303)
        if _valid_login(username, password):
            resp = RedirectResponse("/knowledge", status_code=303)
            return _set_auth_cookie(resp)
        return login_page(error="Invalid username or password")

    @app.get("/logout")
    def logout():
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(_AUTH_COOKIE)
        return resp

    # ------------------------------------------------------------------
    # JSON API endpoints (unchanged – tests depend on these)
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse, response_model=None)
    def root_redirect(request: Request):
        if auth_enabled and not _has_valid_cookie(request):
            return RedirectResponse("/login", status_code=303)
        return RedirectResponse("/knowledge", status_code=303)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    def _get_next_proposal_id(repo: HermesRepository, state: str, current_id: str) -> str:
        """Get the next proposal ID in the same state queue after the current one."""
        if state == "all":
            proposals = repo.list_proposals_ordered()
        else:
            proposals = repo.list_proposals_by_state(state)
        ids = [str(p.get("proposal_id", "")) for p in proposals]
        try:
            idx = ids.index(current_id)
            if idx + 1 < len(ids):
                return ids[idx + 1]
        except ValueError:
            pass
        return ""

    @app.get("/api/review/pending")
    def review_pending() -> dict[str, object]:
        return {"items": repo.list_proposals_by_state("pending")}

    @app.get("/api/review/{proposal_id}")
    def review_detail(proposal_id: str) -> dict[str, object]:
        try:
            return repo.get_proposal(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="proposal not found") from exc

    @app.post("/api/review/{proposal_id}/approve-db-only")
    def approve_db_only(proposal_id: str, state: str = Query(default="pending")) -> dict[str, str]:
        repo.transition_state(proposal_id, "approved_db_only")
        status_publisher.publish()
        next_id = _get_next_proposal_id(repo, state, proposal_id)
        return {"proposal_id": proposal_id, "state": "approved_db_only", "next_id": next_id}

    @app.post("/api/review/{proposal_id}/approve-for-export")
    def approve_for_export(proposal_id: str, state: str = Query(default="pending")) -> dict[str, str]:
        proposal = repo.get_proposal(proposal_id)
        repo.transition_state(proposal_id, "approved_for_export")
        if proposal["project_key"] == "global" or proposal["scope"] == "global":
            exporter.build_global_export()
            exporter.build_claude_md_export()
        else:
            exporter.build_project_export(str(proposal["project_key"]))
        status_publisher.publish()
        next_id = _get_next_proposal_id(repo, state, proposal_id)
        return {"proposal_id": proposal_id, "state": "approved_for_export", "next_id": next_id}

    @app.post("/api/review/{proposal_id}/promote-to-export")
    def promote_to_export(proposal_id: str, state: str = Query(default="pending")) -> dict[str, str]:
        """Promote an approved_db_only proposal to approved_for_export."""
        proposal = repo.get_proposal(proposal_id)
        if proposal["state"] != "approved_db_only":
            raise HTTPException(status_code=409, detail=f"Cannot promote from state '{proposal['state']}', only from 'approved_db_only'")
        repo.transition_state(proposal_id, "approved_for_export")
        if proposal["project_key"] == "global" or proposal["scope"] == "global":
            exporter.build_global_export()
            exporter.build_claude_md_export()
        else:
            exporter.build_project_export(str(proposal["project_key"]))
        status_publisher.publish()
        next_id = _get_next_proposal_id(repo, state, proposal_id)
        return {"proposal_id": proposal_id, "state": "approved_for_export", "next_id": next_id}

    @app.post("/api/review/{proposal_id}/reject")
    def reject(proposal_id: str, state: str = Query(default="pending")) -> dict[str, str]:
        repo.transition_state(proposal_id, "rejected")
        status_publisher.publish()
        next_id = _get_next_proposal_id(repo, state, proposal_id)
        return {"proposal_id": proposal_id, "state": "rejected", "next_id": next_id}

    # ------------------------------------------------------------------
    # Proposal submission endpoint (for remote agents)
    # ------------------------------------------------------------------

    @app.post("/api/proposals/submit")
    async def submit_proposal(request: Request) -> dict[str, str]:
        """Accept a proposal .md file from a remote agent.

        Body can be either:
        - JSON: {"content": "<full .md content>", "filename": "optional-name.md"}
        - Plain text: the raw .md content (Content-Type: text/markdown or text/plain)

        The file is written to the proposals inbox and will be ingested
        on the next watch cycle.
        """
        import json as _json
        import uuid

        content_type = request.headers.get("content-type", "")
        content = ""
        filename = ""

        if "application/json" in content_type:
            body = await request.json()
            content = body.get("content", "")
            filename = body.get("filename", "")
        else:
            raw = await request.body()
            content = raw.decode("utf-8")

        if not content.strip():
            raise HTTPException(status_code=400, detail="empty proposal content")

        # Sanitize filename — prevent path traversal
        safe_filename = Path(filename).name  # strips any directory components
        if not safe_filename or safe_filename.startswith("."):
            safe_filename = f"{uuid.uuid4()}.md"

        # Ensure .md extension
        if not safe_filename.endswith(".md"):
            safe_filename += ".md"

        # Write to inbox
        proposals_dir = sync_root / "inbox" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        filepath = proposals_dir / safe_filename
        filepath.write_text(content, encoding="utf-8")

        return {"status": "ok", "filename": safe_filename, "message": "Proposal written to inbox; will be ingested on next watch cycle"}

    # ------------------------------------------------------------------
    # Export file endpoints
    # ------------------------------------------------------------------

    @app.get("/exports/projects/{file_name}", response_class=PlainTextResponse)
    def get_project_export(file_name: str) -> str:
        base_dir = (sync_root / "exports" / "projects").resolve()
        path = (base_dir / file_name).resolve()
        if not str(path).startswith(str(base_dir) + os.sep) and path != base_dir:
            raise HTTPException(status_code=403, detail="access denied")
        if not path.exists():
            raise HTTPException(status_code=404, detail="export not found")
        return path.read_text(encoding="utf-8")

    @app.get("/exports/global/{file_name}", response_class=PlainTextResponse)
    def get_global_export(file_name: str) -> str:
        base_dir = (sync_root / "exports" / "global").resolve()
        path = (base_dir / file_name).resolve()
        if not str(path).startswith(str(base_dir) + os.sep) and path != base_dir:
            raise HTTPException(status_code=403, detail="access denied")
        if not path.exists():
            raise HTTPException(status_code=404, detail="export not found")
        return path.read_text(encoding="utf-8")

    @app.get("/status.md", response_class=PlainTextResponse)
    def get_status() -> str:
        path = status_publisher.publish()
        return path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # V2 Knowledge API endpoints
    # ------------------------------------------------------------------

    @app.get("/api/knowledge/stats")
    def knowledge_stats() -> dict:
        """Return node counts by stage."""
        counts = repo.count_knowledge_nodes_by_stage()
        total = sum(counts.values())
        return {"total": total, "by_stage": counts}

    @app.get("/api/knowledge/list")
    def knowledge_list(
        stage: str | None = None,
        category: str | None = None,
        domain: str | None = None,
        limit: int = Query(default=50, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> list[dict]:
        """List knowledge nodes with optional filters."""
        nodes = repo.list_knowledge_nodes(
            stage=stage, category=category, domain=domain,
            limit=limit, offset=offset,
        )
        return [
            {
                "id": n.id,
                "summary": n.summary[:120],
                "category": n.category,
                "domain": n.domain,
                "stage": n.stage,
                "confidence": n.confidence,
                "source": n.source,
                "created_at": n.created_at,
                "supersedes": n.supersedes,
            }
            for n in nodes
        ]

    @app.get("/api/knowledge/{node_id}")
    def knowledge_detail(node_id: str) -> dict:
        """Get full details of a knowledge node including thought chains."""
        node = repo.get_knowledge_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        chains = repo.get_thought_chains(node_id)
        children = repo.find_children(node_id)
        return {
            "node": {
                "id": node.id,
                "parent_id": node.parent_id,
                "content": node.content,
                "summary": node.summary,
                "category": node.category,
                "domain": node.domain,
                "stage": node.stage,
                "operation": node.operation,
                "confidence": node.confidence,
                "source": node.source,
                "evidence": node.evidence,
                "supersedes": node.supersedes,
                "merged_from": node.merged_from,
                "contradicts": node.contradicts,
                "verified_by": node.verified_by,
                "created_at": node.created_at,
                "refined_at": node.refined_at,
                "verified_at": node.verified_at,
                "deprecated_at": node.deprecated_at,
                "retrieval_count": node.retrieval_count,
                "correction_count": node.correction_count,
            },
            "thought_chains": [
                {
                    "id": tc.id,
                    "action": tc.action,
                    "reasoning": tc.reasoning,
                    "decision": tc.decision,
                    "confidence": tc.confidence_in_decision,
                    "created_at": tc.created_at,
                }
                for tc in chains
            ],
            "children_count": len(children),
        }

    @app.post("/api/knowledge/integrate")
    async def knowledge_integrate(request: Request) -> dict:
        """Integrate new knowledge into the knowledge tree via API."""
        from hermes.integrate import integrate as _integrate
        body = await request.json()
        content = body.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="content is required")
        result = _integrate(
            content=content,
            source=body.get("source", "api"),
            category=body.get("category", "fact"),
            domain=body.get("domain", "general"),
            parent_id=body.get("parent_id"),
            evidence=body.get("evidence"),
            repo=repo,
        )
        return {
            "action": result.action,
            "node_id": result.node_id,
            "stage": result.stage,
            "confidence": result.confidence,
            "merged_from": result.merged_from,
            "superseded": result.superseded,
            "message": f"{result.action.replace('_', ' ').title()}: {result.node_id[:8]}… (stage={result.stage})",
        }

    @app.post("/api/knowledge/{node_id}/stage")
    async def knowledge_update_stage(node_id: str, request: Request) -> dict:
        """Update a knowledge node's stage (promote/demote)."""
        node = repo.get_knowledge_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        try:
            body = await request.json()
        except Exception:
            body = {}
        new_stage = body.get("stage")
        if new_stage not in ("draft", "refined", "verified", "canonized", "deprecated"):
            raise HTTPException(status_code=400, detail=f"invalid stage: {new_stage}")
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        update_fields = {"stage": new_stage}
        if new_stage == "refined":
            update_fields["refined_at"] = now
        elif new_stage == "verified":
            update_fields["verified_at"] = now
        elif new_stage == "deprecated":
            update_fields["deprecated_at"] = now
        repo.update_knowledge_node(node_id, **update_fields)
        # Recompute confidence after stage change
        from hermes.integrate import recompute_confidence
        updated_node = repo.get_knowledge_node(node_id)
        if updated_node:
            new_conf = recompute_confidence(updated_node, repo)
            repo.update_knowledge_node(node_id, confidence=new_conf)
        return {"node_id": node_id, "stage": new_stage}

    @app.patch("/api/knowledge/{node_id}")
    async def knowledge_patch_node(node_id: str, request: Request) -> dict:
        """Edit summary, content, category, or domain of a knowledge node."""
        node = repo.get_knowledge_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        try:
            body = await request.json()
        except Exception:
            body = {}
        editable = {"summary", "content", "category", "domain"}
        updates = {k: v for k, v in body.items() if k in editable and v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="no editable fields provided")
        repo.update_knowledge_node(node_id, **updates)
        updated = repo.get_knowledge_node(node_id)
        return {"node_id": node_id, "updated_fields": list(updates.keys()), "summary": updated.summary, "domain": updated.domain}

    @app.post("/api/knowledge/{node_id}/merge/{source_id}")
    async def knowledge_merge_nodes(node_id: str, source_id: str) -> dict:
        """Merge source_id into node_id. Source gets deprecated, target gets content merged."""
        from datetime import datetime, timezone
        from hermes.repository import ThoughtChain
        import json as _json
        import uuid

        target = repo.get_knowledge_node(node_id)
        source = repo.get_knowledge_node(source_id)
        if not target:
            raise HTTPException(status_code=404, detail=f"target node {node_id} not found")
        if not source:
            raise HTTPException(status_code=404, detail=f"source node {source_id} not found")
        now = datetime.now(timezone.utc).isoformat()

        # Merge content
        merged_content = (target.content + "\n\n---\n(Merged from " + source_id[:8] + "…)\n" + source.content)
        merged_summary = target.summary
        merged_from = _json.loads(target.merged_from or "[]") + [source_id]
        repo.update_knowledge_node(
            node_id,
            content=merged_content,
            summary=merged_summary,
            merged_from=_json.dumps(merged_from),
            stage="refined",
            refined_at=now,
        )

        # Deprecate source
        repo.update_knowledge_node(source_id, stage="deprecated", deprecated_at=now)

        # Record thought chain
        tc = ThoughtChain(
            id=str(uuid.uuid4()),
            node_id=node_id,
            action="merge",
            reasoning=f"Manually merged {source_id} into {node_id} via UI.",
            evidence_used=_json.dumps([source_id]),
            decision="merge",
            confidence_in_decision=1.0,
            created_at=now,
        )
        repo.insert_thought_chain(tc)
        return {"merged_into": node_id, "deprecated": source_id, "action": "merge"}

    @app.post("/api/knowledge/retrospect")
    def knowledge_retrospect(dry_run: bool = Query(default=False)) -> dict:
        """Run periodic knowledge maintenance."""
        from hermes.integrate import retrospect
        actions = retrospect(repo, dry_run=dry_run)
        return {"dry_run": dry_run, "actions": actions}

    @app.post("/api/knowledge/export")
    def knowledge_export() -> dict:
        """Export canonized knowledge to KNOWLEDGE.md."""
        from hermes.exporter import ExportCompiler
        exporter = ExportCompiler(repo=repo, sync_root=config.sync_root)
        path = exporter.build_knowledge_export()
        return {"path": str(path), "size_bytes": path.stat().st_size}

    @app.delete("/api/knowledge/{node_id}")
    async def knowledge_delete_node(node_id: str) -> dict:
        """Permanently delete a knowledge node (trash empty action)."""
        node = repo.get_knowledge_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        if node.stage != "deprecated":
            raise HTTPException(status_code=400, detail="only deprecated nodes can be deleted — deprecate first")
        repo.delete_knowledge_node(node_id)
        return {"deleted": node_id}

    @app.delete("/api/knowledge/trash/empty")
    async def knowledge_empty_trash() -> dict:
        """Permanently delete all deprecated nodes."""
        deprecated = repo.list_knowledge_nodes(stage="deprecated", limit=10000)
        count = 0
        for n in deprecated:
            repo.delete_knowledge_node(n.id)
            count += 1
        return {"deleted": count}

    # ------------------------------------------------------------------
    # HTML pages – exports list
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # HTML pages – review queue
    # ------------------------------------------------------------------

    _VALID_STATES = {"pending", "approved_db_only", "approved_for_export", "rejected", "all"}

    @app.get("/review", response_class=HTMLResponse)
    def review_queue_page_route(state: str = Query(default="pending")):
        return RedirectResponse("/knowledge", status_code=301)

    @app.get("/review/approved", response_class=HTMLResponse)
    def review_approved_redirect():
        return RedirectResponse("/knowledge", status_code=301)

    @app.get("/review/rejected", response_class=HTMLResponse)
    def review_rejected_redirect():
        return RedirectResponse("/knowledge", status_code=301)

    # ------------------------------------------------------------------
    # HTML pages – review detail
    # ------------------------------------------------------------------

    @app.get("/review/{proposal_id}", response_class=HTMLResponse)
    def review_detail_page_route(proposal_id: str) -> str:
        try:
            proposal = repo.get_proposal(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="proposal not found") from exc
        return review_detail_page(proposal=proposal)

    # ------------------------------------------------------------------
    # HTML pages – knowledge tree
    # ------------------------------------------------------------------

    _VALID_KN_STAGES = {"draft", "refined", "verified", "canonized", "deprecated", "all"}

    @app.get("/knowledge", response_class=HTMLResponse)
    def knowledge_page_route(
        stage: str = Query(default="all"),
        category: str = Query(default=""),
        domain: str = Query(default=""),
        limit: int = Query(default=100, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> str:
        stage = stage if stage in _VALID_KN_STAGES else "all"
        stage_counts = repo.count_knowledge_nodes_by_stage()
        if stage == "all":
            node_objs = repo.list_knowledge_nodes(
                category=category or None,
                domain=domain or None,
                limit=limit,
                offset=offset,
            )
        else:
            node_objs = repo.list_knowledge_nodes(
                stage=stage,
                category=category or None,
                domain=domain or None,
                limit=limit,
                offset=offset,
            )
        # Convert dataclasses to dicts for template rendering
        from dataclasses import asdict
        nodes = [asdict(n) for n in node_objs]
        all_domains = sorted({n.get("domain", "general") for n in nodes}) if nodes else []
        return knowledge_page(
            nodes=nodes,
            counts=stage_counts,
            active_stage=stage,
            active_category=category,
            active_domain=domain,
            domains=all_domains,
        )

    @app.get("/knowledge/{node_id}", response_class=HTMLResponse)
    def knowledge_detail_page_route(node_id: str) -> str:
        node = repo.get_knowledge_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        chains = repo.get_thought_chains(node_id)
        children = repo.find_children(node_id)
        # Resolve parent node if parent_id exists
        parent_node = None
        if node.parent_id:
            pn = repo.get_knowledge_node(node.parent_id)
            if pn:
                parent_node = {"id": pn.id, "summary": pn.summary, "stage": pn.stage}
        # Resolve supersedes node
        supersedes_node = None
        if node.supersedes:
            sn = repo.get_knowledge_node(node.supersedes)
            if sn:
                supersedes_node = {"id": sn.id, "summary": sn.summary, "stage": sn.stage}
        # Resolve superseded_by (nodes that supersede this one)
        superseded_by_nodes = repo.find_superseded_nodes(node_id)
        return knowledge_detail_page(
            node={
                "id": node.id,
                "parent_id": node.parent_id,
                "content": node.content,
                "summary": node.summary,
                "category": node.category,
                "domain": node.domain,
                "stage": node.stage,
                "operation": node.operation,
                "confidence": node.confidence,
                "source": node.source,
                "evidence": node.evidence,
                "supersedes": node.supersedes,
                "merged_from": node.merged_from,
                "contradicts": node.contradicts,
                "verified_by": node.verified_by,
                "created_at": node.created_at,
                "refined_at": node.refined_at,
                "verified_at": node.verified_at,
                "deprecated_at": node.deprecated_at,
                "retrieval_count": node.retrieval_count,
                "correction_count": node.correction_count,
                "last_used_at": node.last_used_at,
            },
            thought_chains=[
                {
                    "id": tc.id,
                    "action": tc.action,
                    "reasoning": tc.reasoning,
                    "decision": tc.decision,
                    "confidence_in_decision": tc.confidence_in_decision,
                    "created_at": tc.created_at,
                }
                for tc in chains
            ],
            parent_node=parent_node,
            child_nodes=[{"id": c.id, "summary": c.summary, "stage": c.stage} for c in children],
            supersedes_node=supersedes_node,
            superseded_by=[{"id": s.id, "summary": s.summary, "stage": s.stage} for s in superseded_by_nodes],
        )

    @app.post("/knowledge/{node_id}/stage")
    async def knowledge_stage_action(node_id: str, stage: str = Form(...)) -> dict:
        """Update a knowledge node's stage (promote/deprecate) via form POST."""
        node = repo.get_knowledge_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        if stage not in ("draft", "refined", "verified", "canonized", "deprecated"):
            raise HTTPException(status_code=400, detail=f"invalid stage: {stage}")
        now = datetime.now(timezone.utc).isoformat()
        update_fields: dict = {"stage": stage}
        if stage == "refined":
            update_fields["refined_at"] = now
        elif stage == "verified":
            update_fields["verified_at"] = now
        elif stage == "deprecated":
            update_fields["deprecated_at"] = now
        repo.update_knowledge_node(node_id, **update_fields)
        # Recompute confidence after stage change
        from hermes.integrate import recompute_confidence
        updated_node = repo.get_knowledge_node(node_id)
        if updated_node:
            new_conf = recompute_confidence(updated_node, repo)
            repo.update_knowledge_node(node_id, confidence=new_conf)
        return {"node_id": node_id, "stage": stage}

    # ------------------------------------------------------------------
    # Security Monitor – standalone page
    # ------------------------------------------------------------------

    @app.get("/security", response_class=HTMLResponse, response_model=None)
    def security_route() -> str:
        do_status = _collect_do_security()
        proxy_status, proxy_traffic = _collect_proxy_security()
        return security_page(
            do_status=do_status,
            proxy_status=proxy_status,
            proxy_traffic=proxy_traffic,
        )

    # --- Pools/Quota/Grok data collection (kept for /api endpoints) ---

    _QUOTA_API_BASE = os.environ.get("QUOTA_API_BASE", "")
    _QUOTA_API_KEY = os.environ.get("QUOTA_API_KEY", "")

    def _fetch_quota_data() -> tuple[list[dict], dict, str, str | None]:
        """Fetch auth-files from Space and classify accounts.
        
        Returns (accounts, summary, last_updated, error).
        """
        try:
            resp = httpx.get(
                f"{_QUOTA_API_BASE}/v0/management/auth-files",
                headers={"Authorization": f"Bearer {_QUOTA_API_KEY}"},
                timeout=15,
            )
            if resp.status_code != 200:
                return [], {}, "", f"HTTP {resp.status_code}: {resp.text[:200]}"
            import json
            data = json.loads(resp.text, strict=False)
            files = data.get("files", [])
            codex_files = [f for f in files if f.get("provider") == "codex"]
            last_updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

            accounts = []
            summary = {"available": 0, "exhausted": 0, "disabled_count": 0, "unavailable": 0, "total": len(codex_files)}

            for f in codex_files:
                name = f.get("name", "").replace("codex-", "").replace("-free.json", "")
                email = f.get("email", "")
                disabled = f.get("disabled", False)
                unavailable = f.get("unavailable", False)
                limit_reached = f.get("limit_reached", False)
                status = f.get("status", "")
                next_retry = f.get("next_retry_after", "")
                usage_pct = int(f.get("usage_percent", 0) or 0)

                if unavailable:
                    group = "unavailable"
                    status_label = "unavailable"
                    summary["unavailable"] += 1
                elif disabled:
                    if limit_reached:
                        group = "exhausted"
                        status_label = "exhausted"
                        summary["exhausted"] += 1
                    else:
                        group = "disabled"
                        status_label = "disabled"
                        summary["disabled_count"] += 1
                elif limit_reached:
                    group = "exhausted"
                    status_label = "exhausted"
                    summary["exhausted"] += 1
                else:
                    group = "available"
                    status_label = "active"
                    summary["available"] += 1

                # Format next_retry_after for display
                reset_time = "—"
                if next_retry:
                    try:
                        # Parse ISO format and show short date
                        dt = datetime.fromisoformat(next_retry.replace("Z", "+00:00"))
                        reset_time = dt.strftime("%m/%d %H:%M")
                    except Exception:
                        reset_time = next_retry[:16]

                accounts.append({
                    "name": name or email,
                    "email": email,
                    "usage_pct": usage_pct,
                    "group": group,
                    "status_label": status_label,
                    "reset_time": reset_time,
                    "limit_reached": limit_reached,
                    "disabled": disabled,
                    "unavailable": unavailable,
                })

            return accounts, summary, last_updated, None
        except Exception as exc:
            return [], {}, "", str(exc)

    @app.get("/api/quota")
    def quota_api() -> dict:
        """JSON API for quota data."""
        accounts, summary, last_updated, error = _fetch_quota_data()
        return {
            "accounts": accounts,
            "summary": summary,
            "last_updated": last_updated,
            "error": error,
        }

    # ------------------------------------------------------------------
    # Grok token pool board – pulls live data from grok2api
    # ------------------------------------------------------------------

    _GROK_API_BASE = "http://127.0.0.1:8000"
    _GROK_API_KEY = os.environ.get("GROK_API_KEY", "grok2api")

    def _fetch_grok_data() -> tuple[list[dict], dict, str, str | None]:
        """Fetch token data from grok2api and classify tokens.

        Returns (tokens, summary, last_updated, error).
        """
        try:
            resp = httpx.get(
                f"{_GROK_API_BASE}/admin/api/tokens?app_key={_GROK_API_KEY}",
                timeout=15,
            )
            if resp.status_code != 200:
                return [], {}, "", f"HTTP {resp.status_code}: {resp.text[:200]}"
            data = resp.json()
            raw_tokens = data.get("tokens", [])
            last_updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

            tokens = []
            summary = {"total": len(raw_tokens), "active": 0, "pools": {}}
            fast_total = 0
            fast_used = 0

            for t in raw_tokens:
                status = t.get("status", "unknown")
                pool = t.get("pool", "basic")
                quota = t.get("quota", {}) or {}
                use_count = t.get("use_count", 0)
                last_used = t.get("last_used_at")

                # Format last_used
                last_used_fmt = "—"
                if last_used:
                    try:
                        dt = datetime.fromtimestamp(last_used / 1000, tz=timezone.utc)
                        last_used_fmt = dt.strftime("%m/%d %H:%M")
                    except Exception:
                        last_used_fmt = str(last_used)[:16]

                if status == "active":
                    summary["active"] += 1

                # Pool aggregation
                if pool not in summary["pools"]:
                    summary["pools"][pool] = {"total": 0, "active": 0, "fast_remaining": 0, "fast_total": 0}
                summary["pools"][pool]["total"] += 1
                if status == "active":
                    summary["pools"][pool]["active"] += 1
                fq = quota.get("fast", {}) or {}
                summary["pools"][pool]["fast_remaining"] += fq.get("remaining", 0)
                summary["pools"][pool]["fast_total"] += fq.get("total", 0)
                fast_total += fq.get("total", 0)
                fast_used += (fq.get("total", 0) - fq.get("remaining", 0))

                tokens.append({
                    "token": t.get("token", ""),
                    "pool": pool,
                    "status": status,
                    "use_count": use_count,
                    "last_used_at_fmt": last_used_fmt,
                    "quota": quota,
                })

            summary["fast_total"] = fast_total
            summary["fast_used"] = fast_used
            return tokens, summary, last_updated, None
        except Exception as exc:
            return [], {}, "", str(exc)

    @app.get("/api/grok")
    def grok_api() -> dict:
        """JSON API for grok token data."""
        tokens, summary, last_updated, error = _fetch_grok_data()
        return {
            "tokens": tokens,
            "summary": summary,
            "last_updated": last_updated,
            "error": error,
        }

    # ------------------------------------------------------------------
    # Plotting Gallery – renders sci-fig template gallery
    # ------------------------------------------------------------------
    from fastapi.staticfiles import StaticFiles

    @app.get("/gallery", response_class=HTMLResponse)
    def gallery_route() -> str:
        return gallery_page()

    # Serve demo images for the gallery
    _PLOTTING_STATIC = Path(os.environ.get("BRAIN_PLOTTING_DIR", ""))
    if _PLOTTING_STATIC.is_dir():
        app.mount("/gallery/static", StaticFiles(directory=str(_PLOTTING_STATIC)), name="gallery-static")

    
    # ------------------------------------------------------------------
    # Gallery feedback API – approve/suggest/reject for chart templates
    # ------------------------------------------------------------------
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    _GALLERY_FEEDBACK = Path(os.environ.get("BRAIN_PLOTTING_DIR", "")) / "gallery_feedback.jsonl"

    @app.post("/api/gallery/feedback")
    async def gallery_feedback(request: Request) -> dict:
        """Store gallery feedback (approve/suggest/reject) for a chart template."""
        body = await request.json()
        chart = body.get("chart", "")
        action = body.get("action", "")  # approve, suggest, reject
        suggestion = body.get("suggestion", "")
        if not chart or action not in ("approve", "suggest", "reject"):
            return {"ok": False, "error": "Invalid chart or action"}
        entry = {
            "chart": chart,
            "action": action,
            "suggestion": suggestion,
            "timestamp": _dt.now(_tz.utc).isoformat(),
        }
        with open(_GALLERY_FEEDBACK, "a") as f:
            f.write(_json.dumps(entry) + "\n")
        return {"ok": True, "action": action, "chart": chart}

    # ------------------------------------------------------------------
    # Gallery figure submission – submit an external figure for analysis
    # ------------------------------------------------------------------
    _FIGURE_SUBMIT_DIR = Path(os.environ.get("BRAIN_PLOTTING_DIR", "")) / "submitted_figures"
    _FIGURE_SUBMIT_DIR.mkdir(parents=True, exist_ok=True)

    @app.post("/api/gallery/submit_figure")
    async def gallery_submit_figure(request: Request) -> dict:
        """Submit a figure image URL or upload for reverse-engineering analysis."""
        import urllib.request as _urlreq
        import hashlib as _hashlib
        content_type = request.headers.get("content-type", "")

        image_url = ""
        image_b64 = ""
        notes = ""

        if "multipart/form-data" in content_type:
            # Handle file upload
            form = await request.form()
            image_url = form.get("image_url", "")
            notes = form.get("notes", "")
            upload = form.get("file")
            if upload and hasattr(upload, "filename"):
                data = await upload.read()
                ext = Path(upload.filename or "img.png").suffix or ".png"
                fname = _hashlib.md5(data).hexdigest()[:12] + ext
                fpath = _FIGURE_SUBMIT_DIR / fname
                fpath.write_bytes(data)
                image_url = image_url or f"/gallery/submitted/{fname}"
        else:
            body = await request.json()
            image_url = body.get("image_url", "")
            notes = body.get("notes", "")

        if not image_url:
            return {"ok": False, "error": "image_url or file required"}

        # Download remote URLs locally
        if image_url.startswith("http"):
            try:
                resp = _urlreq.urlopen(image_url, timeout=15)
                data = resp.read()
                ext = Path(image_url.split("?")[0]).suffix or ".png"
                if len(ext) > 5:
                    ext = ".png"
                fname = _hashlib.md5(data).hexdigest()[:12] + ext
                fpath = _FIGURE_SUBMIT_DIR / fname
                fpath.write_bytes(data)
                image_url = f"/gallery/submitted/{fname}"
            except Exception as e:
                # Keep original URL if download fails
                pass

        entry = {
            "action": "analyze_figure",
            "image_url": image_url,
            "notes": notes,
            "timestamp": _dt.now(_tz.utc).isoformat(),
        }
        with open(_GALLERY_FEEDBACK, "a") as f:
            f.write(_json.dumps(entry) + "\n")
        return {"ok": True, "image_url": image_url, "notes": notes}

    # Serve submitted figures
    app.mount("/gallery/submitted", StaticFiles(directory=str(_FIGURE_SUBMIT_DIR)), name="gallery-submitted")


    # ------------------------------------------------------------------
    # Security Monitor – collects data from DO VPS + Proxy VPS
    # ------------------------------------------------------------------
    import subprocess as _sp

    def _collect_do_security() -> dict:
        """Collect security status from the local DO VPS."""
        result = {
            "ssh_port": "50022",
            "f2b_banned": [],
            "f2b_total": 0,
            "ufw_rules": [],
            "top_attackers": [],
            "uptime": "?",
            "sysctl": {},
        }
        try:
            out = _sp.run(["fail2ban-client", "status", "sshd"], capture_output=True, text=True, timeout=5).stdout
            import re as _re
            banned_match = _re.search(r"Banned IP list:\s*(.*)", out)
            total_match = _re.search(r"Total banned:\s*(\d+)", out)
            if banned_match:
                ips = banned_match.group(1).strip().split()
                result["f2b_banned"] = ips
            if total_match:
                result["f2b_total"] = int(total_match.group(1))
        except Exception:
            pass
        try:
            out = _sp.run(["ufw", "status", "numbered"], capture_output=True, text=True, timeout=5).stdout
            import ipaddress as _ip
            for line in out.splitlines():
                if "[" in line and ("ALLOW" in line or "REJECT" in line or "DENY" in line or "LIMIT" in line):
                    parts = line.strip().split()
                    action = next((p for p in parts if p in ("ALLOW", "REJECT", "DENY", "LIMIT")), "")
                    if not action:
                        continue
                    to_idx = parts.index(action) - 1 if action in parts else -1
                    to_port = parts[to_idx] if to_idx >= 0 else ""
                    comment = ""
                    if "#" in line:
                        comment = line.split("#", 1)[1].strip()
                    # Skip fail2ban auto-REJECT/DENY lines (no meaningful comment)
                    if action in ("REJECT", "DENY") and not comment:
                        continue
                    result["ufw_rules"].append({"action": action, "to": to_port, "comment": comment})
        except Exception:
            pass
        try:
            out = _sp.run(
                ["bash", "-c", "grep 'Failed password' /var/log/auth.log 2>/dev/null | grep -oP '(\\d{1,3}\\.){3}\\d{1,3}' | sort | uniq -c | sort -rn | head -8"],
                capture_output=True, text=True, timeout=5
            ).stdout
            for line in out.strip().splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    result["top_attackers"].append({"ip": parts[1], "count": int(parts[0])})
        except Exception:
            pass
        try:
            result["uptime"] = _sp.run(["uptime", "-p"], capture_output=True, text=True, timeout=3).stdout.strip()
        except Exception:
            pass
        try:
            syn = _sp.run(["sysctl", "-n", "net.ipv4.tcp_syncookies"], capture_output=True, text=True, timeout=3).stdout.strip()
            redir = _sp.run(["sysctl", "-n", "net.ipv4.conf.all.accept_redirects"], capture_output=True, text=True, timeout=3).stdout.strip()
            fwd = _sp.run(["sysctl", "-n", "net.ipv4.ip_forward"], capture_output=True, text=True, timeout=3).stdout.strip()
            result["sysctl"] = {"syncookies": syn == "1", "accept_redirects": redir != "0", "ip_forward": fwd != "0"}
        except Exception:
            pass
        return result

    def _collect_proxy_security() -> tuple[dict, list[dict]]:
        """Collect security + traffic status from the proxy VPS via x-ui API + SSH."""
        _ssh_key = os.environ.get("BRAIN_SSH_KEY", os.path.expanduser("~/.ssh/id_rsa"))
        _ssh_port = os.environ.get("BRAIN_SSH_PORT", "22")
        _ssh_host = os.environ.get("BRAIN_PROXY_HOST", "")
        proxy_status = {"f2b_banned": [], "f2b_total": 0,
                        "ssh_port": _ssh_port, "ufw_rules": [], "top_attackers": [], "uptime": "?", "sysctl": {}}
        proxy_traffic = []
        XUI_URL = os.environ.get("BRAIN_XUI_URL", "")
        XUI_USER = os.environ.get("BRAIN_XUI_USER", "")
        XUI_PASS = os.environ.get("BRAIN_XUI_PASS", "")

        # --- Fetch x-ui traffic data ---
        try:
            import ssl as _ssl
            import urllib.request as _ur
            import http.cookiejar as _cj
            import urllib.parse as _up
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            cj = _cj.CookieJar()
            opener = _ur.build_opener(_ur.HTTPCookieProcessor(cj), _ur.HTTPSHandler(context=ctx))
            login_data = _up.urlencode({"username": XUI_USER, "password": XUI_PASS}).encode()
            req = _ur.Request(XUI_URL + "/login", data=login_data)
            opener.open(req, timeout=10)

            req = _ur.Request(XUI_URL + "/panel/api/inbounds/list")
            resp = opener.open(req, timeout=10)
            import json as _json
            data = _json.loads(resp.read().decode())
            for ib in data.get("obj", []):
                clients_data = []
                for cs in ib.get("clientStats", []):
                    clients_data.append({
                        "email": cs.get("email", "?"),
                        "up": cs.get("up", 0),
                        "down": cs.get("down", 0),
                        "enable": cs.get("enable", False),
                    })
                proxy_traffic.append({
                    "name": ib.get("remark", "?"),
                    "proto": ib.get("protocol", "?"),
                    "port": ib.get("port", 0),
                    "up": ib.get("up", 0),
                    "down": ib.get("down", 0),
                    "enable": ib.get("enable", False),
                    "clients": clients_data,
                })
        except Exception:
            pass

        # --- Fetch proxy VPS security data via SSH (with retry for intermittent connectivity) ---
        import re as _re, logging as _logging
        _ssh_logger = _logging.getLogger("brain.security")
        _ssh_cmd = [
            "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8",
            "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
            "-i", _ssh_key, "-p", _ssh_port, _ssh_host,
            "echo '===F2B==='; fail2ban-client status sshd 2>/dev/null || echo 'f2b-err'; "
            "echo '===UFW==='; ufw status numbered 2>/dev/null || echo 'ufw-err'; "
            "echo '===UPTIME==='; uptime -p; "
            "echo '===SYSCTL==='; sysctl -n net.ipv4.tcp_syncookies net.ipv4.conf.all.accept_redirects net.ipv4.ip_forward"
        ]
        out = None
        for _attempt in range(3):
            try:
                out = _sp.run(_ssh_cmd, capture_output=True, text=True, timeout=25)
                if out.returncode == 0 and out.stdout.strip():
                    break
                _ssh_logger.warning("SSH attempt %d RC=%s stderr=%s", _attempt + 1, out.returncode, out.stderr[:200])
            except _sp.TimeoutExpired:
                _ssh_logger.warning("SSH attempt %d timed out", _attempt + 1)
        if out and out.returncode == 0 and out.stdout.strip():
            _ssh_logger.info("SSH success RC=%s stdout_len=%s", out.returncode, len(out.stdout))
            text = out.stdout
            sections = text.split("===")
            # Parse fail2ban
            if "F2B" in text:
                f2b_section = text.split("===F2B===")[1].split("===UFW===")[0] if "===UFW===" in text else text.split("===F2B===")[1]
                banned_match = _re.search(r"Banned IP list:\s*(.*)", f2b_section)
                total_match = _re.search(r"Total banned:\s*(\d+)", f2b_section)
                if banned_match:
                    proxy_status["f2b_banned"] = banned_match.group(1).strip().split()
                if total_match:
                    proxy_status["f2b_total"] = int(total_match.group(1))
            # Parse UFW
            if "UFW" in text:
                ufw_section = text.split("===UFW===")[1].split("===UPTIME===")[0] if "===UPTIME===" in text else ""
                import ipaddress as _ip
                for line in ufw_section.splitlines():
                    if "[" in line and ("ALLOW" in line or "REJECT" in line or "DENY" in line):
                        parts = line.strip().split()
                        action = next((p for p in parts if p in ("ALLOW", "REJECT", "DENY", "LIMIT")), "")
                        if not action:
                            continue
                        to_idx = parts.index(action) - 1 if action in parts else -1
                        to_port = parts[to_idx] if to_idx >= 0 else ""
                        comment = ""
                        if "#" in line:
                            comment = line.split("#", 1)[1].strip()
                        # Skip fail2ban auto-REJECT/DENY lines (no meaningful comment)
                        if action in ("REJECT", "DENY") and not comment:
                            continue
                        proxy_status["ufw_rules"].append({"action": action, "to": to_port, "comment": comment})
            # Parse uptime
            if "UPTIME" in text:
                uptime_section = text.split("===UPTIME===")[1].split("===SYSCTL===")[0] if "===SYSCTL===" in text else ""
                proxy_status["uptime"] = uptime_section.strip()
            # Parse sysctl
            if "SYSCTL" in text:
                sysctl_section = text.split("===SYSCTL===")[1].strip().splitlines()
                if len(sysctl_section) >= 3:
                    proxy_status["sysctl"] = {
                        "syncookies": sysctl_section[0].strip() == "1",
                        "accept_redirects": sysctl_section[1].strip() != "0",
                        "ip_forward": sysctl_section[2].strip() != "0",
                    }
        else:
            _ssh_logger.warning("SSH failed after 3 attempts: no data")

        return proxy_status, proxy_traffic

    @app.get("/api/security", response_model=None)
    def security_api() -> dict:
        do_status = _collect_do_security()
        proxy_status, proxy_traffic = _collect_proxy_security()
        return {"do": do_status, "proxy": proxy_status, "proxy_traffic": proxy_traffic}

    # ------------------------------------------------------------------
    # Settings page
    # ------------------------------------------------------------------

    @app.get("/settings", response_class=HTMLResponse)
    def settings_get() -> str:
        return settings_page()

    @app.post("/settings/password")
    def settings_password(request: Request, current_password: str = Form(""), new_password: str = Form(""), confirm_password: str = Form("")):
        if not _valid_login(config.auth_username or "admin", current_password):
            return settings_page(error="Current password is incorrect")
        if new_password != confirm_password:
            return settings_page(error="New passwords do not match")
        if len(new_password) < 6:
            return settings_page(error="Password must be at least 6 characters")
        # Update password in config
        object.__setattr__(config, "auth_password", new_password)
        # Also write to .env for persistence
        import hashlib as _hl
        try:
            env_path = sync_root / ".." / ".env"
            env_path = env_path.resolve()
            if env_path.exists():
                lines = []
                with open(env_path) as f:
                    for line in f:
                        if line.startswith("HERMES_AUTH_PASSWORD="):
                            lines.append(f"HERMES_AUTH_PASSWORD={_hl.sha256(new_password.encode()).hexdigest()[:16]}\n")
                        else:
                            lines.append(line)
                with open(env_path, "w") as f:
                    f.writelines(lines)
        except Exception:
            pass
        return settings_page(success="Password updated successfully")

    # ------------------------------------------------------------------
    # Admin: hot-reload templates without full restart
    # ------------------------------------------------------------------
    @app.post("/api/admin/reload")
    def admin_reload_templates(request: Request) -> dict:
        """Hot-reload hermes.templates module (no process restart needed)."""
        if auth_enabled and not _has_valid_cookie(request):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Admin authentication required")
        import importlib
        from hermes import templates as _tmpl_mod
        try:
            importlib.reload(_tmpl_mod)
            # Re-bind all template functions in this module's scope
            from hermes.templates import (
                gallery_page, knowledge_detail_page, knowledge_tree_page as knowledge_page,
                login_page,
                review_detail_page, review_queue_page,
                security_page, settings_page,
            )
            return {"ok": True, "message": "Templates reloaded successfully"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return app