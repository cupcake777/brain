"""Operator-facing project history projected from immutable execution evidence.

A successful tool invocation is an observed action, never task completion.
Workspace/project pairs remain separate even when directory names coincide.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlencode

from .workspace import shell


def _e(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def project_key(workspace: str, project: str) -> str:
    return hashlib.sha256(json.dumps([workspace, project], ensure_ascii=False).encode()).hexdigest()[:24]


def _short(value: object, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _write_target(command: str) -> str:
    first = next((line.strip() for line in command.splitlines() if line.strip()), "")
    write = re.match(r"cat\s*>{1,2}\s*([^\s]+)", first)
    return write.group(1).strip("\"'") if write else ""


def _command_label(command: str) -> str:
    first = next((line.strip() for line in command.splitlines() if line.strip()), "")
    target = _write_target(command)
    if target:
        return "写入文件 · " + target
    if re.search(r"(?:^|/)(?:python[0-9.]*)\s.*<<", first):
        return "运行 Python 脚本"
    return first


def describe_event(row: dict[str, Any]) -> dict[str, Any]:
    """Produce a traceable description; legacy rows keep their actual limits."""
    capture = row.get("capture") or {}
    if isinstance(capture, str):
        try:
            capture = json.loads(capture)
        except (ValueError, TypeError):
            capture = {}
    capture = capture if isinstance(capture, dict) else {}
    inputs = capture.get("input") or {}
    inputs = inputs if isinstance(inputs, dict) else {}
    tool = str(capture.get("tool_name") or "")
    action = str(row.get("action") or "")
    result = str(row.get("result") or "")
    status = capture.get("status")
    if status not in {"completed", "failed", "timeout"}:
        status = "timeout" if action.endswith(" timeout") or result.startswith("timeout") else (
            "failed" if action.endswith(" failed") or result.startswith("failed") else "completed"
        )
    files: list[str] = []
    for name in ("file_path", "filePath", "path", "filename"):
        value = inputs.get(name)
        if isinstance(value, str) and value and value not in files:
            files.append(value[:2048])
    edits = inputs.get("edits")
    if isinstance(edits, list):
        for edit in edits[:50]:
            if isinstance(edit, dict):
                path = edit.get("file_path") or edit.get("path")
                if isinstance(path, str) and path not in files:
                    files.append(path[:2048])
    command = inputs.get("command") or inputs.get("cmd") or inputs.get("patch") or ""
    if isinstance(command, str):
        for path in re.findall(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", command, re.M)[:50]:
            if path not in files:
                files.append(path[:2048])
    else:
        command = ""
    written = _write_target(command)
    if written and written not in files:
        files.append(written)
    summary = capture.get("text") or inputs.get("description") or inputs.get("title") or inputs.get("query")
    if not summary and tool.lower() in {"apply_patch", "functions.apply_patch"} and files:
        summary = "更新文件 · " + ", ".join(files[:3])
    if not summary and command:
        summary = _command_label(command)
    if not summary and files:
        summary = f"{tool or '文件操作'} · {', '.join(files[:3])}"
    if not summary:
        summary = action or "已记录操作"
    change = bool(written) or tool.lower() in {"write", "edit", "multiedit", "apply_patch", "functions.apply_patch"} or bool(
        isinstance(command, str) and re.search(r"^\*\*\* (?:Add|Update|Delete) File:", command, re.M)
    )
    refs = row.get("source_refs") or []
    if isinstance(refs, str):
        try:
            refs = json.loads(refs)
        except ValueError:
            refs = []
    return {
        "id": row["id"], "version": row["version"],
        "occurred_at": row["occurred_at"], "received_at": row["received_at"],
        "agent": row["agent_id"], "session_id": str(capture.get("session_id") or ""),
        "host_hash": str(capture.get("host_hash") or ""),
        "kind": capture.get("kind") if capture.get("kind") in {"request", "summary"} else "tool",
        "text": str(capture.get("text") or "")[:4000],
        "tool": tool, "status": status, "summary": _short(summary),
        "files": files, "file_operation": "change" if change else "reference",
        "result": _short(result, 1500), "command": str(command)[:4000],
        "has_context": bool(capture), "source_refs": refs if isinstance(refs, list) else [],
    }


class ProjectActivity:
    """Read-only cross-project view for the authenticated operator UI."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection | None]:
        if not self.db_path.exists():
            yield None
            return
        conn = sqlite3.connect(self.db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='source_events'").fetchone():
                yield None
            else:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _base(conn: sqlite3.Connection) -> str:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(source_events)")}
        capture = "e.capture" if "capture" in columns else "'{}'"
        return f"""WITH current_events AS (
            SELECT e.id, e.version, e.agent_id, e.occurred_at, e.received_at,
                   e.principal_workspace, e.principal_project, e.action, e.result,
                   e.source_refs, {capture} AS capture
            FROM source_events e
            WHERE e.classification = 'production' AND NOT EXISTS (
                SELECT 1 FROM source_events newer WHERE newer.id=e.id AND newer.version>e.version
            )
        ) """

    def projects(self) -> list[dict[str, Any]]:
        with self._db() as conn:
            if conn is None:
                return []
            rows = conn.execute(self._base(conn) + """, ranked AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY principal_workspace,principal_project
                    ORDER BY julianday(occurred_at) DESC,id DESC
                ) AS position FROM current_events
                ) SELECT principal_workspace AS workspace, principal_project AS project,
                       COUNT(*) AS event_count,
                       MAX(CASE WHEN position=1 THEN action END) AS latest_action,
                       MAX(CASE WHEN position=1 THEN result END) AS latest_result,
                       MAX(CASE WHEN position=1 THEN agent_id END) AS latest_agent,
                       MAX(CASE WHEN position=1 THEN capture END) AS latest_capture,
                       COUNT(DISTINCT agent_id) AS agent_count,
                       COUNT(DISTINCT CASE WHEN COALESCE(json_extract(capture,'$.session_id'),'')<>'' THEN json_array(json_extract(capture,'$.host_hash'),json_extract(capture,'$.session_id')) END) AS session_count,
                       SUM(CASE WHEN capture<>'{}' THEN 1 ELSE 0 END) AS context_count,
                       strftime('%Y-%m-%dT%H:%M:%SZ',MIN(julianday(occurred_at))) AS first_seen,
                       strftime('%Y-%m-%dT%H:%M:%SZ',MAX(julianday(occurred_at))) AS last_seen
                FROM ranked GROUP BY principal_workspace, principal_project
                ORDER BY MAX(julianday(occurred_at)) DESC, workspace, project
            """).fetchall()
            projects = []
            for row in rows:
                item = dict(row)
                item["key"] = project_key(item["workspace"], item["project"])
                latest = describe_event({
                    "id": "", "version": 1, "occurred_at": item["last_seen"],
                    "received_at": "", "agent_id": item.pop("latest_agent"),
                    "action": item.pop("latest_action"), "result": item.pop("latest_result"),
                    "capture": item.pop("latest_capture"),
                })
                item["latest"] = {k: latest[k] for k in ("agent", "summary", "kind", "status", "has_context")}
                projects.append(item)
            return projects

    def timeline(self, key: str, *, query: str = "", agent: str = "", status: str = "",
                 offset: int = 0, limit: int = 60) -> dict[str, Any] | None:
        project = next((p for p in self.projects() if p["key"] == key), None)
        if project is None:
            return None
        limit = min(100, max(1, limit))
        offset = max(0, offset)
        with self._db() as conn:
            if conn is None:
                return None
            where = " WHERE principal_workspace=? AND principal_project=?"
            params: list[Any] = [project["workspace"], project["project"]]
            # Session identity is scoped by project and host, never globally merged.
            if query:
                where += " AND instr(lower(COALESCE(action,'')||' '||COALESCE(result,'')||' '||capture),lower(?))>0"
                params.append(query)
            if agent:
                where += " AND agent_id=?"
                params.append(agent)
            if status:
                where += " AND COALESCE(json_extract(capture,'$.status'), CASE WHEN action LIKE '% timeout' OR result LIKE 'timeout%' THEN 'timeout' WHEN action LIKE '% failed' OR result LIKE 'failed%' THEN 'failed' ELSE 'completed' END)=?"
                params.append(status)
            base = self._base(conn)
            total = conn.execute(base + "SELECT COUNT(*) FROM current_events" + where, params).fetchone()[0]
            rows = conn.execute(base + "SELECT * FROM current_events" + where +
                                " ORDER BY julianday(occurred_at) DESC, id DESC LIMIT ? OFFSET ?",
                                [*params, limit, offset]).fetchall()
            agents = [r[0] for r in conn.execute(base + "SELECT DISTINCT agent_id FROM current_events WHERE principal_workspace=? AND principal_project=? ORDER BY agent_id", [project["workspace"], project["project"]])]
            highlights = {}
            for kind in ("request", "summary"):
                row = conn.execute(base + "SELECT * FROM current_events WHERE principal_workspace=? AND principal_project=? AND json_extract(capture,'$.kind')=? AND COALESCE(json_extract(capture,'$.text'),'')<>'' ORDER BY julianday(occurred_at) DESC,id DESC LIMIT 1",
                                   [project["workspace"], project["project"], kind]).fetchone()
                highlights[kind] = describe_event(dict(row)) if row else None
        return {"project": project, "highlights": highlights, "events": [describe_event(dict(r)) for r in rows],
                "agents": agents, "total": total, "offset": offset, "limit": limit,
                "has_more": offset + len(rows) < total}


def _time(value: object) -> str:
    text = str(value or "")
    return f'<time datetime="{_e(text)}" data-local-time>{_e(text.replace("T", " ").replace("Z", " UTC"))}</time>'


_CSS = """<style>
.activity{--ink-muted:var(--muted);--border:var(--line);--card:var(--panel);max-width:1180px;margin:0 auto;padding:0 0 40px;color:var(--ink)}
.activity a{color:inherit}.activity-head{display:flex;justify-content:space-between;gap:20px;align-items:start;margin-bottom:25px}.activity h1{font-size:32px;letter-spacing:-1px;margin:8px 0}.activity p{color:var(--ink-muted);line-height:1.7}.activity-kicker{font-size:12px;text-transform:uppercase;letter-spacing:2px;color:var(--ink-muted)}.activity-stat{font-size:28px;white-space:nowrap;padding:14px 0}.activity-stat small{font-size:12px;display:block;color:var(--ink-muted)}
.project-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,310px),1fr));gap:16px}.project-card{display:block;text-decoration:none;border:1px solid var(--border);border-radius:16px;padding:22px;background:var(--card);transition:transform .15s,border-color .15s}.project-card:hover{transform:translateY(-3px);border-color:#8b9ccb}.project-card h2{margin:7px 0 12px;font-size:23px;overflow-wrap:anywhere}.project-card>p{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.project-card .scope{font-size:12px;color:var(--ink-muted)}.project-facts{display:flex;gap:17px;flex-wrap:wrap;margin:20px 0 14px;font-size:13px}.project-last{font-size:12px;color:var(--ink-muted)}.activity-note{padding:12px 16px;border-left:3px solid #8b9ccb;background:var(--card);font-size:13px;margin:20px 0;line-height:1.7}.activity-filters{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0}.activity input,.activity select,.activity button,.activity-refresh{color:inherit;background:var(--card);border:1px solid var(--border);border-radius:8px;min-height:40px;padding:8px 12px;font:inherit}.activity input{flex:1;min-width:180px}.activity-refresh{text-decoration:none;font-size:13px;display:inline-block;white-space:nowrap}.session-block{margin:28px 0}.session-head{display:flex;gap:12px;flex-wrap:wrap;align-items:center;font-size:13px;margin-bottom:12px}.session-head code{font-size:11px;overflow-wrap:anywhere}.event-row{position:relative;border-left:2px solid var(--border);padding:0 0 22px 23px;margin-left:5px}.event-row:before{content:'';position:absolute;width:8px;height:8px;background:#8196cb;border-radius:50%;left:-5px;top:8px}.event-row.failed:before,.event-row.timeout:before{background:#d7a16e}.event-meta{display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:11px;color:var(--ink-muted)}.event-summary{font-size:15px;line-height:1.6;margin:7px 0;overflow-wrap:anywhere}.event-files{font-size:12px;line-height:1.8;overflow-wrap:anywhere}.event-files code{margin-right:10px}.event-row details{font-size:12px;margin-top:9px}.event-row summary{cursor:pointer;color:var(--ink-muted)}.event-row pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--card);padding:12px;border-radius:8px;line-height:1.6}.event-proof{display:block;font-size:11px;overflow-wrap:anywhere;margin-top:12px;color:var(--ink-muted)}.project-highlights{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:22px 0}.project-highlight{border:1px solid var(--border);border-radius:12px;padding:18px;min-width:0}.project-highlight h2{font-size:14px;margin-bottom:10px}.project-highlight p{font-size:13px;overflow-wrap:anywhere;white-space:pre-wrap}.project-highlight small{display:block;color:var(--ink-muted);font-size:11px;margin-top:12px}.activity-empty{padding:45px 20px;text-align:center;border:1px dashed var(--border);border-radius:14px}.activity-pages{display:flex;justify-content:space-between;gap:15px;margin-top:30px}.activity-pages a{padding:10px 16px;border:1px solid var(--border);border-radius:8px;text-decoration:none}@media(max-width:600px){.project-highlights{grid-template-columns:1fr}.activity-head{display:block}.activity h1{font-size:26px}.activity-stat{font-size:22px}.activity-filters select{flex:1}.activity{padding:20px 8px}.event-row{padding-left:16px}}
</style>"""
_JS = """document.querySelectorAll('[data-local-time]').forEach(function(el){var d=new Date(el.dateTime);if(!isNaN(d)){el.textContent=d.toLocaleString();el.title=el.dateTime;}});
var refresh=document.getElementById('activity-live');if(refresh)refresh.addEventListener('change',function(){if(this.checked){this.dataset.timer=setInterval(function(){if(!document.hidden&&!document.querySelector('details[open]'))location.reload();},30000);}else{clearInterval(Number(this.dataset.timer));}});"""


def _frame(body: str) -> str:
    return shell("工作记录", _CSS + '<div class="activity">' + body + '</div><script>' + _JS + '</script>', active="projects")


def projects_page(projects: list[dict[str, Any]], *, query: str = "") -> str:
    selected = [p for p in projects if query.casefold() in (p["project"] + " " + p["workspace"]).casefold()]
    cards = []
    for p in selected:
        cards.append(f'''<a class="project-card" href="/projects/{_e(p['key'])}"><span class="scope">{_e(p['workspace'])}</span><h2>{_e(p['project'])} →</h2>
        <div class="project-facts"><span>{p['event_count']:,} 条动态</span><span>{p['session_count']:,} 个已关联会话</span><span>{p['agent_count']} 个 Agent</span></div>
        <div class="project-last">最近活动 {_time(p['last_seen'])}</div><p>{_e(p['latest']['summary'])}</p><p>{p['context_count']:,} 条操作保留了会话或工具上下文</p></a>''')
    empty = '<div class="activity-empty">没有匹配的项目。项目会在收到第一条执行记录后出现。</div>'
    return _frame(f'''<header class="activity-head"><div><span class="activity-kicker">工作记录</span><h1>每个项目，正在发生什么。</h1><p>从实际操作追踪项目的发展过程，按项目回看会话、文件和问题。</p></div><div class="activity-stat">{len(projects)}<small>已采集项目 / 活动来源</small></div></header>
    <form class="activity-filters" method="get"><input aria-label="搜索项目" name="q" value="{_e(query)}" placeholder="搜索项目或工作区…"><button type="submit">搜索</button><a class="activity-refresh" href="/projects">刷新</a></form>
    <div class="activity-note">只展示真实采集记录。同名项目按工作区区分；工具完成表示一次操作结束。旧记录可能缺少会话和文件细节。</div><div class="project-grid">{''.join(cards) or empty}</div>''')


def project_page(data: dict[str, Any], *, query: str = "", agent: str = "", status: str = "") -> str:
    p = data["project"]
    # Keep chronological segments intact: an interleaved session may have multiple segments.
    blocks: list[tuple[tuple[str, str], list[dict[str, Any]]]] = []
    for event in data["events"]:
        identity = (event["host_hash"], event["session_id"] or event["occurred_at"][:10])
        if not blocks or blocks[-1][0] != identity:
            blocks.append((identity, []))
        blocks[-1][1].append(event)
    sections = []
    for (_, session), events in blocks:
        label = f'会话 <code>{_e(session)}</code>' if events[0]["session_id"] else f'{_e(session)} · 历史记录未关联会话'
        rows = []
        for ev in events:
            badge = {"request": "用户请求", "summary": "Agent 会话小结"}.get(ev["kind"]) or {"completed": "操作完成", "failed": "工具报错", "timeout": "操作超时"}[ev["status"]]
            files = "".join(f'<code>{_e(path)}</code>' for path in ev["files"])
            files = f'<div class="event-files">{"写入 / 编辑目标" if ev["file_operation"] == "change" else "涉及文件"}：{files}</div>' if files else ""
            context_note = "" if ev["has_context"] else '<span>旧记录 · 细节未采集</span>'
            rows.append(f'''<article class="event-row {_e(ev['status'])}"><div class="event-meta">{_time(ev['occurred_at'])}<span>{_e(ev['agent'])}</span><span>{_e(ev['tool'])}</span><span>{badge}</span>{context_note}</div>
            <div class="event-summary">{_e(ev['summary'])}</div>{files}<details><summary>查看操作证据</summary><pre>{_e(ev['text'] or ev['command'] or ev['summary'])}</pre><pre>{_e(ev['result'] or '未提供结果正文')}</pre><code class="event-proof">event:{_e(ev['id'])} · revision:{ev['version']} · received:{_e(ev['received_at'])}</code></details></article>''')
        sections.append(f'<section class="session-block"><div class="session-head">{label}<span>{len(events)} 条操作</span></div>{"".join(rows)}</section>')
    agent_options = ''.join(f'<option value="{_e(a)}" {"selected" if a == agent else ""}>{_e(a)}</option>' for a in data["agents"])
    status_options = ''.join(f'<option value="{s}" {"selected" if s == status else ""}>{label}</option>' for s, label in (("completed", "操作完成"), ("failed", "工具报错"), ("timeout", "超时")))
    def page_link(offset: int, label: str) -> str:
        qs = urlencode({"q": query, "agent": agent, "status": status, "offset": offset})
        return f'<a href="/projects/{p["key"]}?{_e(qs)}">{label}</a>'
    pagination = (page_link(max(0, data["offset"] - data["limit"]), "← 较新记录") if data["offset"] else '<span></span>')
    if data["has_more"]:
        pagination += page_link(data["offset"] + data["limit"], "较早记录 →")
    feed = ''.join(sections) or '<div class="activity-empty">当前筛选下没有操作记录。</div>'
    highlights = []
    for kind, label, empty in (("request", "最近的工作目标", "尚未收到请求正文。客户端加载新版 hooks 后，从后续请求开始记录。"),
                                ("summary", "最近的会话小结", "尚未收到小结正文。Agent 在结束时提供的小结会显示在这里。")):
        item = data.get("highlights", {}).get(kind)
        content = _e(item["text"]) if item else empty
        proof = f'<small>{_e(item["agent"])} · {_time(item["occurred_at"])} · event:{_e(item["id"])}</small>' if item else ""
        highlights.append(f'<section class="project-highlight"><h2>{label}</h2><p>{content}</p>{proof}</section>')
    overview = '<div class="project-highlights">' + ''.join(highlights) + '</div>'
    return _frame(f'''<a href="/projects">← 全部项目</a><header class="activity-head"><div><p class="activity-kicker">{_e(p['workspace'])} · Project history</p><h1>{_e(p['project'])}</h1><p>最近活动 {_time(p['last_seen'])} · {p['session_count']} 个已关联会话 · {p['agent_count']} 个 Agent</p></div><div class="activity-stat">{p['event_count']:,}<small>真实动态记录</small></div></header>
    <div class="activity-note">按时间记录用户请求、Agent 提供的小结和实际操作。小结是 Agent 的陈述，完成状态仍以操作证据为准；旧版采集没有请求和小结正文。{p['event_count'] - p['context_count']:,} 条历史记录缺少工具上下文。</div>
    {overview}<form class="activity-filters" method="get"><input aria-label="搜索项目记录" name="q" value="{_e(query)}" placeholder="搜索操作、文件、报错或会话…"><select aria-label="Agent" name="agent"><option value="">全部 Agent</option>{agent_options}</select><select aria-label="操作状态" name="status"><option value="">全部状态</option>{status_options}</select><button type="submit">筛选</button></form>
    <p>{data['total']:,} 条匹配记录 · 每页 {data['limit']} 条　<label><input style="min-height:auto;min-width:auto" type="checkbox" id="activity-live"> 每 30 秒刷新</label></p>{feed}<nav class="activity-pages" aria-label="时间线分页">{pagination}</nav>''')
