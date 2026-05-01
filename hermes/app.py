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
    dashboard_page,
    gallery_page,
    login_page,
    pools_page,
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
            return RedirectResponse("/review", status_code=303)
        if _has_valid_cookie(request):
            return RedirectResponse("/review", status_code=303)
        return login_page()

    @app.post("/login", response_model=None)
    def login_post(request: Request, username: str = Form(""), password: str = Form("")):
        if not config.auth_token and not config.auth_username:
            return RedirectResponse("/review", status_code=303)
        if _valid_login(username, password):
            resp = RedirectResponse("/review", status_code=303)
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
        return RedirectResponse("/review", status_code=303)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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
    def approve_db_only(proposal_id: str) -> dict[str, str]:
        repo.transition_state(proposal_id, "approved_db_only")
        status_publisher.publish()
        return {"proposal_id": proposal_id, "state": "approved_db_only"}

    @app.post("/api/review/{proposal_id}/approve-for-export")
    def approve_for_export(proposal_id: str) -> dict[str, str]:
        proposal = repo.get_proposal(proposal_id)
        repo.transition_state(proposal_id, "approved_for_export")
        if proposal["project_key"] == "global" or proposal["scope"] == "global":
            exporter.build_global_export()
            exporter.build_claude_md_export()
        else:
            exporter.build_project_export(str(proposal["project_key"]))
        status_publisher.publish()
        return {"proposal_id": proposal_id, "state": "approved_for_export"}

    @app.post("/api/review/{proposal_id}/promote-to-export")
    def promote_to_export(proposal_id: str) -> dict[str, str]:
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
        return {"proposal_id": proposal_id, "state": "approved_for_export"}

    @app.post("/api/review/{proposal_id}/reject")
    def reject(proposal_id: str) -> dict[str, str]:
        repo.transition_state(proposal_id, "rejected")
        status_publisher.publish()
        return {"proposal_id": proposal_id, "state": "rejected"}

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

        # Generate filename if not provided
        if not filename:
            filename = f"{uuid.uuid4()}.md"

        # Ensure .md extension
        if not filename.endswith(".md"):
            filename += ".md"

        # Write to inbox
        proposals_dir = sync_root / "inbox" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        filepath = proposals_dir / filename
        filepath.write_text(content, encoding="utf-8")

        return {"status": "ok", "filename": filename, "message": "Proposal written to inbox; will be ingested on next watch cycle"}

    # ------------------------------------------------------------------
    # Export file endpoints
    # ------------------------------------------------------------------

    @app.get("/exports/projects/{file_name}", response_class=PlainTextResponse)
    def get_project_export(file_name: str) -> str:
        path = sync_root / "exports" / "projects" / file_name
        if not path.exists():
            raise HTTPException(status_code=404, detail="export not found")
        return path.read_text(encoding="utf-8")

    @app.get("/exports/global/{file_name}", response_class=PlainTextResponse)
    def get_global_export(file_name: str) -> str:
        path = sync_root / "exports" / "global" / file_name
        if not path.exists():
            raise HTTPException(status_code=404, detail="export not found")
        return path.read_text(encoding="utf-8")

    @app.get("/status.md", response_class=PlainTextResponse)
    def get_status() -> str:
        path = status_publisher.publish()
        return path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # HTML pages – exports list
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # HTML pages – review queue
    # ------------------------------------------------------------------

    _VALID_STATES = {"pending", "approved_db_only", "approved_for_export", "rejected", "all"}

    @app.get("/review", response_class=HTMLResponse)
    def review_queue_page_route(state: str = Query(default="pending")) -> str:
        state = state if state in _VALID_STATES else "pending"
        counts = repo.counts_by_state()
        if state == "all":
            proposals: list[dict] = []
            for s in ("pending", "approved_db_only", "approved_for_export", "rejected"):
                proposals.extend(repo.list_proposals_by_state(s))
        else:
            proposals = repo.list_proposals_by_state(state)
        return review_queue_page(
            proposals=proposals,
            counts=counts,
            active_state=state,
        )

    @app.get("/review/approved", response_class=HTMLResponse)
    def review_approved_page() -> str:
        counts = repo.counts_by_state()
        proposals = repo.list_proposals_by_state("approved_db_only") + repo.list_proposals_by_state("approved_for_export")
        return review_queue_page(
            proposals=proposals,
            counts=counts,
            active_state="approved_db_only",
        )

    @app.get("/review/rejected", response_class=HTMLResponse)
    def review_rejected_page() -> str:
        counts = repo.counts_by_state()
        proposals = repo.list_proposals_by_state("rejected")
        return review_queue_page(
            proposals=proposals,
            counts=counts,
            active_state="rejected",
        )

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
    # HTML pages – dashboard
    # ------------------------------------------------------------------

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard_route() -> str:
        counts = repo.counts_by_state()
        oldest = repo.oldest_pending_age_seconds()
        export_records = [_asdict(r) for r in repo.list_export_records()]
        # Security data for integrated dashboard
        do_status = _collect_do_security()
        proxy_status, proxy_traffic = _collect_proxy_security()
        return dashboard_page(
            counts=counts,
            oldest_pending=oldest,
            export_records=export_records,
            do_status=do_status,
            proxy_status=proxy_status,
            proxy_traffic=proxy_traffic,
        )

    @app.get("/security", response_class=HTMLResponse)
    def security_redirect_route() -> str:
        """Redirect old /security to /dashboard (security is now a dashboard section)."""
        return RedirectResponse(url="/dashboard")

    # ------------------------------------------------------------------
    # Quota board – pulls live data from HF Space
    # ------------------------------------------------------------------

    _QUOTA_API_BASE = "https://cupcake777-20t.hf.space"
    _QUOTA_API_KEY = os.environ.get("HERMES_QUOTA_API_KEY", "592252@Lyc")

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

    @app.get("/pools", response_class=HTMLResponse)
    def pools_route(tab: str = "cpa") -> str:
        accounts, summary, last_updated, quota_error = _fetch_quota_data()
        tokens, grok_summary, grok_last_updated, grok_error = _fetch_grok_data()
        return pools_page(
            accounts=accounts,
            summary=summary,
            last_updated=last_updated,
            space_error=quota_error,
            tokens=tokens,
            grok_summary=grok_summary,
            grok_last_updated=grok_last_updated,
            grok_error=grok_error,
            active_tab=tab,
        )

    @app.get("/quota", response_class=HTMLResponse)
    def quota_redirect() -> str:
        """Redirect old /quota to /pools?tab=cpa."""
        return RedirectResponse(url="/pools?tab=cpa")

    @app.get("/grok", response_class=HTMLResponse)
    def grok_redirect() -> str:
        """Redirect old /grok to /pools?tab=grok."""
        return RedirectResponse(url="/pools?tab=grok")

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
    _GROK_API_KEY=os.environ.get("GROK_API_KEY", "grok2api")

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
    _PLOTTING_STATIC = Path("/root/ops/plotting")
    if _PLOTTING_STATIC.is_dir():
        app.mount("/gallery/static", StaticFiles(directory=str(_PLOTTING_STATIC)), name="gallery-static")

    
    # ------------------------------------------------------------------
    # Gallery feedback API – approve/suggest/reject for chart templates
    # ------------------------------------------------------------------
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    _GALLERY_FEEDBACK = Path("/root/ops/plotting/gallery_feedback.jsonl")

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
        proxy_status = {"ssh_port": "50023", "f2b_banned": [], "f2b_total": 0,
                        "ufw_rules": [], "top_attackers": [], "uptime": "?", "sysctl": {}}
        proxy_traffic = []
        XUI_URL = "https://107.173.255.112:15109/R5lGRUAHs6l7Ep7O7J"
        XUI_USER = "hunqnyyRha"
        XUI_PASS = "CbHOnnzbbc"

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

        # --- Fetch proxy VPS security data via SSH ---
        try:
            out = _sp.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                 "-i", os.path.expanduser("~/.ssh/my_vps_key"), "-p", "50023",
                 "root@107.173.255.112",
                 "echo '===F2B==='; fail2ban-client status sshd 2>/dev/null || echo 'f2b-err'; "
                 "echo '===UFW==='; ufw status numbered 2>/dev/null || echo 'ufw-err'; "
                 "echo '===UPTIME==='; uptime -p; "
                 "echo '===SYSCTL==='; sysctl -n net.ipv4.tcp_syncookies net.ipv4.conf.all.accept_redirects net.ipv4.ip_forward"],
                capture_output=True, text=True, timeout=15
            )
            import re as _re
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
        except Exception:
            pass

        return proxy_status, proxy_traffic

    @app.get("/security", response_class=HTMLResponse, response_model=None)
    def security_route() -> str:
        """Redirect old /security to /dashboard (security is now a dashboard section)."""
        return RedirectResponse(url="/dashboard")

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
        config.auth_password = new_password
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
    def admin_reload_templates() -> dict:
        """Hot-reload hermes.templates module (no process restart needed)."""
        import importlib
        from hermes import templates as _tmpl_mod
        try:
            importlib.reload(_tmpl_mod)
            # Re-bind all template functions in this module's scope
            from hermes.templates import (
                dashboard_page, gallery_page, login_page,
                pools_page, review_detail_page, review_queue_page,
                security_page, settings_page,
            )
            return {"ok": True, "message": "Templates reloaded successfully"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return app