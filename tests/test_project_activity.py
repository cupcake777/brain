from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.event_store import EventStore, SensitiveRejectedError, StaticPrincipalAdapter, UnauthorizedError
from hermes.project_activity import ProjectActivity, describe_event, project_key
from hermes.project_activity_backfill import backfill
from hermes.repository import HermesRepository


def _store(path, workspace="personal", project="paper"):
    return EventStore(path, principal=StaticPrincipalAdapter(actor="codex", workspace=workspace, project=project))


def _event(store, *, identity=None, hour=12, capture=None, action="codex PostToolUse Edit completed", **extra):
    return store.record_event(id=identity or str(uuid4()), project_id=store._resolve_principal().project,
                              agent_id="codex", occurred_at=datetime(2026, 11, 27, hour, tzinfo=timezone.utc),
                              action=action, result="completed", capture=capture, **extra)


def _app(tmp_path, *, auth=False, scoped=False):
    options = {}
    if scoped:
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({"version": 1, "tokens": [{
            "name": "agent", "actor": "codex", "workspace": "personal", "projects": ["paper"],
            "default_project": "paper", "token_sha256": hashlib.sha256(b"agent-token").hexdigest(),
            "permissions": ["events:read", "events:write"],
        }]}))
        token_file.chmod(0o600)
        options["brain_scoped_tokens_file"] = str(token_file)
    config = HermesConfig(sync_root=tmp_path, db_path=tmp_path / "brain.sqlite3",
                          auth_token="owner-token" if auth else None, brain_v2_enabled=True,
                          brain_v2_actor="codex", brain_v2_workspace="personal", brain_v2_project="paper", **options)
    return TestClient(create_app(repo=HermesRepository(config.db_path), sync_root=tmp_path, config=config)), config.db_path


def test_project_view_reads_old_schema_without_mutating_it(tmp_path):
    path = tmp_path / "old.sqlite3"
    assert ProjectActivity(path).projects() == []
    store = _store(path)
    _event(store)
    store.close()
    conn = sqlite3.connect(path)
    conn.execute("DROP INDEX idx_source_events_project_activity")
    conn.execute("ALTER TABLE source_events DROP COLUMN capture")
    conn.commit()
    conn.close()
    projects = ProjectActivity(path).projects()
    assert projects[0]["event_count"] == 1
    assert projects[0]["context_count"] == 0
    assert not ProjectActivity(path).timeline(projects[0]["key"])["events"][0]["has_context"]
    conn = sqlite3.connect(path)
    assert "capture" not in {r[1] for r in conn.execute("PRAGMA table_info(source_events)")}
    conn.close()


def test_project_history_separates_workspaces_and_latest_revisions(tmp_path):
    path = tmp_path / "brain.sqlite3"
    store = _store(path)
    first = _event(store, capture={"session_id": "s", "tool_name": "Edit", "input": {"file_path": "analysis.py"}})
    _event(store, identity=first["id"], capture={"session_id": "s", "tool_name": "Edit", "input": {"file_path": "new.py"}})
    _event(store, hour=13, action="codex PostToolUse Bash failed", capture={"status": "failed", "input": {"command": "pytest"}})
    store.close()
    other = _store(path, workspace="other")
    _event(other, capture={"session_id": "s", "input": {"command": "private-other-project"}})
    other.close()
    view = ProjectActivity(path)
    projects = view.projects()
    assert len(projects) == 2
    paper = next(p for p in projects if p["workspace"] == "personal")
    assert paper["event_count"] == 2
    assert paper["session_count"] == 1
    assert paper["latest"]["summary"] == "pytest"
    detail = view.timeline(paper["key"])
    assert detail["total"] == 2
    assert detail["events"][1]["files"] == ["new.py"]
    assert detail["events"][1]["version"] == 2
    assert "private-other-project" not in json.dumps(detail)
    assert view.timeline(paper["key"], status="failed")["total"] == 1
    assert view.timeline(paper["key"], query="new.py")["total"] == 1
    assert view.timeline(paper["key"], query="%'")["total"] == 0
    assert view.timeline(paper["key"], limit=1)["has_more"]
    assert len(view.timeline(paper["key"], limit=1, offset=1)["events"]) == 1
    assert view.timeline("missing") is None
    store = _store(path)
    goal = _event(store, hour=14, capture={"kind": "request", "text": "Add a project history view", "session_id": "s"})
    summary = _event(store, hour=15, capture={"kind": "summary", "text": "Added history. Next: browser review.", "session_id": "s"})
    store.close()
    filtered = view.timeline(paper["key"], query="new.py")
    assert filtered["highlights"]["request"]["id"] == goal["id"]
    assert filtered["highlights"]["summary"]["id"] == summary["id"]


def test_capture_is_privacy_scanned_and_identity_cannot_cross_scope(tmp_path):
    path = tmp_path / "brain.sqlite3"
    store = _store(path)
    with pytest.raises(SensitiveRejectedError):
        _event(store, capture={"input": {"command": "api_key=abcdefghijklmno"}})
    assert store.list_events() == []
    first = _event(store, capture={"session_id": "real-session"})
    assert _event(store, identity=first["id"], capture={"session_id": "real-session"})["status"] == "duplicate"
    store.close()
    other = _store(path, workspace="other")
    with pytest.raises(UnauthorizedError):
        _event(other, identity=first["id"], capture={"session_id": "real-session"})
    other.close()


def test_api_persists_context_and_project_pages_escape_untrusted_text(tmp_path):
    client, path = _app(tmp_path)
    payload = {"id": str(uuid4()), "project_id": "paper", "agent_id": "codex",
               "occurred_at": "2026-11-27T12:00:00Z", "action": "Edit completed", "result": "completed",
               "capture": {"session_id": "real-session", "tool_name": "Edit",
                           "input": {"file_path": "<script>alert(1)</script>.py", "description": "Fix project capture"}}}
    response = client.post("/api/v2/brain/events", json=payload)
    assert response.status_code == 200, response.text
    listed = client.get("/api/v2/brain/events").json()
    assert listed[0]["capture"]["session_id"] == "real-session"
    assert client.post("/api/v2/brain/events", json=payload).json()["status"] == "duplicate"
    key = client.get("/api/projects").json()["projects"][0]["key"]
    page = client.get(f"/projects/{key}")
    assert page.status_code == 200
    assert "real-session" in page.text
    assert "Fix project capture" in page.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;.py" in page.text
    assert "<script>alert(1)</script>.py" not in page.text
    assert 'href="/projects"' in client.get("/").text
    assert client.get("/projects").status_code == 200
    assert client.get("/projects/missing").status_code == 404
    assert client.get(f"/api/projects/{key}/activity?status=failed").json()["total"] == 0
    assert client.get(f"/api/projects/{key}/activity?offset=-1").status_code == 422
    assert client.get(f"/api/projects/{key}/activity?status=made-up").status_code == 422
    for capture, expected in (({"principal_workspace": "other"}, 422),
                              ({"input": {"api_key": "private-credential"}}, 422),
                              ({"input": {"command": "x" * 70000}}, 413)):
        rejected = client.post("/api/v2/brain/events", json={**payload, "id": str(uuid4()), "capture": capture})
        assert rejected.status_code == expected, rejected.text
    assert len(client.get("/api/v2/brain/events").json()) == 1


def test_cross_project_operator_endpoints_reject_agent_and_anonymous_access(tmp_path):
    client, path = _app(tmp_path, auth=True, scoped=True)
    store = _store(path)
    _event(store)
    store.close()
    key = project_key("personal", "paper")
    for endpoint in ("/api/projects", f"/api/projects/{key}/activity"):
        assert client.get(endpoint).status_code == 401
        assert client.get(endpoint, headers={"Authorization": "Bearer agent-token"}).status_code == 401
        assert client.get(endpoint, headers={"Authorization": "Bearer owner-token"}).status_code == 200
    assert client.get("/projects", follow_redirects=False).status_code == 303
    assert client.get("/projects", headers={"Authorization": "Bearer agent-token"}, follow_redirects=False).status_code == 303
    assert client.get("/projects", headers={"Authorization": "Bearer owner-token"}).status_code == 200


def test_backfill_appends_verified_revision_without_changing_original_or_outbox(tmp_path):
    path = tmp_path / "brain.sqlite3"
    outbox = tmp_path / "outbox.sqlite3"
    payload = {"id": str(uuid4()), "project_id": "paper", "capture": {"session_id": "historical", "input": {"file_path": "real.py"}}}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    conn = sqlite3.connect(outbox)
    conn.execute("CREATE TABLE jobs(kind TEXT,payload_json TEXT)")
    conn.execute("INSERT INTO jobs VALUES ('execution',?)", (json.dumps(payload),))
    conn.commit()
    conn.close()
    original_outbox = outbox.read_bytes()
    store = _store(path)
    _event(store, identity=payload["id"], client_digest=digest)
    store.close()
    assert backfill(path, [outbox])["candidates"] == 1
    assert ProjectActivity(path).projects()[0]["context_count"] == 0
    assert backfill(path, [outbox], apply=True)["applied"] == 1
    assert backfill(path, [outbox], apply=True)["already_present"] == 1
    assert outbox.read_bytes() == original_outbox
    store = _store(path)
    assert store.get_event(payload["id"], version=1)["capture"] == {}
    assert store.get_event(payload["id"], version=2)["capture"]["session_id"] == "historical"
    store.close()
    assert ProjectActivity(path).projects()[0]["event_count"] == 1


def test_summary_and_patch_description_keep_claims_distinct():
    base = dict(id="event", version=1, occurred_at="2026-11-27T12:00:00Z", received_at="", agent_id="codex")
    row = describe_event({**base, "capture": {"kind": "summary", "text": "Finished the capture repair. Next: review UI."}})
    assert row["kind"] == "summary"
    assert row["summary"].startswith("Finished the capture repair")
    row = describe_event({**base, "capture": {"tool_name": "apply_patch", "input": {"patch": "*** Begin Patch\n*** Update File: src/main.py\n*** End Patch"}}})
    assert row["files"] == ["src/main.py"]
    assert row["file_operation"] == "change"

    row = describe_event({**base, "capture": {"tool_name": "Bash", "input": {"command": "cat > src/repair.py <<'PY'\nprint('body')\nPY"}}})
    assert row["summary"] == "写入文件 · src/repair.py"
    assert row["files"] == ["src/repair.py"]
    assert row["file_operation"] == "change"
    assert "print('body')" in row["command"]
