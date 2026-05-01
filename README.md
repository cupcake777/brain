# Brain

Multi-agent shared memory pipeline with proposal-based learning, reflection, and cross-session context injection.

## What It Does

Brain is the memory backbone for a multi-AIGent workflow. It provides:

- **Proposal System** — Agents submit knowledge/rules as Markdown proposals (with YAML front-matter or bare MD), which flow through a 3-layer funnel: inbox → review → approved/rejected
- **Reflect Engine** — Periodic reflection on accumulated proposals, deduplication (60-char prefix matching), semantic linking, and automatic rule generation
- **Export Compiler** — Approved proposals compile into `global.md` and project-specific `CLAUDE.md` exports that agents consume as context
- **Review Web UI** — Mobile-first dark-theme dashboard at `/dashboard`, `/review`, `/pools` with filter/collapse state persistence
- **Eviction** — Stale proposal detection, soft/hard budget cap enforcement, automatic demotion
- **Cross-Session Context** — `cross_session_context.py` extracts recent conversation summaries from Hermes state.db and injects them into new sessions via `prefill_messages_file`

## Architecture

```
Agent (Telegram/CLI/Web)
  ↓ proposal.md (via Syncthing or API)
Inbox → Reflect → Review Queue → Approved
  ↓                              ↓
Dedup & Link              Export Compiler
                              ↓
                    global.md / CLAUDE.md
                              ↓
                   Agent reads as context
```

**Data flow:** Proposals land in `sync/inbox/` → get ingested into SQLite → reflected/deduped → queued for review → approved items compiled into export Markdown → agents pick up exports as context files.

**Syncthing integration:** The `sync/` directory is shared across devices (VPS, Mac, Windows WSL) via Syncthing, enabling any agent on any device to submit proposals that flow to the central Brain.

## Layout

```
brain/
├── hermes/               # Core Python package
│   ├── app.py            # FastAPI web server + routes
│   ├── templates.py      # HTML templates (dark theme)
│   ├── reflect.py        # Reflection & dedup engine
│   ├── proposals.py      # Proposal CRUD + bare MD parsing
│   ├── repository.py     # SQLite data layer
│   ├── exporter.py       # Export compilation (global.md, CLAUDE.md)
│   ├── ingest.py         # Inbox scanner + replay dedup
│   ├── selflearn.py      # Self-learning loop
│   ├── eviction.py       # Stale detection & budget enforcement
│   ├── notifier.py       # Telegram notifications
│   ├── cross_session_context.py  # Cross-session summary injection
│   ├── auth.py           # Bearer token + CSRF
│   ├── cli.py            # CLI entrypoints (scan, serve, evict, watch)
│   ├── config.py         # Configuration
│   └── runtime.py        # Polling runtime
├── scripts/              # Utility scripts
│   ├── brain-sync        # Syncthing sync helper
│   └── proposal_monitor.py
├── tests/                # Test suite
├── docs/                 # Architecture docs
├── exports/              # Compiled output (gitignored)
├── inbox/                # Raw proposals (gitignored)
├── review/               # Review queue (gitignored)
└── state/                # Runtime status (gitignored)
```

## Quick Start

```bash
# Install
pip install -e .

# One-shot inbox scan
python -m hermes --sync-root ./sync scan

# Rebuild exports from approved items
python -m hermes --sync-root ./sync rebuild-exports

# Run export eviction
python -m hermes --sync-root ./sync evict

# Long-running watcher
python -m hermes --sync-root ./sync watch

# Start web server (no auth)
python -m hermes --sync-root ./sync serve --host 0.0.0.0 --port 8083

# With auth + TLS
HERMES_AUTH_TOKEN=secret python -m hermes --sync-root ./sync serve \
  --host 0.0.0.0 --port 8443 \
  --tls-cert /etc/ssl/hermes.crt --tls-key /etc/ssl/hermes.key
```

## Configuration

| Env var | CLI flag | Purpose |
|---------|----------|---------|
| `HERMES_AUTH_TOKEN` | `--auth-token` | Bearer token (unset = no auth) |
| `HERMES_CSRF_SECRET` | `--csrf-secret` | CSRF token secret |
| `HERMES_TLS_CERT` | `--tls-cert` | TLS certificate PEM |
| `HERMES_TLS_KEY` | `--tls-key` | TLS private key PEM |
| `HERMES_TELEGRAM_BOT_TOKEN` | — | Telegram bot token |
| `HERMES_TELEGRAM_CHAT_ID` | — | Telegram chat ID |

## Web Routes

| Route | Purpose |
|-------|---------|
| `/dashboard` | Status overview with counts and export info |
| `/review` | Review queue (filter by state, mobile-friendly) |
| `/review/{id}` | Proposal detail with approve/reject buttons |
| `/pools` | Pools view with collapsible categories |
| `/exports/global/global.md` | Global export (public) |
| `/exports/projects/{key}.md` | Per-project export (public) |
| `/health` | Health check (public) |

## Test

```bash
pytest -q
```

## License

MIT