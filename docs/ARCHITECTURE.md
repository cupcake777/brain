# Architecture

## Data Flow

```
Agent (Telegram / CLI / Web / Codex / Claude)
  ↓ proposal.md (via Syncthing or API)
Inbox → Ingest (dedup) → Reflect (semantic link) → Review Queue
  ↓ approved                                       ↓ rejected
Export Compiler                               marked or deleted
  ↓
global.md / CLAUDE.md / project exports
  ↓
Agents consume as context (prefill, CLAUDE.md, skills)
```

## Module Responsibilities

| Module | Role |
|--------|------|
| `app.py` | FastAPI routes, dashboard, review UI, gallery, security board |
| `templates.py` | All HTML templates (dark theme, mobile-first) |
| `reflect.py` | Reflection engine: dedup, semantic linking, rule generation |
| `proposals.py` | Proposal CRUD + bare MD auto-parsing with front-matter fallback |
| `repository.py` | SQLite data layer (proposals, exports tables) |
| `exporter.py` | Compile approved items into global.md, CLAUDE.md, per-project exports |
| `ingest.py` | Inbox scanner with replay dedup and semantic duplicate detection |
| `selflearn.py` | Self-learning loop: web research, proposal generation |
| `eviction.py` | Stale detection, budget cap enforcement, proposal demotion |
| `notifier.py` | Telegram notifications for ingest/review/eviction events |
| `cross_session_context.py` | Extract conversation summaries from agent state DB, inject into new sessions |
| `auth.py` | Bearer token + CSRF protection |
| `cli.py` | CLI commands: `scan`, `serve`, `watch`, `evict`, `rebuild-exports` |
| `config.py` | Configuration dataclass |
| `runtime.py` | Polling runtime for VPS-side background ingestion |

## State Machine

```
pending → approved_db_only → approved_for_export → superseded
   ↓              ↓
rejected        rejected
```

Proposals flow through a 3-layer funnel:
1. **Inbox**: Raw proposals land via Syncthing or API
2. **Review**: Human approval required for export
3. **Approved**: Compiled into agent-consumable exports

## Configuration

All paths are configurable via environment variables with sensible defaults:

| Env var | Default | Purpose |
|---------|---------|---------|
| `HERMES_SYNC_ROOT` | `~/hermes-sync` | Root directory for sync data |
| `HERMES_DB_PATH` | `$SYNC_ROOT/hermes.sqlite3` | SQLite database path |
| `HERMES_HOME` | `~/.hermes` | Hermes agent home directory |
| `BRAIN_DATA_DIR` | `./data` | Brain data directory |
| `BRAIN_PLOTTING_DIR` | (empty) | Plotting gallery static files |
| `BRAIN_XUI_URL` | (empty) | X-UI panel URL (optional) |
| `BRAIN_XUI_USER` | (empty) | X-UI panel username (optional) |
| `BRAIN_XUI_PASS` | (empty) | X-UI panel password (optional) |
| `BRAIN_PROXY_HOST` | (empty) | SSH host for security data (optional) |
| `BRAIN_SSH_KEY` | `~/.ssh/id_rsa` | SSH key path (optional) |
| `BRAIN_SSH_PORT` | `22` | SSH port (optional) |
| `QUOTA_API_BASE` | (empty) | Quota API base URL (optional) |
| `QUOTA_API_KEY` | (empty) | Quota API key (optional) |