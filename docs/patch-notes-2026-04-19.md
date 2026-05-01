# Hermes Brain MVP — Patch Notes (2026-04-19)

## New: Self-Reflection Engine (`hermes/reflect.py`)
- cron job `hermes-brain-self-reflect` runs every 6 hours
- Produces low-risk (auto-approve) and medium/high-risk (pending) proposals
- After writing proposals, triggers `hermes scan` to ingest immediately
- Usage: `python3 /root/management/Brain/hermes/reflect.py --mode all`

## Fix: Telegram HTML Escaping (notifier.py)
- Proposal summaries containing `<uuid>` or other HTML-like text caused 400 errors
- `send()` now does `html.escape(text)` then restores safe tags (`<b>`, `<code>`, etc.)
- This fixed 3 stuck proposals that were in inbox but not ingested

## New: brain-sync apply now projects agent instructions
- `apply_agent_instructions()` added to brain-sync script
- Projects `exports/global/codex-instructions.md` → `~/.codex/instructions.md`
- Projects `exports/global/memory-header.md` → `~/.codex/memories/MEMORY.md` (preserving user content below markers)
- Both source files are in `exports/global/` and sync via Syncthing to Mac

## New: Export source files for agent projection
- `exports/global/codex-instructions.md` — full instructions telling Codex it CAN write durable memory via `brain-sync propose`
- `exports/global/memory-header.md` — Brain-managed section for MEMORY.md with authority hierarchy

## Complete Memory Loop
```
Agent learns → brain-sync propose → Syncthing → VPS ingest
  → low-risk: auto-approve → export → Syncthing back
  → high-risk: pending → Telegram notifies user → Web review → export
  → brain-sync apply → rules projected to ~/.claude/ + ~/.codex/
  → Agent reads updated rules on next session start
  → Hermes reflect.py (every 6h) → auto-writes proposals from accumulated knowledge
```

## Key Commands
- `brain-sync apply` — project all exports to agent directories (CLAUDE.md, skills, rules, instructions, MEMORY.md header)
- `brain-sync propose --agent codex --summary "..." --observation "..." --why "..." --memory "..." --category rule --risk medium` — write a proposal
- `python3 -m hermes --sync-root /root/hermes-sync scan` — force ingest all inbox proposals
- `systemctl restart hermes-serve hermes-watch` — restart after code changes