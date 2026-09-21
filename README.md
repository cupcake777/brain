<div align="center">

# 🧠 Brain

**The self-evolving memory layer for AI agents**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.122+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

*Agents forget. Brain remembers — then improves what it remembers.*

</div>

---

## Connect your agent in minutes

Brain ships both a native Hermes plugin (Hermes Agent `>=0.21.1`) and a portable [Agent Skill](skills/brain-loop/SKILL.md). The plugin is the recommended Hermes install because it registers automatic, sanitized tool-event hooks and bundles the skill:

```bash
hermes plugins install cupcake777/brain --enable
hermes gateway restart
```

The installer asks for your operator-owned `BRAIN_URL` and scoped `BRAIN_TOKEN`; this repository contains neither. After restart, the plugin records durable tool events automatically and exposes `brain:brain-loop` for the full **retrieve → verify → outcome → evidence-backed proposal → curation → export** loop.

For hosts that can load skills but cannot run Hermes plugins, install the instruction/client package only:

```bash
hermes skills install https://YOUR-BRAIN-HOST/skills/brain-loop/SKILL.md
```

Skill-only installation does **not** register executable hooks. Configure `BRAIN_URL` and securely provide your service's `BRAIN_TOKEN`. See [agent installation and verification](docs/agent-install.md) for setup, security boundaries and cross-agent instructions.

## The Problem

Every AI session starts from zero. Your agents re-learn the same lessons, repeat the same mistakes, and lose the context you spent hours building. Context windows get bigger, but **bigger windows don't fix bad structure** — they just waste more tokens reading noise.

Existing solutions fall into two camps, both incomplete:

| Approach | What it does | What it misses |
|----------|-------------|----------------|
| **Static files** (CLAUDE.md, AGENTS.md) | Human writes rules, agents read them | No learning. No dedup. Rules rot. |
| **Memory plugins** (mem0, honcho) | Auto-capture conversation snippets | No curation. No lifecycle. Noise accumulates. |

**Brain is the missing middle** — a pipeline that captures knowledge automatically, curates it through a lifecycle, and compiles it into context your agents actually consume.

## How It Works

```
                    ┌─────────────────────────────────┐
                    │          Any AI Agent            │
                    │  (Claude · Codex · Hermes · …)  │
                    └──────────────┬──────────────────┘
                                   │ learns something
                                   ▼
                    ┌─────────────────────────────────┐
                    │         📥 Proposal              │
                    │  "I discovered that X causes Y"  │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │      🧬 Lifecycle Pipeline       │
                    │                                  │
                    │  draft → refined → canonized     │
                    │    │        │          │         │
                    │    ▼        ▼          ▼         │
                    │  embed   dedup      export       │
                    │  detect  reflect    compile      │
                    │  link    merge      inject       │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │       📤 Compiled Context        │
                    │                                  │
                    │  global.md · CLAUDE.md · per-    │
                    │  project exports · system prompt │
                    └──────────────┬──────────────────┘
                                   │ consumed by
                                   ▼
                    ┌─────────────────────────────────┐
                    │          Any AI Agent            │
                    │      (next session, smarter)     │
                    └─────────────────────────────────┘
```

**The loop closes.** Agents propose knowledge → Brain curates it → agents consume it → they propose better knowledge. Each cycle, the system gets smarter.

## What Makes This Different

### 🔄 Proposal Lifecycle (not just "save and forget")

Knowledge has a lifecycle. A raw observation isn't the same as a battle-tested rule.

```
  ┌─────────┐    ┌──────────┐    ┌───────────┐    ┌────────────┐
  │  draft   │───▶│ refined  │───▶│ canonized │───▶│ deprecated │
  └─────────┘    └──────────┘    └───────────┘    └────────────┘
   (new idea)    (validated)     (trusted rule)    (superseded)
```

- **Draft**: Raw proposal from an agent. Untouched.
- **Refined**: Reviewed, reworded, validated against existing knowledge.
- **Canonized**: Exported to agents as trusted context.
- **Deprecated**: Superseded by newer, better knowledge. Kept for history.

### 🪞 Reflection Engine (finds what you didn't know you knew)

A semantic deduplication engine that doesn't just catch duplicates — it discovers **connections**:

- **60-char prefix matching** for fast exact dedup
- **Embedding similarity** for semantic overlap ("X causes Y" ≈ "Y is caused by X")
- **Auto-linking** related rules across categories
- **Contradiction detection** — flags when new knowledge conflicts with existing canon

### 📤 Export Compiler (context your agents actually read)

Approved proposals don't sit in a database. They compile into files agents consume as system instructions:

| Export | What it contains |
|--------|-----------------|
| `global.md` | Universal rules across all projects |
| `CLAUDE.md` | Per-project rules (auto-injected by Claude Code) |
| `AGENTS.md` | Codex/Aider compatible format |
| Custom | Any template, any format |

The compiler deduplicates, categorizes, and formats — so agents read a clean 2KB file, not a 50KB database dump.

### 🌐 Agent-Agnostic by Design

Brain doesn't care which agent you use. The interface is the **filesystem**:

1. Any agent writes a `.md` file to the inbox
2. Brain processes it through the pipeline
3. Any agent reads the compiled exports

Works with Claude Code, Codex, Hermes, Cursor, custom agents — anything that can read a file.

## Features

| Feature | Description |
|---------|-------------|
| 🔄 **Proposal Pipeline** | 3-layer funnel: inbox → review → approved/rejected with semantic dedup |
| 🧬 **Lifecycle Stages** | draft → refined → canonized → deprecated with automated transitions |
| 🪞 **Reflection Engine** | Semantic deduplication, auto-linking, contradiction detection |
| 📤 **Export Compiler** | Approved items compile to `global.md` + per-project `CLAUDE.md` |
| 🌐 **Web Dashboard** | Dark theme, mobile-first review UI with knowledge tree visualization |
| 🧹 **Eviction** | Stale detection, budget caps, automatic proposal demotion |
| 🔗 **Cross-Session Context** | Injects conversation summaries into new sessions |
| 📡 **Notifications** | Event-driven alerts for ingest, review, eviction |
| 🔒 **Auth + CSRF** | Bearer token auth, CSRF protection, DB-fail-closed |
| 🔀 **Filesystem Sync** | Multi-device proposal sync — write a file, Brain picks it up |

## Quick Start

```bash
# Install
pip install -e .

# Launch the web server
python -m hermes serve --host 0.0.0.0 --port 8083

# Or with auth
HERMES_AUTH_TOKEN=mysecret python -m hermes serve --port 8083
```

Then open `http://localhost:8083` — the dashboard walks you through the rest.

### CLI Commands

```bash
# Scan inbox for new proposals
python -m hermes scan

# Rebuild exports from approved items
python -m hermes rebuild-exports

# Run eviction (enforce budget caps)
python -m hermes evict

# Start long-running watcher (auto-processes new proposals)
python -m hermes watch
```

## Architecture

```
brain/
├── hermes/                    # Core package
│   ├── app.py                # FastAPI server + all routes
│   ├── templates.py          # Web UI (dark theme, mobile-first)
│   ├── reflect.py            # Reflection & dedup engine
│   ├── proposals.py          # Proposal CRUD + bare MD parsing
│   ├── repository.py         # SQLite data layer
│   ├── exporter.py           # Export compiler
│   ├── ingest.py             # Inbox scanner + dedup
│   ├── integrate.py          # Lifecycle stage transitions
│   ├── selflearn.py          # Self-learning loop
│   ├── eviction.py           # Stale detection & budget caps
│   ├── notifier.py           # Notification system
│   ├── cross_session_context.py  # Cross-session injection
│   ├── auth.py               # Auth middleware
│   └── cli.py                # CLI commands
├── scripts/                  # Utility scripts
├── tests/                    # Test suite
└── docs/                     # Architecture docs
```

## Web Routes

| Route | Purpose |
|-------|---------|
| `/knowledge` | Knowledge tree — browse by lifecycle stage and category |
| `/knowledge/{id}` | Node detail — history, links, related entries |
| `/review` | Review queue with state filters |
| `/review/{id}` | Proposal detail with approve / reject actions |
| `/dashboard` | Overview: proposal counts, export status, health |
| `/exports/global/global.md` | Global export (public) |
| `/health` | Health check (public) |

## Configuration

All configuration via environment variables:

| Env var | Default | Purpose |
|---------|---------|---------|
| `HERMES_SYNC_ROOT` | `~/hermes-sync` | Root directory for sync data |
| `HERMES_AUTH_TOKEN` | (none) | Bearer token for API auth |
| `HERMES_CSRF_SECRET` | (none) | CSRF protection secret |
| `BRAIN_DEDUP_SPACE` | (none) | HuggingFace Space for remote embedding dedup |
| `BRAIN_DISABLE_EMBEDDINGS` | (none) | Disable local embeddings (use remote) |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full reference.

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

## How It Compares

| | Static files | Memory plugins | **Brain** |
|---|:---:|:---:|:---:|
| Auto-capture knowledge | ❌ | ✅ | ✅ |
| Lifecycle management | ❌ | ❌ | ✅ |
| Semantic dedup | ❌ | ❌ | ✅ |
| Contradiction detection | ❌ | ❌ | ✅ |
| Curated exports | Manual | ❌ | ✅ |
| Multi-agent support | ❌ | Varies | ✅ |
| Web dashboard | ❌ | Varies | ✅ |
| Agent-agnostic | ❌ | ❌ | ✅ |

## Testing

```bash
pytest -q
```

## License

MIT
