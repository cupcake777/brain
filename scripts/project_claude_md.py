#!/usr/bin/env python3
"""Project CLAUDE.md from Hermes Brain exports to ~/.claude/CLAUDE.md.

Handles user-section preservation per the CLAUDE.md spec:
- Wraps existing user content with <!-- User-managed section --> markers on first run
- Replaces only the Hermes-managed section between <!-- Hermes Brain sync --> and <!-- End of Hermes-managed rules -->
- Preserves all user content outside those markers
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

SYNC_ROOT = Path.home() / "hermes-sync"
SOURCE = SYNC_ROOT / "exports" / "global" / "CLAUDE.md"
TARGET = Path.home() / ".claude" / "CLAUDE.md"

HERMES_START = "<!-- Hermes Brain sync:"
HERMES_END = "<!-- End of Hermes-managed rules"
USER_START = "<!-- User-managed section:"
USER_END = "<!-- End of user-managed section"


def _atomic_write(target: Path, content: str) -> None:
    """Write content to target atomically using tmpfile + rename."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent), suffix=".tmp", prefix=".claude-md-"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(target))
    except BaseException:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def find_marker_range(text: str, start_marker: str, end_marker: str) -> tuple[int, int] | None:
    """Find the byte range of content between start_marker and end_marker lines."""
    lines = text.split("\n")
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith(start_marker):
            start_idx = i
        if line.strip().startswith(end_marker):
            end_idx = i
            break
    if start_idx is not None and end_idx is not None:
        return (start_idx, end_idx)
    return None


def project_claude_md(*, dry_run: bool = False) -> bool:
    """Project CLAUDE.md from exports to ~/.claude/CLAUDE.md.
    
    Returns True if changes were made (or would be made in dry_run mode).
    """
    if not SOURCE.exists():
        print(f"Source not found: {SOURCE}")
        return False

    new_content = SOURCE.read_text(encoding="utf-8")
    target = TARGET
    target.parent.mkdir(parents=True, exist_ok=True)

    if not target.exists():
        # First projection: just copy
        if dry_run:
            print(f"Would create: {target}")
            return True
        shutil.copy2(SOURCE, target)
        print(f"Created: {target}")
        return True

    existing = target.read_text(encoding="utf-8")

    # Check if file already has Hermes markers
    hermes_range = find_marker_range(existing, HERMES_START, HERMES_END)

    if hermes_range is None:
        # No Hermes End marker — check if this is a clean file with just a header + Hermes section
        # (i.e., the output of a manual rebuild, not a corrupted accumulative file)
        #
        # Strategy: if the file is small enough (< 200KB) and contains exactly one Hermes sync
        # start marker, treat it as a clean replacement target rather than wrapping.
        hermes_start_count = existing.count(HERMES_START)
        existing_size = len(existing.encode("utf-8"))

        if hermes_start_count == 1 and existing_size < 200_000:
            # Clean file: just rewrite with proper user section wrapper
            merged = (
                f"# CLAUDE.md\n\n"
                f"{USER_START} content below this line is preserved across projections. -->\n\n"
                f"{new_content.rstrip()}\n"
            )
        else:
            # Corrupted/accumulative file: wrap existing content as user section, then append Hermes section
            lines = existing.split("\n")

            # Check if file already has user markers
            user_range = find_marker_range(existing, USER_START, USER_END)

            if user_range is None:
                # No markers at all: wrap everything as user content, then append Hermes section
                user_content = existing.rstrip("\n")
                merged = (
                    f"# CLAUDE.md\n\n"
                    f"{USER_START} content below this line is preserved across projections. -->\n\n"
                    f"{user_content}\n\n"
                    f"{USER_END} -->\n\n"
                    f"---\n\n"
                    f"{new_content.rstrip()}\n"
                )
            else:
                # User markers exist but no Hermes markers: append Hermes section after user section
                new_hermes = new_content.split("\n", 1)[-1] if "\n" in new_content else new_content
                merged = existing.rstrip("\n") + "\n\n" + new_hermes + "\n"

        if dry_run:
            print(f"Would update: {target}")
            return True

        _atomic_write(target, merged)
        print(f"Updated: {target}")
        return True

    # Hermes markers exist: replace the Hermes section, preserve everything else
    lines = existing.split("\n")
    start_idx, end_idx = hermes_range

    # Find the new Hermes-managed content (everything between the markers in the source)
    new_lines = new_content.split("\n")
    new_hermes_start = None
    new_hermes_end = None
    for i, line in enumerate(new_lines):
        if line.strip().startswith(HERMES_START):
            new_hermes_start = i
        if line.strip().startswith(HERMES_END):
            new_hermes_end = i
            break

    if new_hermes_start is None or new_hermes_end is None:
        # Source doesn't have proper markers, just replace the file
        if dry_run:
            print(f"Would replace: {target} (source missing markers)")
            return True
        shutil.copy2(SOURCE, target)
        print(f"Replaced: {target}")
        return True

    # Build merged content: before Hermes section + new Hermes section + after Hermes section
    before = lines[:start_idx]
    after = lines[end_idx + 1:]  # Lines after the End marker
    new_hermes_section = new_lines[new_hermes_start:new_hermes_end + 1]

    merged_lines = before + new_hermes_section + after
    merged = "\n".join(merged_lines)

    if merged == existing:
        print(f"No changes: {target}")
        return False

    if dry_run:
        print(f"Would update: {target}")
        return True

    _atomic_write(target, merged)
    print(f"Updated: {target}")
    return True


def main():
    dry_run = "--check" in sys.argv or "--dry-run" in sys.argv
    project_claude_md(dry_run=dry_run)


if __name__ == "__main__":
    main()