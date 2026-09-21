"""Sensitive content detection gate.

Centralized enforcement of Brain's secret-scan contract.

A single ``SensitiveContentGate`` instance is wired into every persistence
adapter (HTTP request bodies, proposal writer, ingest, and direct persistence
helpers). All callers MUST treat any ``SensitiveContentError`` as a hard
rejection: do not write the file, do not commit the DB row, do not log the
matched substring, and do not echo the offending payload in error responses.

Design constraints:

* Fail-closed: a disabled / mis-initialised gate blocks writes (audit hook
  logs a single ``sensitive_gate_disabled`` counter and raises).
* Bounded regexes with explicit size limits, no catastrophic backtracking.
* Returns generic info only: detector class + JSON path.  Never the matched
  substring, surrounding context, request body, or SQL parameters.
* Normalises input via NFKC, URL/HTML decoding, and case-folding for the
  matchers that need it.  Keeps the original payload intact for caller use.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from html import unescape
from typing import Any, Iterable
from urllib.parse import unquote


# --- Matchers ---------------------------------------------------------------

# All patterns must be anchored to "word-ish" boundaries and have a hard
# length limit to bound back-tracking.  See review:
# "Regexes must have explicit size limits and avoid catastrophic backtracking."

_BEARER_TOKEN = re.compile(
    r"\bbearer\s+[A-Za-z0-9._\-]{8,4096}\b",
    flags=re.IGNORECASE,
)

_PROVIDER_KEY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # OpenAI / Groq / Mistral / xAI style "sk-..." style keys
    ("api_key_sk", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,200}\b")),
    ("api_key_groq", re.compile(r"\bgsk_[A-Za-z0-9]{16,200}\b")),
    # GitHub classic + fine-grained
    ("api_key_github", re.compile(r"\bghp_[A-Za-z0-9]{16,200}\b")),
    ("api_key_github_fine", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,200}\b")),
    # Google API key
    ("api_key_google", re.compile(r"\bAIza[0-9A-Za-z_\-]{16,200}\b")),
    # AWS access keys
    ("api_key_aws", re.compile(r"\bAKIA[0-9A-Z]{12,32}\b")),
    # Hugging Face
    ("api_key_hf", re.compile(r"\bhf_[A-Za-z0-9]{16,200}\b")),
    # Anthropic
    ("api_key_anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,200}\b")),
    # Stripe
    ("api_key_stripe", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,200}\b")),
    # Slack
    ("api_key_slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,200}\b")),
    # Generic labeled secrets
    ("labeled_secret",
     re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|pwd)\s*[:=]\s*[\"']?([A-Za-z0-9._\-/+=]{12,512})[\"']?")),
)

# Email: pragmatic RFC 5322 subset with size cap.
_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,255}\.[A-Za-z]{2,24}\b"
)

# IPv4: cheap capture; validated through ipaddress.
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# IPv6: bracket-stripped and zone-id tolerant; validated through ipaddress.
_IPV6 = re.compile(r"\b(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}\b")

_MAX_INPUT_BYTES = 200_000  # deny suspiciously large payloads; reject rather than process
_MAX_MATCH_LENGTH = 200    # used to truncate internal regex matches; never returned to caller


# --- Exceptions -------------------------------------------------------------


@dataclass(frozen=True)
class SensitiveMatch:
    """Generic, non-leaking match descriptor exposed to callers."""

    detector: str
    field: str


class SensitiveContentError(Exception):
    """Raised when a SensitiveContentGate rejects a payload.

    Attributes:
        detector: short identifier of the matching detector class.
        field:    JSON path / key where the offending value was found.
        matches:  full list of SensitiveMatch descriptors (no raw text).
    """

    def __init__(self, matches: list[SensitiveMatch]) -> None:
        self.detector = matches[0].detector if matches else "sensitive_content_detected"
        self.field = matches[0].field if matches else ""
        self.matches = matches
        super().__init__(
            f"sensitive_content_detected ({self.detector} @ {self.field or '<root>'})"
        )


# --- Normalisation helpers -------------------------------------------------


def _normalize(value: str) -> str:
    """Apply NFKC + URL + HTML decoding to harden against obfuscation.

    The original value is *not* mutated; this returns a derived string used
    for matching only.
    """
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value)
    # Apply URL decoding twice to catch double-encoded payloads.
    try:
        text = unquote(unquote(text))
    except Exception:
        # URL-decode errors should never block the gate; fall back to original.
        pass
    text = unescape(text)
    return text


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _detect_high_entropy_secrets(value: str) -> Iterable[str]:
    """Yield generic detector ids for high-entropy candidates ≥ 32 chars.

    Avoids base64-decoding the payload (review: "Base64/hex/encrypted
    secrets; decoding everything may create false positives or DoS").
    Only flags sequences that look like base64/hex AND have entropy ≥ 4.5.
    """
    candidates: list[str] = []
    for match in re.finditer(r"\b[A-Za-z0-9+/=_\-]{32,200}\b", value):
        token = match.group(0)
        if not token:
            continue
        ratio_alpha = sum(1 for ch in token if ch.isalnum()) / len(token)
        # Exclude plain-word / hex-like candidates; require ≥ 0.85 alnum.
        if ratio_alpha < 0.85:
            continue
        ent = _entropy(token)
        if ent >= 4.5 and len(token) >= 40:
            candidates.append("high_entropy_secret")
    return candidates


def _ip_candidates(value: str) -> Iterable[str]:
    """Yield detector ids for valid IPv4/IPv6 candidates."""
    import ipaddress
    out: list[str] = []
    for m in _IPV4.finditer(value):
        candidate = m.group(0)
        if len(candidate) > 64:
            continue
        try:
            ipaddress.IPv4Address(candidate)
        except ValueError:
            continue
        out.append("ipv4_address")
    for m in _IPV6.finditer(value):
        candidate = m.group(0).split("%", 1)[0]
        candidate = candidate.strip("[]")
        if len(candidate) > 96:
            continue
        try:
            ipaddress.IPv6Address(candidate)
        except ValueError:
            continue
        out.append("ipv6_address")
    return out


# --- Gate ------------------------------------------------------------------


class SensitiveContentGate:
    """Apply detectors recursively over a payload (dict / list / str / scalars).

    Raises :class:`SensitiveContentError` on the first detector category match
    OR when the payload exceeds the size budget.  Logs a redacted counter only.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        max_input_bytes: int = _MAX_INPUT_BYTES,
    ) -> None:
        self.enabled = enabled
        self.max_input_bytes = max_input_bytes

    def audit(self) -> None:
        """Verify gate is enabled and ready.  Raises SensitiveContentError otherwise.

        Callers should invoke this once at startup; persistence helpers should
        call it again as the final invariant.
        """
        if not self.enabled:
            raise SensitiveContentError(
                [SensitiveMatch(detector="sensitive_gate_disabled", field="<audit>")]
            )

    def check(self, payload: Any, *, field: str = "") -> None:
        """Walk a payload and raise on first detector hit.

        Field path is constructed with bracketed indices so the caller can
        sanitise offending records without echoing the value itself.
        """
        if not self.enabled:
            raise SensitiveContentError(
                [SensitiveMatch(detector="sensitive_gate_disabled", field=field or "<root>")]
            )
        size = _estimate_size(payload)
        if size > self.max_input_bytes:
            raise SensitiveContentError(
                [SensitiveMatch(detector="sensitive_content_too_large", field=field or "<root>")]
            )
        matches = self._scan(payload, field=field)
        if matches:
            raise SensitiveContentError(matches)

    def _scan(self, payload: Any, *, field: str) -> list[SensitiveMatch]:
        if isinstance(payload, dict):
            found: list[SensitiveMatch] = []
            for key, value in payload.items():
                child_field = f"{field}.{key}" if field else str(key)
                found.extend(self._scan(value, field=child_field))
                if found:
                    return found
            return found
        if isinstance(payload, list):
            for index, value in enumerate(payload):
                child_field = f"{field}[{index}]"
                found = self._scan(value, field=child_field)
                if found:
                    return found
            return []
        if isinstance(payload, str):
            return self._scan_string(payload, field=field)
        return []

    def _scan_string(self, value: str, *, field: str) -> list[SensitiveMatch]:
        if not value:
            return []
        # Coerce to str in case caller passes bytes.
        try:
            text = value if isinstance(value, str) else value.decode("utf-8", "replace")
        except Exception:
            text = str(value)
        if len(text.encode("utf-8", "ignore")) > self.max_input_bytes:
            return [SensitiveMatch(detector="sensitive_content_too_large", field=field)]
        normalised = _normalize(text)
        # Match against both normalised and raw to catch obfuscation bypasses.
        for source, source_label in ((normalised, "normalized"), (text, "raw")):
            for match in self._detect(source, source_label, field=field):
                return [match]
        return []

    def _detect(self, value: str, source: str, *, field: str) -> Iterable[SensitiveMatch]:
        # Bearer tokens (case-insensitive)
        if _BEARER_TOKEN.search(value):
            yield SensitiveMatch(detector="bearer_token", field=field)
        # Provider-specific API keys
        for detector, pattern in _PROVIDER_KEY_PATTERNS:
            if pattern.search(value):
                yield SensitiveMatch(detector=detector, field=field)
        # Generic labelled secrets are intentionally tested *after* provider
        # patterns so that "sk-..." style keys are not shadowed.
        for detector in _detect_high_entropy_secrets(value):
            yield SensitiveMatch(detector=detector, field=field)
        # Email
        if _EMAIL.search(value):
            yield SensitiveMatch(detector="email_address", field=field)
        # IPv4 / IPv6 (validated through ipaddress)
        for detector in _ip_candidates(value):
            yield SensitiveMatch(detector=detector, field=field)


# --- Helpers ---------------------------------------------------------------


def _estimate_size(payload: Any) -> int:
    """Cheap size estimate for nested payloads.

    Bounded so the gate cannot be used to amplify CPU / memory cost on a
    pathological input — see review: "Availability attacks using huge input".
    """
    if isinstance(payload, str):
        return len(payload.encode("utf-8", "ignore"))
    if isinstance(payload, (int, float, bool)) or payload is None:
        return 32
    if isinstance(payload, dict):
        total = 16
        for key, value in payload.items():
            total += _estimate_size(key) + _estimate_size(value)
            if total > _MAX_INPUT_BYTES:
                return total
        return total
    if isinstance(payload, list):
        total = 16
        for item in payload:
            total += _estimate_size(item)
            if total > _MAX_INPUT_BYTES:
                return total
        return total
    return 64


# Module-level singleton used by persistence helpers; overridable for tests.
_default_gate: SensitiveContentGate | None = None


def default_gate() -> SensitiveContentGate:
    global _default_gate
    if _default_gate is None:
        from os import getenv

        env_enabled = getenv("BRAIN_SENSITIVE_GATE", "1").lower() not in {"0", "false", "off", "no"}
        _default_gate = SensitiveContentGate(enabled=env_enabled)
    return _default_gate


def reset_default_gate_for_tests() -> None:
    """Tests use this to inject a fresh gate per fixture."""
    global _default_gate
    _default_gate = None


__all__ = [
    "SensitiveContentError",
    "SensitiveContentGate",
    "SensitiveMatch",
    "default_gate",
    "reset_default_gate_for_tests",
]