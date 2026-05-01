<div align="center">

# 🧠 Brain

**Multi-agent shared memory with proposal-based learning**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.122+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

*A memory pipeline that learns, reflects, and evolves across any AI agent.*

</div>

---

## Why Brain?

AI agents forget. Every session starts from scratch. Brain fixes this by giving your agents a **shared, persistent memory system** that:

- **Learns from experience** — agents submit knowledge as proposals, which flow through a review pipeline
- **Reflects and deduplicates** — a reflection engine finds semantic overlaps, links related rules, and prunes stale knowledge
- **Compiles to context** — approved proposals export as Markdown that agents consume as system instructions
- **Works across agents** — any LLM agent (Claude, Codex, Hermes, custom) can read/write via Syncthing or API

Think of it as a **git-like workflow for agent memory**: propose → review → merge → export.

## Architecture

```
  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
  │  Telegram    │    │  Claude     │    │   Codex     │
  │   Agent      │    │   Code      │    │   Agent     │
  └──────┬───────┘    └──────┬──────┘    └──────┬───────┘
         │                    │                    │
         ▼                    ▼                    ▼
  ┌──────────────────────────────────────────────────────┐
  │                   Syncthing Bus                      │
  │              (proposal.md files)                     │
  └──────────────────────────┬───────────────────────────┘
                             │
                             ▼
  ┌──────────────────────────────────────────────────────┐
  │                     Brain                             │
  │  ┌─────────┐  ┌──────────┐  ┌─────────┐             │
  │  │  Inbox   │→│  Reflect  │→│ Review  │             │
  │  └─────────┘  └──────────┘  └────┬────┘             │
  │                                   │                  │
  │                              ┌────▼────┐             │
  │                              │ Approved│             │
  │                              └────┬────┘             │
  │                                   │                  │
  │                    ┌──────────────▼───────────────┐   │
  │                    │     Export Compiler          │   │
  │                    │  global.md / CLAUDE.md / *   │   │
  │                    └──────────────────────────────┘   │
  └──────────────────────────┬───────────────────────────┘
                             │
                     ┌───────▼────────┐
                     │  Agent reads    │
                     │  as context      │
                     └─────────────────┘
```

## Key Features

| Feature | Description |
|---------|-------------|
| 🔄 **Proposal Pipeline** | 3-layer funnel: inbox → review → approved/rejected with dedup |
| 🪞 **Reflection Engine** | Semantic deduplication, 60-char prefix matching, auto-rule generation |
| 📤 **Export Compiler** | Approved items compile to `global.md` + project-specific `CLAUDE.md` |
| 🌐 **Web Dashboard** | Dark theme, mobile-first review UI at `/dashboard` and `/pools` |
| 🧹 **Eviction** | Stale detection, budget caps, automatic proposal demotion |
| 🔗 **Cross-Session Context** | Injects conversation summaries from agent state DB into new sessions |
| 📡 **Telegram Notifications** | Event-driven alerts for ingest, review, eviction |
| 🔒 **Auth + CSRF** | Bearer token auth, CSRF protection, DB-fail-closed (503 on errors) |
| 🔀 **Syncthing Integration** | Multi-device proposal sync — write a `.md` file, Brain picks it up |

## Quick Start

```bash
# Install
pip install -e .

# Scan inbox for new proposals
python -m hermes --sync-root ./sync scan

# Rebuild exports from approved items
python -m hermes --sync-root ./sync rebuild-exports

# Run eviction (enforce budget caps)
python -m hermes --sync-root ./sync evict

# Start long-running watcher
python -m hermes --sync-root ./sync watch

# Launch the web server
python -m hermes --sync-root ./sync serve --host 0.0.0.0 --port 8083

# With auth + TLS
HERMES_AUTH_TOKEN=mysecret python -m hermes --sync-root ./sync serve \
  --host 0.0.0.0 --port 8443 \
  --tls-cert /etc/ssl/hermes.crt --tls-key /etc/ssl/hermes.key
```

## Proposal Format

Proposals are Markdown files with optional YAML front-matter:

```markdown
---
title: Prefer structure over prose
category: style
risk: low
---

### Rule: Use tables, not walls of text

**Always** format comparisons as tables.
**Never** dump unstructured text when a list or table works.
```

Bare Markdown (no front-matter) is also supported — Brain auto-extracts the title and infers category/risk.

## Web Routes

| Route | Purpose |
|-------|---------|
| `/dashboard` | Overview: proposal counts, export status, health |
| `/review` | Review queue with state filters (pending / approved / rejected) |
| `/review/{id}` | Proposal detail with approve / reject actions |
| `/pools` | Collapsible category view |
| `/exports/global/global.md` | Global export (public) |
| `/exports/projects/{key}.md` | Per-project export (public) |
| `/health` | Health check (public) |

## Configuration

All configuration via environment variables or CLI flags:

| Env var | CLI flag | Default | Purpose |
|---------|---------|---------|---------|
| `HERMES_SYNC_ROOT` | `--sync-root` | `~/hermes-sync` | Root directory for sync data |
| `HERMES_AUTH_TOKEN` | `--auth-token` | (none) | Bearer token for API auth |
| `HERMES_CSRF_SECRET` | `--csrf-secret` | (none) | CSRF protection secret |
| `BRAIN_XUI_URL` | — | (none) | X-UI panel URL (optional) |
| `BRAIN_PROXY_HOST` | — | (none) | SSH host for security data (optional) |

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for full env var reference.

## How It Works With Agents

Brain is agent-agnostic — it uses the filesystem as the interface:

1. **Any agent** writes a proposal to `sync/inbox/proposals/`
2. **Brain** scans, deduplicates, and queues it for review
3. **You** approve or reject via the web dashboard
4. **Brain** compiles approved proposals into `global.md` and `CLAUDE.md`
5. **Agents** read these exports as context instructions

Syncthing keeps `sync/` directories identical across all your devices — VPS, laptop, phone — so any agent anywhere can participate.

## Testing

```bash
pytest -q
```

## Project Structure

```
brain/
├── hermes/                    # Core package
│   ├── app.py                # FastAPI server + all routes
│   ├── templates.py          # HTML templates (dark theme)
│   ├── reflect.py            # Reflection & dedup engine
│   ├── proposals.py          # Proposal CRUD + bare MD parsing
│   ├── repository.py         # SQLite data layer
│   ├── exporter.py           # Export compilation
│   ├── ingest.py             # Inbox scanner + dedup
│   ├── selflearn.py          # Self-learning loop
│   ├── eviction.py           # Stale detection & caps
│   ├── notifier.py           # Telegram notifications
│   ├── cross_session_context.py  # Cross-session injection
│   ├── auth.py               # Auth middleware
│   └── cli.py                # CLI commands
├── scripts/                  # Utility scripts
├── tests/                    # Test suite
├── docs/                     # Architecture docs
└── exports/                  # Compiled output (gitignored)
```

## License

MIT