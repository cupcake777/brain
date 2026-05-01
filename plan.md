# Hermes Brain MVP Plan

## 已完成

### 1. 核心架构骨架已落地

- 已创建 `hermes/` Python package，形成可运行的 Hermes MVP。
- 已实现本地 proposal 原子写入：`.tmp-<uuid>.md -> fsync -> rename`。
- 已实现 `project_key` 解析规则：`.hermes-project` / git remote hash / cwd fallback / `global`

### 2. 数据层与处理链路已打通

- SQLite-backed Hermes repository（proposals + exports 表）
- Proposal ingest: front matter 解析 / replay dedup / semantic duplicate linking / 风险分流
- Review state 流转: pending / approved_db_only / approved_for_export / rejected / superseded

### 3. 导出与状态发布已可用

- Project / global export snapshot + supersede-collapse
- `state/status.md` 发布: queue state counts / export records / health summary

### 4. 服务运行面已具备

- FastAPI review API + mobile-first dark-theme HTML UI
- CLI: scan / rebuild-exports / watch / serve / evict

### 5. 工程化基础已补齐

- pyproject.toml / .gitignore / README / tests (44 passing)

### 6. Production 级特性已实现

- **Auth/TLS**: Bearer token auth middleware (public /health + /exports/*), CSRF middleware (same-origin + X-CSRF-Token), DB-fail-closed (503 on sqlite3 errors), TLS termination via uvicorn
- **Telegram notifier**: TelegramNotifier (urllib, no extra deps), NotificationRouter fire-and-forget, 6 event templates (pending_new / auto_approved / duplicate_detected / health_alert / export_rebuilt / eviction_performed)
- **Mobile review UI**: Dark dracula theme, responsive single-column, card-based queue with filter tabs, proposal detail with action buttons (approve/reject), /dashboard page, touch-friendly 44px+ targets
- **Export eviction**: EvictionService with stale detection (soft 72h / hard 14d), hard-stale file deletion + DB record removal, proposal demotion (approved_for_export → approved_db_only) by retrieval_count + age, soft cap warning in export files

## 验证结果

```bash
pytest -q  -> 44 passed
py_compile -> success
```

## 下一步可选方向

- Audit log (reviewer / timestamp / before-after state)
- Syncthing filesystem event watcher (inotify/fswatch, replace polling)
- Connection pooling for SQLite (WAL mode, single writer)
- Structured logging
- Real Syncthing directory end-to-end integration test
