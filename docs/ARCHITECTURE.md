# Hermes Brain Architecture

## brain/rules/ vs Hermes export — structural separation

These two rule delivery paths serve **different concerns** and must not overlap:

| Path | What it delivers | Format | Consumer | Deployment |
|------|-------------------|--------|----------|------------|
| `brain/rules/` | Command approval policies | Codex `prefix_rule()` | Codex shell sandbox | `brain-sync --apply` → `~/.codex/rules/` |
| `brain/skills/` | Tool skill packages | SKILL.md + references/ | Codex & Claude | `brain-sync --apply` → `~/.claude/skills/`, `~/.codex/skills/` |
| Hermes export `global.md` | Natural language behavioral rules | Markdown bullets | Human audit | Syncthing → stays in `exports/` |
| Hermes export `CLAUDE.md` | Imperative agent instructions | Markdown with keyword markers | Claude Code / Codex / Hermes | Syncthing → `brain-sync --apply` → `~/.claude/CLAUDE.md` |

**Rule**: `brain/rules/` only contains Codex `prefix_rule()` command approvals. Natural language behavioral rules belong exclusively in Hermes proposals → export. No overlap.

## CLAUDE.md Export

CLAUDE.md format specification: `/root/knowledge/hermes-claude-md-spec.md`

Key design:
- Each proposal gets a `### category: slug` heading
- Multi-assertion bullets decomposed with `**Always**`/`**Never**`/`**Prefer**`/`**Avoid**`/`**If**` keywords
- No rationale in agent-facing output — instructions only
- Deduplicated by `semantic_hash`, higher risk wins
- Only `approved_for_export` proposals go into CLAUDE.md; `approved_db_only` stays DB-only
- Merge strategy: `<!-- Hermes Brain sync -->` markers preserve user-written content above/below

## Deployment Pipeline

```
Agent writes proposal.md → ~/hermes-sync/inbox/proposals/
  ↓ Syncthing
VPS hermes-watch ingests → DB (pending/auto-approved)
  ↓ Telegram notification (if high-risk/pending)
Human reviews via Web UI → approve/reject
  ↓ Approval
Hermes exports → global.md + CLAUDE.md
  ↓ Syncthing (back to local)
Local brain-sync --apply projects:
  - ~/.claude/CLAUDE.md (agent instructions)
  - ~/.claude/skills/ (skill packages)
  - ~/.codex/rules/ (command approvals)
  - ~/.codex/skills/ (skill packages)
```