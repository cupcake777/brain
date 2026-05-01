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
        proxy_status = {"f2b_banned": [], "f2b_total": 0,
                        "ufw_rules": [], "top_attackers": [], "uptime": "?", "sysctl": {}}
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

        # --- Fetch proxy VPS security data via SSH ---
        try:
            out = _sp.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                 "-i", os.environ.get("BRAIN_SSH_KEY", os.path.expanduser("~/.ssh/id_rsa")),
                 "-p", os.environ.get("BRAIN_SSH_PORT", "22"),
                 os.environ.get("BRAIN_PROXY_HOST", ""),
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
        do_status = _collect_do_security()
        proxy_status, proxy_traffic = _collect_proxy_security()
        return security_page(
            do_status=do_status,
            proxy_status=proxy_status,
            proxy_traffic=proxy_traffic,
        )

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
                gallery_page, login_page,
                review_detail_page, review_queue_page,
                security_page, settings_page,
            )
            return {"ok": True, "message": "Templates reloaded successfully"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return app