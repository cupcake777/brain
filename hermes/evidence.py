"""Evidence extraction and validation for Brain Protocol v3."""
import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Minimum content length for non-garbage text
_MIN_CONTENT_LENGTH = 20

# UUID pattern for detecting bare UUID garbage
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Required fields for strong evidence
_STRONG_EVIDENCE_FIELDS = {"source_type", "source_uri"}

# All recognized evidence fields
_EVIDENCE_FIELDS = {
    "source_type", "source_uri", "source_span",
    "quoted_excerpt", "content_hash",
}


def _is_garbage_content(text: str) -> bool:
    """Return True if the text looks like garbage (bare UUID, empty, too short)."""
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) < _MIN_CONTENT_LENGTH:
        return True
    if _UUID_PATTERN.match(stripped):
        return True
    return False


def parse_evidence_section(evidence_text: str) -> list[dict]:
    """Parse the Evidence section as a JSON array of evidence entries.

    Returns a list of parsed evidence dicts. Supports both the v3 JSON format
    and legacy free-text format. Empty or unparseable evidence returns [].
    """
    text = evidence_text.strip()
    if not text:
        return []

    # Try JSON format first (v3 protocol)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            parsed = [parsed]
        if isinstance(parsed, list) and all(isinstance(e, dict) for e in parsed):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    # Legacy format: free-text references
    # Parse lines like "session: 20260630_...", "file: /path/to/file"
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Try to detect session ID patterns
        session_match = re.search(r"([0-9]{8}_[0-9]{6}_[0-9a-f]{6})", line)
        if session_match:
            entries.append({
                "source_type": "session",
                "source_uri": session_match.group(1),
                "source_span": "",
                "quoted_excerpt": line[:500],
                "content_hash": "",
            })
            continue
        # File path
        file_match = re.search(r"(/[^\s,;]+)", line)
        if file_match:
            entries.append({
                "source_type": "file",
                "source_uri": file_match.group(1),
                "source_span": "",
                "quoted_excerpt": line[:500],
                "content_hash": "",
            })
            continue
        # URL
        url_match = re.search(r"(https?://[^\s,;]+)", line)
        if url_match:
            entries.append({
                "source_type": "url",
                "source_uri": url_match.group(1),
                "source_span": "",
                "quoted_excerpt": line[:500],
                "content_hash": "",
            })
            continue

    return entries


def classify_evidence(entries: list[dict]) -> str:
    """Classify evidence quality.

    Returns:
        "strong" — at least one entry has source_type + source_uri + quoted_excerpt
        "weak"   — at least one entry has source_type + source_uri, but no excerpt
        "none"   — no valid evidence entries
    """
    if not entries:
        return "none"

    has_strong = False
    has_weak = False

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source_type = str(entry.get("source_type", "")).strip()
        source_uri = str(entry.get("source_uri", "")).strip()
        quoted_excerpt = str(entry.get("quoted_excerpt", "")).strip()

        if not source_type or not source_uri:
            continue

        if quoted_excerpt and len(quoted_excerpt) >= 10:
            has_strong = True
        else:
            has_weak = True

    if has_strong:
        return "strong"
    if has_weak:
        return "weak"
    return "none"


def validate_evidence(evidence_text: str) -> tuple[str, list[dict]]:
    """Validate the Evidence section and return (quality, entries).

    Raises ValueError if evidence is completely empty/missing.
    """
    entries = parse_evidence_section(evidence_text)
    quality = classify_evidence(entries)

    if quality == "none":
        raise ValueError(
            "proposal Evidence section has no valid evidence entries. "
            "At minimum, provide source_type and source_uri (e.g., session ID, "
            "file path, or URL). See Brain Protocol v3 §0.1."
        )

    return quality, entries


def extract_observations(
    entries: list[dict],
    proposal_id: str,
) -> list[dict]:
    """Convert evidence entries to observation rows for DB insertion.

    Each observation is immutable evidence linked to a proposal.
    """
    observations = []
    now = datetime.now(timezone.utc).isoformat()

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source_type = str(entry.get("source_type", "")).strip()
        source_uri = str(entry.get("source_uri", "")).strip()
        if not source_type or not source_uri:
            continue

        import uuid
        import hashlib

        obs_id = str(uuid.uuid4())
        content = str(entry.get("quoted_excerpt", ""))[:2000]
        source_span = str(entry.get("source_span", ""))[:500]
        quoted_excerpt = str(entry.get("quoted_excerpt", ""))[:500]
        content_hash = str(entry.get("content_hash", ""))

        if not content_hash:
            hash_input = f"{content}|{source_uri}"
            content_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

        observations.append({
            "id": obs_id,
            "content": content,
            "source_type": source_type,
            "source_uri": source_uri,
            "source_span": source_span,
            "quoted_excerpt": quoted_excerpt,
            "content_hash": content_hash,
            "proposal_id": proposal_id,
            "created_at": now,
        })

    return observations
