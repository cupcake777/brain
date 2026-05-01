from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from hermes.repository import HermesRepository

@dataclass(frozen=True)
class ExportBudgets:
    global_hard_cap: int = 8 * 1024
    global_soft_cap: int = 6 * 1024
    project_hard_cap: int = 12 * 1024
    project_soft_cap: int = 9 * 1024
    recent_hard_cap: int = 4 * 1024
    recent_soft_cap: int = 3 * 1024
    claude_md_hard_cap: int = 16 * 1024

# ---------------------------------------------------------------------------
# Category / risk ordering for CLAUDE.md compilation
# ---------------------------------------------------------------------------

_CATEGORY_ORDER = {"rule": 0, "workflow_hint": 1, "preference": 2, "fact": 3}
_CATEGORY_TITLES = {
    "rule": "Rules",
    "workflow_hint": "Workflows",
    "preference": "Preferences",
    "fact": "Facts",
}
_REQUIRED_CATEGORIES = {"rule", "workflow_hint"}
_RISK_ORDER = {"high": 3, "medium": 2, "low": 1}
_KEYWORD_ORDER = {"Always": 0, "Never": 1, "Prefer": 2, "Avoid": 3, "If": 4}

# ---------------------------------------------------------------------------
# Helpers for CLAUDE.md compilation
# ---------------------------------------------------------------------------

def _slugify(text: str, max_len: int = 60) -> str:
    """Derive a stable kebab-case slug from suggested_memory text."""
    # Take first ~6 meaningful words
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    slug = "-".join(words[:6]) if len(words) >= 2 else "-".join(words)
    return slug[:max_len]


def _decompose_memory(memory: str) -> list[str]:
    """Split a suggested_memory into imperative bullet lines.

    Each line is prefixed with a keyword: **Always**, **Never**, **Prefer**,
    **Avoid**, or **If**.  If no keyword fits naturally, **Always** is used.
    """
    # Split on sentence boundaries or semicolons
    sentences = re.split(r"(?<=[.!?])\s+|;\s*", memory.strip())
    lines: list[str] = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        # Heuristic keyword assignment
        low = s.lower()
        if low.startswith(("never ", "do not ", "don't ", "must not ")):
            line = s.replace(s.split()[0], "**Never**", 1) if s.split()[0].lower() in ("never", "do", "don't") else f"**Never** {s[0].lower()}{s[1:]}"
            # Normalise common patterns
            for prefix in ("Never ", "Do not ", "Don't ", "Must not "):
                if low.startswith(prefix.lower()):
                    rest = s[len(prefix):]
                    line = f"**Never** {rest[0].lower()}{rest[1:]}" if rest else s
                    break
            else:
                line = f"**Never** {s[0].lower()}{s[1:]}"
        elif low.startswith(("always ", "must ")):
            for prefix in ("Always ", "Must "):
                if low.startswith(prefix.lower()):
                    rest = s[len(prefix):]
                    line = f"**Always** {rest[0].lower()}{rest[1:]}" if rest else s
                    break
            else:
                line = f"**Always** {s[0].lower()}{s[1:]}"
        elif low.startswith(("prefer ", "preferably ")):
            line = f"**Prefer** {s[len('prefer '):]}" if low.startswith("prefer ") else f"**Prefer** {s}"
        elif low.startswith(("avoid ", "should avoid ")):
            line = f"**Avoid** {s[len('avoid '):]}" if low.startswith("avoid ") else f"**Avoid** {s}"
        elif low.startswith("if "):
            line = f"**If** {s[3:]}"
        else:
            # Default: Always
            line = f"- {s}"
            # Still check for negative patterns mid-sentence
            if any(neg in low for neg in ("must not", "never", "do not", "don't")):
                # Try to reframe as a Never line
                line = f"**Never** {s[0].lower()}{s[1:]}"
            else:
                line = f"**Always** {s[0].lower()}{s[1:]}"
        if not line.startswith("- "):
            line = f"- {line}"
        lines.append(line)
    if lines:
        return lines
    if memory:
        return [f"- **Always** {memory[0].lower()}{memory[1:]}"]
    return ["- (no memory content)"]


def _format_claude_entry(proposal: dict) -> str:
    """Format a single proposal as a CLAUDE.md entry."""
    cat = proposal.get("category", "rule")
    slug = _slugify(str(proposal.get("suggested_memory", "")))
    scope = str(proposal.get("scope", "global"))
    risk = proposal.get("risk_level", "medium")

    # Heading with optional scope annotation
    heading = f"### {cat}: {slug}"
    if scope != "global":
        heading += f" (scope: {scope})"
    heading += f" [{risk}]"

    # Decompose suggested_memory into imperative lines
    memory = str(proposal.get("suggested_memory", ""))
    lines = _decompose_memory(memory)

    return heading + "\n" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# ExportCompiler
# ---------------------------------------------------------------------------

class ExportCompiler:
    def __init__(self, *, repo: HermesRepository, sync_root: str | Path, budgets: ExportBudgets | None = None) -> None:
        self.repo = repo
        self.sync_root = Path(sync_root)
        self.budgets = budgets or ExportBudgets()

    def build_project_export(self, project_key: str) -> Path:
        proposals = self.repo.list_exportable(project_key)
        active = self._collapse_superseded(proposals)
        body = self._build_markdown_body(active, project_key=project_key, scope_label="Project Learnings")
        body = self._enforce_cap(body, hard_cap=self.budgets.project_hard_cap, soft_cap=self.budgets.project_soft_cap)
        export_dir = self.sync_root / "exports" / "projects"
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / f"{project_key}.md"
        path.write_text(body, encoding="utf-8")
        self.repo.record_export(
            scope_type="project",
            project_key=project_key,
            file_name=path.name,
            size_bytes=path.stat().st_size,
        )
        return path

    def build_global_export(self) -> Path:
        proposals = self.repo.list_exportable(None)
        body = self._build_markdown_body(self._collapse_superseded(proposals), project_key="global", scope_label="Core Rules")
        body = self._enforce_cap(body, hard_cap=self.budgets.global_hard_cap, soft_cap=self.budgets.global_soft_cap)
        export_dir = self.sync_root / "exports" / "global"
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / "global.md"
        path.write_text(body, encoding="utf-8")
        self.repo.record_export(
            scope_type="global",
            project_key="global",
            file_name=path.name,
            size_bytes=path.stat().st_size,
        )
        return path

    def build_claude_md_export(self) -> Path:
        """Compile approved_for_export proposals into CLAUDE.md format.

        Only proposals with state='approved_for_export' are included.
        approved_db_only proposals are excluded (they must be promoted first).
        """
        proposals = self.repo.list_exportable(None)  # global scope
        active = self._collapse_superseded(proposals)
        # Filter: only approved_for_export
        entries = [p for p in active if p.get("state") == "approved_for_export"]
        if not entries:
            body = self._build_empty_claude_md()
        else:
            body = self._compile_claude_md(entries)

        body = self._enforce_cap(body, hard_cap=self.budgets.claude_md_hard_cap)
        export_dir = self.sync_root / "exports" / "global"
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / "CLAUDE.md"
        path.write_text(body, encoding="utf-8")
        self.repo.record_export(
            scope_type="global",
            project_key="global",
            file_name=path.name,
            size_bytes=path.stat().st_size,
        )
        return path

    def _build_empty_claude_md(self) -> str:
        now = datetime.now(timezone.utc).isoformat()
        return (
            f"# CLAUDE.md\n\n"
            f"<!-- Hermes Brain sync: auto-generated from approved proposals. -->\n"
            f"<!-- Edits will be overwritten on next projection cycle. -->\n"
            f"<!-- Source of truth: Hermes Brain VPS proposals DB + ~/hermes-sync/brain/ -->\n"
            f"<!-- Project: global | Updated: {now} | Entries: 0 -->\n\n"
            f"## Rules\n\n<!-- no entries -->\n\n"
            f"## Workflows\n\n<!-- no entries -->\n\n"
            f"---\n\n"
            f"*End of Hermes-managed rules. Do not edit above this line — changes will be overwritten.*\n"
            f"*To propose a new rule: write a .md proposal to `~/hermes-sync/inbox/proposals/` and it will be reviewed via the Brain pipeline.*\n"
        )

    def _compile_claude_md(self, proposals: list[dict]) -> str:
        # Deduplicate by semantic_hash, keeping higher risk level
        seen: dict[str, dict] = {}
        for p in proposals:
            key = str(p.get("semantic_hash") or str(p.get("suggested_memory", ""))[:80])
            existing = seen.get(key)
            if existing is None or _RISK_ORDER.get(p.get("risk_level", "medium"), 1) > _RISK_ORDER.get(existing.get("risk_level", "medium"), 1):
                seen[key] = p

        entries = sorted(
            seen.values(),
            key=lambda p: (
                _CATEGORY_ORDER.get(p.get("category", "rule"), 99),
                -_RISK_ORDER.get(p.get("risk_level", "medium"), 1),
                _slugify(str(p.get("suggested_memory", ""))),
            ),
        )

        # Group by category
        groups: dict[str, list[dict]] = {}
        for e in entries:
            cat = e.get("category", "rule")
            groups.setdefault(cat, []).append(e)

        now = datetime.now(timezone.utc).isoformat()
        header = (
            f"# CLAUDE.md\n\n"
            f"<!-- Hermes Brain sync: auto-generated from approved proposals. -->\n"
            f"<!-- Edits will be overwritten on next projection cycle. -->\n"
            f"<!-- Source of truth: Hermes Brain VPS proposals DB + ~/hermes-sync/brain/ -->\n"
            f"<!-- Project: global | Updated: {now} | Entries: {len(entries)} -->\n\n"
        )

        sections: list[str] = []
        for cat in ["rule", "workflow_hint", "preference", "fact"]:
            title = _CATEGORY_TITLES.get(cat, cat.title())
            items = groups.get(cat, [])
            section = f"## {title}\n\n"
            if not items:
                section += "<!-- no entries -->\n\n"
            else:
                section += "\n".join(_format_claude_entry(p) for p in items) + "\n\n"
            sections.append(section)

        footer = (
            "---\n\n"
            "*End of Hermes-managed rules. Do not edit above this line — changes will be overwritten.*\n"
            "*To propose a new rule: write a .md proposal to `~/hermes-sync/inbox/proposals/` and it will be reviewed via the Brain pipeline.*\n"
        )

        return header + "".join(sections) + footer

    # -----------------------------------------------------------------------
    # Original markdown export methods (unchanged)
    # -----------------------------------------------------------------------

    def _collapse_superseded(self, proposals: list[dict[str, object]]) -> list[dict[str, object]]:
        superseded_ids = {str(item["supersedes"]) for item in proposals if item.get("supersedes")}
        return [item for item in proposals if str(item["proposal_id"]) not in superseded_ids]

    def _build_markdown_body(self, proposals: list[dict[str, object]], *, project_key: str, scope_label: str) -> str:
        lines = [
            f"# {project_key} export",
            "",
            f"Last updated: {datetime.now(timezone.utc).isoformat()}",
            "",
            f"## {scope_label}",
        ]
        for item in proposals:
            lines.append(f"- {item['suggested_memory']}")
        if not proposals:
            lines.append("- No approved export rules yet.")
        return "\n".join(lines).strip() + "\n"

    def _enforce_soft_cap(self, body: str, soft_cap: int) -> str:
        encoded = body.encode("utf-8")
        if len(encoded) > soft_cap:
            warning = "<!-- Over soft cap: consider eviction -->\n"
            return warning + body
        return body

    def _enforce_cap(self, body: str, hard_cap: int, soft_cap: int | None = None) -> str:
        encoded = body.encode("utf-8")
        if len(encoded) > hard_cap:
            truncated = encoded[: hard_cap - len(b"\n...truncated\n")] + b"\n...truncated\n"
            return truncated.decode("utf-8", errors="ignore")
        if soft_cap is not None:
            return self._enforce_soft_cap(body, soft_cap)
        return body