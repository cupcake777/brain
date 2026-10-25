"""Deterministic, shadow-only compactor for Brain ``source_events`` (Phase 2).

Tier 0 (``source_events``) is immutable: this module only *reads* it and
emits additive, content-addressed sidecar artifacts.  Nothing here ever
writes to proposals, knowledge nodes, memory edges, or any other existing
table.  Normal mode writes exactly four derived tables
(``compaction_state``, ``compaction_blocks``, ``compaction_review``,
``compaction_relations``).

Design invariants (Phase 2 contract):

* **Deterministic** — compaction is a pure function of the input rows:
  same window (in any row order, any timezone offsets) ⇒ byte-identical
  blocks, digests, and content hashes.  Ordering is by UTC epoch
  (``occurred_at`` instants), never by raw timestamp strings.
* **Latest revision only** — when a ``source_events`` id has multiple
  versions, only the highest version is compacted.  Provenance and graph
  endpoints carry ``(event_id, version)`` pairs so superseded revisions
  are never silently mixed in.
* **Explicit failure→recovery chains** — only rows whose parsed status is
  explicitly ``failed`` may start a chain.  Only an explicitly
  ``completed`` event can close one; ``unknown`` never recovers (and
  never fabricates a failure).  Failures without an in-session recovery
  become ``unrecovered_failure`` review items, never silent losses.
  Legacy ``completed`` rows whose dropped response-field *names* hint at
  failure become ``possible_failure_legacy`` review items only.
* **Char budget on the final redacted text** — context digests are
  rendered under a hard char budget that includes the header and is
  enforced after redaction (redaction can grow text).  A budget smaller
  than the redacted header yields an explicitly truncated empty digest.
* **Scope isolation + deterministic rebuild** — every read and write is
  bound to one ``(workspace, project)`` principal.  State is keyed by a
  collision-free JSON key; ``compaction_blocks``/``compaction_relations``
  primary keys include the principal scope, so identical content in two
  scopes is storable in both.  A run recomputes the scope's full window
  up to the horizon; if the input basis digest is unchanged the run is a
  physical noop, otherwise the scope's derived rows are replaced inside
  one transaction (no stale or duplicate derived rows survive).
  ``--full`` forces the rebuild and is itself idempotent.
  ``compaction_review_decisions`` is an operator sidecar, never created
  or written here. When it exists, a rebuild puts each decided row's
  non-open state back onto the matching ``compaction_review`` id.
  Undecided rows come back ``open``.
* **Shadow graph relations, candidate-only** — ``compaction_relations``
  is a derived, shadow-side table with typed endpoints, a rule version,
  an explicit confidence, a basis digest/ref per edge, and
  ``state='candidate'``.  It is never
  joined into the official graph.  Rules (exact evidence only, no
  text/time/heuristic matching):

  - ``block_event_exact``: tier-1 block → event revision, from the
    stored run ``(id, version)`` projections.
  - ``proposal_event_exact``: proposal revision → event revision, from
    ``proposal_revisions.source_refs`` entries of ``type=execution``
    whose referenced event exists in the same principal scope.
  - ``proposal_v1_knowledge_existing``: V1 ``proposals`` row →
    knowledge node, an exact projection of existing
    ``proposal_knowledge_links`` rows (a ``global`` bridge: V1 tables
    carry no principal scope, so the edge is never claimed to be a
    scoped event bridge).
  - knowledge↔knowledge edges are **not** copied: existing
    ``memory_edges`` are only reported as a count for future union
    queries.

  Edges beyond :data:`RELATION_MAX` are dropped with an explicit
  ``relation_overflow`` review item — never silently truncated.
* **Schema drift is an error** — a missing ``source_events``/relation
  source table is tolerated (empty input); any other
  ``sqlite3.OperationalError`` (e.g. a missing column) propagates, and
  the CLI reports it with a nonzero exit instead of a fake success.
* **``dry_run`` is physically read-only** — the database is opened with
  ``mode=ro``; zero table creation, zero writes.

This module is stdlib-only (plus :mod:`hermes.event_store`, itself
stdlib-only).
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# Reuse the ingest-layer privacy detectors verbatim so the compaction
# summary surface is guaranteed to be a subset of the gated ingest surface.
from hermes.event_store import (
    _BEARER_TOKEN,
    _LABELED_SECRET,
    _PROVIDER_KEY_SIGNATURE,
)


VERSION = "experience-compactor/2"

#: Idle gap that splits sessions (30 min).
SESSION_GAP_S = 1800.0
#: A failure must be recovered within this window to form a chain (15 min).
RECOVERY_WINDOW_S = 900.0
#: Consecutive same-tool failures merge into one chain while gap < 10 min.
CHAIN_GAP_S = 600.0
#: Never compact the trailing 48h (protects active sessions).
HORIZON_LAG_S = 48 * 3600.0
#: A signature seen fewer than this many times in the window is rare.
RARE_SIGNATURE_COUNT = 3
#: Default context-digest budget (chars).
DEFAULT_CHAR_BUDGET = 8000
#: Provenance sidecar cap before overflow becomes a review item.
PROVENANCE_MAX_IDS = 50_000
#: Deterministic chars-per-token heuristic.
TOKEN_ESTIMATE_DIVISOR = 4
#: Hard cap on candidate relations per scope per run; overflow is an
#: explicit review item, never a silent truncation.
RELATION_MAX = 20_000
#: Version tag stamped on every generated relation row.
RELATION_RULE_VERSION = "relation-rules/1"

STATUS_TOKENS = {"completed", "failed"}

#: Relation rules, in deterministic generation order.
RELATION_RULES: tuple[str, ...] = (
    "block_event_exact",
    "proposal_event_exact",
    "proposal_v1_knowledge_existing",
)


# ---------------------------------------------------------------------------
# Defense-in-depth redaction (summary-facing text ONLY; Tier 0 is never
# modified).  Rules are ordered most-specific first.  Hits log kind only.
# ---------------------------------------------------------------------------

_REDACT_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("provider_key", _PROVIDER_KEY_SIGNATURE, "<key>"),
    ("bearer", _BEARER_TOKEN, "<bearer>"),
    ("labeled_secret", _LABELED_SECRET, "<secret>"),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "<email>"),
    (
        "ipv4",
        re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
        "<ip>",
    ),
    ("home_path", re.compile(r"(?:/home|/Users)/[A-Za-z0-9._-]+/"), "~/"),
    ("root_path", re.compile(r"/root/"), "~/"),
    ("long_hex", re.compile(r"\b[0-9a-fA-F]{32,}\b"), "<hex>"),
)


def redact(text: str) -> tuple[str, list[dict[str, str]]]:
    """Return ``(redacted_text, hits)``; hits carry ``kind`` only, never values."""
    hits: list[dict[str, str]] = []
    out = text
    for kind, pattern, repl in _REDACT_RULES:

        def _sub(match: re.Match[str], _kind: str = kind) -> str:
            hits.append({"kind": _kind})
            return repl

        out = pattern.sub(_sub, out)
    return out, hits


# ---------------------------------------------------------------------------
# Parsing (right-anchored, pattern-driven; legacy + current adapter shapes)
# ---------------------------------------------------------------------------

FAILURE_HINT_FIELDS = frozenset({"failure", "isError", "FileNotFound"})

_RE_EXIT = re.compile(r"\bexit_code=(-?\d+)\b")
_RE_ERRTYPE = re.compile(r"\berror_type=([A-Za-z_][A-Za-z0-9_]*)\b")
_RE_FIELDS = re.compile(r"\bresponse fields: ([A-Za-z0-9_,]+)")


def parse_action(action: str | None) -> dict[str, str]:
    """Parse ``"<label> <event...> <tool> <status>"`` (status last)."""
    if not action:
        return {"label": "?", "event": "?", "tool": "?", "status": "unknown"}
    tokens = action.split(" ")
    status = tokens[-1] if tokens[-1] in STATUS_TOKENS else "unknown"
    if status in STATUS_TOKENS and len(tokens) >= 4:
        label, tool, event = tokens[0], tokens[-2], " ".join(tokens[1:-2])
    elif status in STATUS_TOKENS and len(tokens) == 3:
        label, tool, event = tokens[0], tokens[-2], ""
    else:
        label, tool, event, status = tokens[0], "?", " ".join(tokens[1:]) or "?", "unknown"
    return {"label": label, "event": event, "tool": tool, "status": status}


def parse_result(result: str | None) -> dict[str, Any]:
    """Parse result into status/exit_code/error_type/fields/tail."""
    text = result or ""
    head = text.split(";", 1)[0].strip()
    status = head if head in STATUS_TOKENS else "unknown"
    m = _RE_EXIT.search(text)
    exit_code = int(m.group(1)) if m else None
    m = _RE_ERRTYPE.search(text)
    error_type = m.group(1) if m else ""
    m = _RE_FIELDS.search(text)
    fields = frozenset(m.group(1).split(",")) if m else frozenset()
    tail = text
    idx = tail.find("response fields:")
    if idx >= 0:
        tail = tail[:idx]
    tail = _RE_EXIT.sub("", tail)
    tail = _RE_ERRTYPE.sub("", tail)
    tail = tail.replace(status, "", 1).strip(" ;")
    return {
        "status": status,
        "exit_code": exit_code,
        "error_type": error_type,
        "fields": fields,
        "tail": tail,
    }


# ---------------------------------------------------------------------------
# Canonical projection
# ---------------------------------------------------------------------------


def _epoch(iso: str) -> float:
    """UTC epoch seconds for an ISO timestamp of any offset shape."""
    raw = str(iso)
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


@dataclass(frozen=True)
class Ev:
    """Canonical projection of one ``source_events`` row (latest revision)."""

    id: str
    version: int
    project_id: str | None
    agent_id: str
    occurred_at: str
    action: str
    result: str
    payload_digest: str

    @property
    def ts(self) -> float:
        return _epoch(self.occurred_at)


def to_events(rows: Iterable[Mapping[str, Any]]) -> list[Ev]:
    """Project raw rows into canonical events.

    Only the **highest version** of each event id survives (ties on
    ``(version, payload_digest)`` broken deterministically).  Events are
    totally ordered by the UTC epoch of ``occurred_at`` — never by the
    raw timestamp string — then by ``(id, version)``, so the output
    never depends on input order or timezone offsets.
    """
    latest: dict[str, Mapping[str, Any]] = {}
    for r in rows:
        eid = str(r["id"])
        ver = int(r["version"])
        dig = str(r["payload_digest"] or "")
        cur = latest.get(eid)
        if cur is None or (ver, dig) > (int(cur["version"]), str(cur["payload_digest"] or "")):
            latest[eid] = r
    evs = [
        Ev(
            id=eid,
            version=int(r["version"]),
            project_id=(str(r["project_id"]) if r["project_id"] is not None else None),
            agent_id=str(r["agent_id"]),
            occurred_at=str(r["occurred_at"]),
            action=str(r["action"] or ""),
            result=str(r["result"] or ""),
            payload_digest=str(r["payload_digest"] or ""),
        )
        for eid, r in latest.items()
    ]
    evs.sort(key=lambda e: (e.ts, e.id, e.version))
    return evs


def signature_of(ev: Ev) -> tuple[str, str, str, str, tuple[str, ...], str]:
    p = parse_action(ev.action)
    q = parse_result(ev.result)
    status = q["status"] if q["status"] in STATUS_TOKENS else p["status"]
    return (
        p["label"],
        p["event"],
        p["tool"],
        status,
        tuple(sorted(q["fields"])),
        q["error_type"],
    )


def _is_failure(ev: Ev) -> bool:
    p = parse_action(ev.action)
    q = parse_result(ev.result)
    status = q["status"] if q["status"] in STATUS_TOKENS else p["status"]
    return status == "failed"  # unknown never fabricates a failure


def _possible_failure_legacy(ev: Ev) -> bool:
    p = parse_action(ev.action)
    q = parse_result(ev.result)
    if p["status"] == "failed" or q["status"] == "failed":
        return False
    return bool(q["fields"] & FAILURE_HINT_FIELDS)


# ---------------------------------------------------------------------------
# Sessionization + run folding + failure→recovery chains
# ---------------------------------------------------------------------------


@dataclass
class RunBlock:
    sig: tuple
    ids: list[str]
    id_versions: list[list]  # [[id, version], ...] aligned with ``ids``
    t0: float
    t1: float
    digests: list[str]

    @property
    def count(self) -> int:
        return len(self.ids)

    def digest_fingerprint(self) -> str:
        h = hashlib.sha256()
        for d in sorted(self.digests):
            h.update(d.encode())
        return h.hexdigest()[:16]


@dataclass
class Session:
    agent: str
    events: list[Ev]

    @property
    def sid(self) -> str:
        seed = f"{self.agent}|{self.events[0].id}"
        return "sess-" + hashlib.sha256(seed.encode()).hexdigest()[:12]

    @property
    def span(self) -> tuple[float, float]:
        return self.events[0].ts, self.events[-1].ts


def sessionize(events: Sequence[Ev], gap_s: float = SESSION_GAP_S) -> list[Session]:
    """Split per-agent streams on idle gaps > ``gap_s``.  Deterministic."""
    sessions: list[Session] = []
    by_agent: dict[str, list[Ev]] = {}
    for e in events:
        by_agent.setdefault(e.agent_id, []).append(e)
    for agent in sorted(by_agent):
        stream = by_agent[agent]
        cur: list[Ev] = [stream[0]]
        for e in stream[1:]:
            if e.ts - cur[-1].ts > gap_s:
                sessions.append(Session(agent, cur))
                cur = [e]
            else:
                cur.append(e)
        sessions.append(Session(agent, cur))
    sessions.sort(key=lambda s: (s.events[0].ts, s.agent, s.events[0].id))
    return sessions


def run_encode(events: Sequence[Ev]) -> list[RunBlock]:
    """Collapse consecutive identical-signature events into run blocks."""
    runs: list[RunBlock] = []
    for e in events:
        sig = signature_of(e)
        if runs and runs[-1].sig == sig:
            runs[-1].ids.append(e.id)
            runs[-1].id_versions.append([e.id, e.version])
            runs[-1].digests.append(e.payload_digest)
            runs[-1].t1 = e.ts
        else:
            runs.append(
                RunBlock(
                    sig=sig,
                    ids=[e.id],
                    id_versions=[[e.id, e.version]],
                    t0=e.ts,
                    t1=e.ts,
                    digests=[e.payload_digest],
                )
            )
    return runs


@dataclass
class Chain:
    tool: str
    fail_ids: list[str]
    recovery_id: str | None
    error_types: list[str]
    started_at: float
    recovered_at: float | None

    @property
    def duration_s(self) -> float | None:
        return (self.recovered_at - self.started_at) if self.recovered_at else None


def extract_chains(session: Session) -> tuple[list[Chain], list[str]]:
    """Group failure→recovery chains inside one session.

    Returns ``(chains, unrecovered_fail_ids)``.  A chain = one or more
    explicitly-``failed`` events of one tool followed by an explicitly
    ``completed`` event of that tool within :data:`RECOVERY_WINDOW_S`.
    ``unknown`` statuses never recover (and never fail).  Failures with
    no in-session recovery are returned unrecovered — they become review
    items, never silent losses.
    """
    chains: list[Chain] = []
    unrecovered: list[str] = []
    pending: dict[str, list[Ev]] = {}
    for e in session.events:
        tool = parse_action(e.action)["tool"]
        if _is_failure(e):
            bucket = pending.setdefault(tool, [])
            if bucket and e.ts - bucket[-1].ts > CHAIN_GAP_S:
                unrecovered.extend(x.id for x in bucket)
                bucket = pending[tool] = [e]
            else:
                bucket.append(e)
            continue
        # Not an explicit failure: it may only *recover* a pending chain if
        # it is explicitly completed — unknown statuses fall through and
        # leave the chain unrecovered.
        p = parse_action(e.action)
        q = parse_result(e.result)
        status = q["status"] if q["status"] in STATUS_TOKENS else p["status"]
        if status != "completed":
            continue
        bucket = pending.pop(tool, None)
        if bucket and e.ts - bucket[0].ts <= RECOVERY_WINDOW_S:
            chains.append(
                Chain(
                    tool=tool,
                    fail_ids=[x.id for x in bucket],
                    recovery_id=e.id,
                    error_types=sorted(
                        {
                            parse_result(x.result)["error_type"]
                            for x in bucket
                            if parse_result(x.result)["error_type"]
                        }
                    ),
                    started_at=bucket[0].ts,
                    recovered_at=e.ts,
                )
            )
        elif bucket:
            unrecovered.extend(x.id for x in bucket)
    for bucket in pending.values():
        unrecovered.extend(x.id for x in bucket)
    return chains, unrecovered


# ---------------------------------------------------------------------------
# Content-addressed blocks
# ---------------------------------------------------------------------------


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode()).hexdigest()


def build_tier1(session: Session) -> dict[str, Any]:
    """Session rollup: signature table + run provenance + chains + anomalies."""
    runs = run_encode(session.events)
    chains, unrecovered = extract_chains(session)
    sig_counter: dict[tuple, int] = {}
    for r in runs:
        sig_counter[r.sig] = sig_counter.get(r.sig, 0) + r.count
    possible_legacy = [e.id for e in session.events if _possible_failure_legacy(e)]
    block = {
        "type": "tier1/session",
        "compactor": VERSION,
        "project": session.events[0].project_id or "",
        "agent": session.agent,
        "session_id": session.sid,
        "t0": session.events[0].occurred_at,
        "t1": session.events[-1].occurred_at,
        "n_events": len(session.events),
        "n_runs": len(runs),
        "signatures": [
            {"sig": list(sig), "count": n}
            for sig, n in sorted(sig_counter.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "chains": [
            {
                "tool": c.tool,
                "fail_ids": c.fail_ids,
                "recovery_id": c.recovery_id,
                "error_types": c.error_types,
                "duration_s": c.duration_s,
            }
            for c in chains
        ],
        "unrecovered_fail_ids": unrecovered,
        "possible_failure_legacy_ids": possible_legacy,
        # Provenance sidecar: every event id verbatim (never truncated)
        # plus the exact (id, version) revision each id was taken from.
        "runs": [
            {
                "sig": list(r.sig),
                "count": r.count,
                "first_id": r.ids[0],
                "last_id": r.ids[-1],
                "ids": list(r.ids),
                "id_versions": [list(iv) for iv in r.id_versions],
                "digest_fp": r.digest_fingerprint(),
            }
            for r in runs
        ],
    }
    block["content_hash"] = content_hash({k: v for k, v in block.items()})
    return block


def build_tier2(t1_blocks: Sequence[Mapping[str, Any]], day: str) -> dict[str, Any]:
    """Day rollup over tier-1 blocks (context-facing)."""
    sig_totals: dict[tuple, int] = {}
    for b in t1_blocks:
        for s in b["signatures"]:
            key = tuple(s["sig"])
            sig_totals[key] = sig_totals.get(key, 0) + s["count"]
    block = {
        "type": "tier2/day",
        "compactor": VERSION,
        "day": day,
        "projects": sorted({b["project"] for b in t1_blocks}),
        "n_sessions": len(t1_blocks),
        "n_events": sum(b["n_events"] for b in t1_blocks),
        "n_runs": sum(b["n_runs"] for b in t1_blocks),
        "n_chains": sum(len(b["chains"]) for b in t1_blocks),
        "n_unrecovered": sum(len(b["unrecovered_fail_ids"]) for b in t1_blocks),
        "n_possible_failure_legacy": sum(len(b["possible_failure_legacy_ids"]) for b in t1_blocks),
        "top_signatures": [
            {"sig": list(sig), "count": n}
            for sig, n in sorted(sig_totals.items(), key=lambda kv: (-kv[1], kv[0]))[:12]
        ],
        "session_ids": [b["session_id"] for b in t1_blocks],
    }
    block["content_hash"] = content_hash({k: v for k, v in block.items()})
    return block


# ---------------------------------------------------------------------------
# Budgeted context digest (greedy fill by priority class; the budget is
# enforced on the FINAL REDACTED text — redaction may grow the text —
# and the header is counted like any other line).
# ---------------------------------------------------------------------------


def _fmt_sig(sig: Sequence[str]) -> str:
    label, event, tool, status, fields, err = sig[0], sig[1], sig[2], sig[3], sig[4], sig[5]
    parts = [f"{label}/{tool}/{status}"]
    if err:
        parts.append(f"err={err}")
    if fields:
        parts.append("fields=" + ",".join(fields))
    return " ".join(parts)


def render_digest(
    t2: Mapping[str, Any],
    t1_blocks: Sequence[Mapping[str, Any]],
    shadows: Sequence[Mapping[str, Any]],
    budget: int = DEFAULT_CHAR_BUDGET,
) -> tuple[str, dict[str, Any]]:
    """Render the context-facing digest under a hard char budget.

    Priority: REVIEW/shadow items > chains > session one-liners >
    signature table.  A line is accepted only if the *redacted* join of
    the accepted lines stays within ``budget``.  If even the redacted
    header exceeds the budget, the digest is empty and explicitly marked
    truncated with ``header`` in the overflow keys.
    """
    header = (
        f"== {VERSION} day={t2['day']} projects={','.join(t2['projects'])} =="
        f" events={t2['n_events']} sessions={t2['n_sessions']} runs={t2['n_runs']}"
    )
    overflow: list[str] = []

    def _fits(lines: list[str]) -> bool:
        text, _ = redact("\n".join(lines))
        return len(text) <= budget

    lines: list[str] = []
    if _fits([header]):
        lines.append(header)
    else:
        # Budget smaller than the redacted header: explicit empty digest.
        return "", {
            "chars": 0,
            "token_estimate": 0,
            "budget": budget,
            "truncated": True,
            "overflow_keys": ["header"],
            "redaction_hits": [],
            "content_hash": content_hash({"lines": [], "day": t2["day"]}),
        }

    def flush_candidate(line: str, key: str) -> bool:
        if _fits(lines + [line]):
            lines.append(line)
            return True
        if key not in overflow:
            overflow.append(key)
        return False

    # P0: shadows — at most 12 REVIEW lines; the rest stay in the durable queue.
    queue = sorted(shadows, key=lambda s: (s["kind"], s.get("ref", "")))
    cap = 12
    shown, rest = queue[:cap], queue[cap:]
    for sh in shown:
        flush_candidate(f"REVIEW {sh['kind']} {sh.get('ref', '')}".rstrip(),
                        f"shadow:{sh['kind']}:{sh.get('ref', '')}")
    if rest:
        flush_candidate(f"REVIEW +{len(rest)} more (see review queue)", "shadow:overflow-summary")
    # P1: chains
    for b in sorted(t1_blocks, key=lambda b: b["t0"]):
        for c in b["chains"]:
            flush_candidate(
                f"chain {b['agent']}/{c['tool']} failed x{len(c['fail_ids'])}"
                f" ({','.join(c['error_types']) or '?'})"
                f" -> recovered {c['duration_s']:.0f}s"
                f" [{c['fail_ids'][0]}..{c['recovery_id']}]",
                f"chain:{b['session_id']}",
            )
    # P2: session one-liners
    for b in sorted(t1_blocks, key=lambda b: b["t0"]):
        flush_candidate(
            f"sess {b['session_id']} {b['agent']} n={b['n_events']}"
            f" runs={b['n_runs']} t0={b['t0'][11:19]} t1={b['t1'][11:19]}",
            f"sess:{b['session_id']}",
        )
    # P3: signature table
    for s in t2["top_signatures"]:
        flush_candidate(f"sig x{s['count']:>5} {_fmt_sig(s['sig'])}", "sig")

    text, tail_hits = redact("\n".join(lines))
    meta = {
        "chars": len(text),
        "token_estimate": len(text) // TOKEN_ESTIMATE_DIVISOR,
        "budget": budget,
        "truncated": bool(overflow),
        "overflow_keys": overflow,
        "redaction_hits": tail_hits,
        "content_hash": content_hash({"lines": lines, "day": t2["day"]}),
    }
    return text, meta


# ---------------------------------------------------------------------------
# Shadow candidates (review queue — compaction never auto-applies these)
# ---------------------------------------------------------------------------


def collect_shadows(
    t1_blocks: Sequence[Mapping[str, Any]],
    overflow_keys: Sequence[str],
    provenance_ids: int,
) -> list[dict[str, Any]]:
    """Review candidates.  Rarity is measured over the whole compacted
    window, never per day.  Bulk runs are normal in this workload — every
    id stays in the sidecar — so they are stats, not shadows."""
    shadows: list[dict[str, Any]] = []
    sig_total: dict[tuple, int] = {}
    for b in t1_blocks:
        for s in b["signatures"]:
            key = tuple(s["sig"])
            sig_total[key] = sig_total.get(key, 0) + s["count"]
    for sig, n in sorted(sig_total.items()):
        if n < RARE_SIGNATURE_COUNT:
            shadows.append({"kind": "rare_signature", "ref": _fmt_sig(sig), "count": n})
    for b in t1_blocks:
        for fid in b["unrecovered_fail_ids"]:
            shadows.append({"kind": "unrecovered_failure", "ref": fid, "session": b["session_id"]})
        for fid in b["possible_failure_legacy_ids"]:
            shadows.append({"kind": "possible_failure_legacy", "ref": fid, "session": b["session_id"]})
    for key in overflow_keys:
        shadows.append({"kind": "budget_overflow", "ref": key})
    if provenance_ids > PROVENANCE_MAX_IDS:
        shadows.append({"kind": "provenance_overflow", "ref": str(provenance_ids)})
    shadows.sort(key=lambda s: (s["kind"], s["ref"]))
    return shadows


# ---------------------------------------------------------------------------
# Compaction driver (pure): full deterministic window, latest revisions,
# UTC-epoch ordering and horizon.
# ---------------------------------------------------------------------------


def compact_window(
    rows: Iterable[Mapping[str, Any]],
    *,
    horizon_iso: str | None = None,
    budget: int = DEFAULT_CHAR_BUDGET,
) -> dict[str, Any]:
    """Compact the latest revisions of ``rows`` up to ``horizon`` (inclusive).

    Pure function of ``(rows, horizon, budget)``: same inputs (any order,
    any timezone offsets) ⇒ byte-identical outputs, including every
    content hash.  The horizon is compared on the UTC instant.
    """
    events = to_events(rows)
    if horizon_iso is not None:
        horizon_epoch = _epoch(horizon_iso)
        window = [e for e in events if e.ts <= horizon_epoch]
    else:
        window = list(events)
    if not window:
        return {
            "status": "noop",
            "processed": 0,
            "tier1": [],
            "tier2": [],
            "digests": [],
            "shadows": [],
            "provenance": {"n_ids": 0, "ids": [], "id_versions": []},
        }

    sessions = sessionize(window)
    t1_blocks = [build_tier1(s) for s in sessions]
    by_day: dict[str, list[Mapping[str, Any]]] = {}
    for b in t1_blocks:
        by_day.setdefault(b["t0"][:10], []).append(b)
    t2_blocks = [build_tier2(by_day[d], d) for d in sorted(by_day)]

    provenance_ids = [e.id for e in window]
    id_versions = [[e.id, e.version] for e in window]
    window_shadows = collect_shadows(t1_blocks, [], len(provenance_ids))
    sess_to_day = {b["session_id"]: b["t0"][:10] for b in t1_blocks}
    last_day = max(t2_blocks, key=lambda t: t["day"])["day"]
    all_shadows: list[dict[str, Any]] = []
    digests: list[tuple[str, str, dict[str, Any]]] = []
    for t2 in t2_blocks:
        # Session-scoped shadows surface on their day; window-wide shadows
        # (rarity, provenance) surface once, on the last day.
        day_shadows = [
            s
            for s in window_shadows
            if s["kind"] in ("unrecovered_failure", "possible_failure_legacy")
            and sess_to_day.get(s.get("session", ""), "") == t2["day"]
        ]
        if t2["day"] == last_day:
            day_shadows += [
                s for s in window_shadows if s["kind"] not in ("unrecovered_failure", "possible_failure_legacy")
            ]
        day_shadows.sort(key=lambda s: (s["kind"], s["ref"]))
        text, meta = render_digest(t2, by_day[t2["day"]], day_shadows, budget=budget)
        all_shadows.extend({"day": t2["day"], **s} for s in day_shadows)
        for key in meta["overflow_keys"]:
            if key.startswith("shadow:"):
                continue  # shadows live in the durable queue, not overflow
            all_shadows.append({"day": t2["day"], "kind": "budget_overflow", "ref": key})
        digests.append((t2["day"], text, meta))

    return {
        "status": "ok",
        "processed": len(window),
        "tier1": t1_blocks,
        "tier2": t2_blocks,
        "digests": [{"day": d, "text": t, "meta": m} for d, t, m in digests],
        "shadows": all_shadows,
        "provenance": {
            "n_ids": len(provenance_ids),
            "ids": provenance_ids,
            "id_versions": id_versions,
        },
    }


def verify_coverage(result: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Provenance check: every window id appears exactly once (at exactly
    one version); run counts conserve (Σ run.count == n_events per block)."""
    ids = result["provenance"]["ids"]
    id_versions = [tuple(iv) for iv in result["provenance"]["id_versions"]]
    dupes = len(ids) - len(set(ids))
    version_dupes = len(id_versions) - len(set(id_versions))
    window_ids = {str(r["id"]) for r in rows}
    missing = window_ids - set(ids)
    extra = set(ids) - window_ids
    count_ok = all(
        sum(r["count"] for r in b["runs"]) == b["n_events"] for b in result["tier1"]
    )
    return {
        "ids_exact": dupes == 0 and version_dupes == 0 and not missing and not extra,
        "dupes": dupes,
        "missing": sorted(missing),
        "extra": sorted(extra),
        "counts_conserve": count_ok,
    }


# ---------------------------------------------------------------------------
# Shadow graph relations (candidate-only; exact evidence, typed endpoints)
# ---------------------------------------------------------------------------


def _relation_core(
    rule: str,
    from_type: str,
    from_id: str,
    from_version: int | None,
    to_type: str,
    to_id: str,
    to_version: int | None,
) -> str:
    return canonical_json(
        [
            RELATION_RULE_VERSION,
            rule,
            from_type,
            str(from_id),
            from_version,
            to_type,
            str(to_id),
            to_version,
        ]
    )


def build_relations(
    tier1_blocks: Sequence[Mapping[str, Any]],
    *,
    event_versions: Mapping[str, int],
    proposals: Sequence[Mapping[str, Any]],
    proposal_knowledge_links: Sequence[Mapping[str, Any]],
    v1_proposal_ids: set[str],
    knowledge_node_ids: set[str],
    rel_cap: int | None = None,
) -> dict[str, Any]:
    """Build candidate shadow-graph relations from exact evidence only.

    * ``block_event_exact`` — tier-1 block → event revision, projected
      from the stored run ``(id, version)`` lists.
    * ``proposal_event_exact`` — proposal revision → event revision, only
      for ``source_refs`` entries of ``type=execution`` that resolve to a
      source event in the same principal scope (the caller passes that
      scope's latest ``event_versions``).  Unresolvable execution refs
      are counted ``unavailable`` — never guessed via text/time matching.
    * ``proposal_v1_knowledge_existing`` — V1 proposal → knowledge node,
      an exact projection of existing ``proposal_knowledge_links`` rows
      whose endpoints both exist.  These are ``global`` bridge edges (V1
      tables have no principal scope) and never event bridges.

    Returns ``{"rows", "stats", "total", "cap", "overflow"}``.  Rows are
    deterministic in content and order; ``relation_id`` is assigned at
    persist time (scope-safe).  Candidates beyond ``rel_cap`` are dropped
    with an explicit per-rule overflow entry.
    """
    cap = RELATION_MAX if rel_cap is None else rel_cap
    stats: dict[str, dict[str, int]] = {
        rule: {"exact": 0, "unavailable": 0, "dropped": 0} for rule in RELATION_RULES
    }
    candidates: list[dict[str, Any]] = []

    # A) tier1 block -> event revision (exact projection of run payloads)
    for block in tier1_blocks:
        block_hash = str(block["content_hash"])
        for run in block["runs"]:
            for pair in run.get("id_versions", []):
                eid, ver = str(pair[0]), int(pair[1])
                candidates.append(
                    {
                        "rule": "block_event_exact",
                        "from_type": "tier1_block",
                        "from_id": block_hash,
                        "from_version": None,
                        "to_type": "event_revision",
                        "to_id": eid,
                        "to_version": ver,
                        "edge_scope": "principal",
                        "basis_ref": f"tier1:{block_hash}",
                    }
                )
                stats["block_event_exact"]["exact"] += 1

    # B) proposal revision -> event revision (same-scope execution refs only)
    for prop in sorted(proposals, key=lambda p: (str(p["id"]), int(p["version"]))):
        pid, pver = str(prop["id"]), int(prop["version"])
        refs = prop.get("refs") or []
        exec_refs = [r for r in refs if isinstance(r, dict) and r.get("type") == "execution"]
        for ref in sorted(exec_refs, key=lambda r: str(r.get("id", ""))):
            tid = str(ref.get("id", ""))
            if tid in event_versions:
                candidates.append(
                    {
                        "rule": "proposal_event_exact",
                        "from_type": "proposal_revision",
                        "from_id": pid,
                        "from_version": pver,
                        "to_type": "event_revision",
                        "to_id": tid,
                        "to_version": int(event_versions[tid]),
                        "edge_scope": "principal",
                        "basis_ref": f"proposal_revisions:{pid}#v{pver}/source_refs",
                    }
                )
                stats["proposal_event_exact"]["exact"] += 1
            else:
                stats["proposal_event_exact"]["unavailable"] += 1

    # C) V1 proposal -> knowledge_node (exact projection of existing links)
    for link in sorted(
        proposal_knowledge_links,
        key=lambda l: (str(l["proposal_id"]), str(l["knowledge_id"])),
    ):
        pid, kid = str(link["proposal_id"]), str(link["knowledge_id"])
        if pid in v1_proposal_ids and kid in knowledge_node_ids:
            candidates.append(
                {
                    "rule": "proposal_v1_knowledge_existing",
                    "from_type": "proposal_v1",
                    "from_id": pid,
                    "from_version": None,
                    "to_type": "knowledge_node",
                    "to_id": kid,
                    "to_version": None,
                    "edge_scope": "global",
                    "basis_ref": f"proposal_knowledge_links:{pid}->{kid}",
                }
            )
            stats["proposal_v1_knowledge_existing"]["exact"] += 1
        else:
            stats["proposal_v1_knowledge_existing"]["unavailable"] += 1

    # D) knowledge<->knowledge edges are deliberately NOT generated here:
    #    memory_edges stays the single source of truth and is reported as
    #    an existing count by the driver (future graph queries may union).

    rows: list[dict[str, Any]] = []
    dropped_by_rule: dict[str, int] = {}
    for cand in candidates:
        if len(rows) < cap:
            core = _relation_core(
                cand["rule"],
                cand["from_type"],
                cand["from_id"],
                cand["from_version"],
                cand["to_type"],
                cand["to_id"],
                cand["to_version"],
            )
            row = dict(cand)
            row["state"] = "candidate"
            # Every current rule is a lossless projection of an exact,
            # validated identifier reference.  Keep confidence explicit so
            # reviewers and future promotion code never have to infer it
            # from the rule name.
            row["confidence"] = 1.0
            row["basis_digest"] = hashlib.sha256(core.encode()).hexdigest()
            rows.append(row)
        else:
            dropped_by_rule[cand["rule"]] = dropped_by_rule.get(cand["rule"], 0) + 1
    overflow: list[dict[str, str]] = []
    for rule in RELATION_RULES:
        n = dropped_by_rule.get(rule, 0)
        stats[rule]["dropped"] = n
        if n:
            overflow.append({"kind": "relation_overflow", "ref": f"{rule}:{n}"})
    return {"rows": rows, "stats": stats, "total": len(rows), "cap": cap, "overflow": overflow}


# ---------------------------------------------------------------------------
# Persistence (additive; four derived tables; scope-isolated rebuild)
# ---------------------------------------------------------------------------

_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS compaction_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS compaction_blocks (
        content_hash TEXT NOT NULL,
        tier INTEGER NOT NULL,
        day TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        principal_workspace TEXT NOT NULL,
        principal_project TEXT NOT NULL,
        PRIMARY KEY (principal_workspace, principal_project, content_hash)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_compaction_blocks_scope
        ON compaction_blocks(principal_workspace, principal_project, tier, day)
    """,
    """
    CREATE TABLE IF NOT EXISTS compaction_review (
        id TEXT PRIMARY KEY,
        day TEXT NOT NULL,
        kind TEXT NOT NULL,
        ref TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'open',
        created_at TEXT NOT NULL,
        principal_workspace TEXT NOT NULL,
        principal_project TEXT NOT NULL,
        UNIQUE(principal_workspace, principal_project, day, kind, ref)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS compaction_relations (
        relation_id TEXT NOT NULL,
        rule TEXT NOT NULL,
        rule_version TEXT NOT NULL,
        from_type TEXT NOT NULL,
        from_id TEXT NOT NULL,
        from_version INTEGER,
        to_type TEXT NOT NULL,
        to_id TEXT NOT NULL,
        to_version INTEGER,
        edge_scope TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'candidate',
        confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
        basis_digest TEXT NOT NULL,
        basis_ref TEXT NOT NULL,
        created_at TEXT NOT NULL,
        principal_workspace TEXT NOT NULL,
        principal_project TEXT NOT NULL,
        PRIMARY KEY (principal_workspace, principal_project, relation_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_compaction_relations_from
        ON compaction_relations(principal_workspace, principal_project, from_type, from_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_compaction_relations_to
        ON compaction_relations(principal_workspace, principal_project, to_type, to_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_compaction_relations_rule
        ON compaction_relations(principal_workspace, principal_project, rule, state)
    """,
)

_EVENT_COLUMNS: tuple[str, ...] = (
    "id",
    "version",
    "project_id",
    "agent_id",
    "occurred_at",
    "action",
    "result",
    "payload_digest",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str | Path, *, read_only: bool) -> sqlite3.Connection:
    if read_only:
        # Read-only URI open: a dry-run physically cannot write, so the
        # schema cannot mutate — not even table creation.
        uri = Path(db_path).resolve().as_uri() + "?mode=ro"
        return sqlite3.connect(uri, uri=True)
    return sqlite3.connect(str(db_path))


def state_key(workspace: str, project: str) -> str:
    """Collision-free state key for a ``(workspace, project)`` scope.

    Uses a JSON array so scope names containing the delimiter character
    can never collide with another scope's pair.
    """
    return "compaction|" + canonical_json([workspace, project])


def _is_no_such_table(exc: sqlite3.OperationalError) -> bool:
    return "no such table" in str(exc).lower()


def _scope_rows(conn: sqlite3.Connection, workspace: str, project: str) -> list[dict[str, Any]]:
    """Read the principal's events only; scopes never mix.

    A missing ``source_events`` table is an empty input; any other
    ``OperationalError`` (e.g. schema drift — missing columns) is raised,
    never silently treated as empty.
    """
    try:
        cur = conn.execute(
            f"SELECT {', '.join(_EVENT_COLUMNS)} FROM source_events"
            " WHERE principal_workspace = ? AND principal_project = ?",
            (workspace, project),
        )
    except sqlite3.OperationalError as exc:
        if _is_no_such_table(exc):
            return []
        raise
    return [dict(zip(_EVENT_COLUMNS, row)) for row in cur.fetchall()]


def _load_relation_inputs(
    conn: sqlite3.Connection, workspace: str, project: str
) -> dict[str, Any]:
    """Load relation evidence for the scope.

    Missing source tables (``proposal_revisions`` / V1 tables) are
    tolerated as empty — a scope without proposals simply yields zero
    proposal edges.  Schema drift inside an existing table raises.
    """
    proposals: list[dict[str, Any]] = []
    try:
        cur = conn.execute(
            "SELECT id, version, source_refs FROM proposal_revisions"
            " WHERE principal_workspace = ? AND principal_project = ?",
            (workspace, project),
        )
        for pid, ver, refs_raw in cur.fetchall():
            try:
                refs = json.loads(refs_raw or "[]")
            except ValueError:
                refs = []
            if not isinstance(refs, list):
                refs = []
            proposals.append({"id": str(pid), "version": int(ver), "refs": refs})
    except sqlite3.OperationalError as exc:
        if not _is_no_such_table(exc):
            raise

    links: list[dict[str, str]] = []
    try:
        cur = conn.execute("SELECT proposal_id, knowledge_id FROM proposal_knowledge_links")
        links = [
            {"proposal_id": str(r[0]), "knowledge_id": str(r[1])} for r in cur.fetchall()
        ]
    except sqlite3.OperationalError as exc:
        if not _is_no_such_table(exc):
            raise

    v1_proposal_ids: set[str] = set()
    try:
        cur = conn.execute("SELECT proposal_id FROM proposals")
        v1_proposal_ids = {str(r[0]) for r in cur.fetchall()}
    except sqlite3.OperationalError as exc:
        if not _is_no_such_table(exc):
            raise

    knowledge_node_ids: set[str] = set()
    try:
        cur = conn.execute("SELECT id FROM knowledge_nodes")
        knowledge_node_ids = {str(r[0]) for r in cur.fetchall()}
    except sqlite3.OperationalError as exc:
        if not _is_no_such_table(exc):
            raise

    existing_knowledge_edges: int | None = None
    try:
        existing_knowledge_edges = int(
            conn.execute("SELECT COUNT(*) FROM memory_edges").fetchone()[0]
        )
    except sqlite3.OperationalError as exc:
        if not _is_no_such_table(exc):
            raise

    return {
        "proposals": proposals,
        "links": links,
        "v1_proposal_ids": v1_proposal_ids,
        "knowledge_node_ids": knowledge_node_ids,
        "existing_knowledge_edges": existing_knowledge_edges,
    }


def _basis_digest(
    result: Mapping[str, Any],
    relation_inputs: Mapping[str, Any],
    *,
    budget: int,
    horizon: str,
) -> str:
    """Digest of every input the derived rows depend on.

    Unchanged digest ⇒ a normal run is a physical noop.  Any new/edited
    event revision, proposal revision, or link changes it and triggers a
    deterministic rebuild of the scope.
    """
    payload = {
        "compactor": VERSION,
        "rules": RELATION_RULE_VERSION,
        "budget": budget,
        "horizon": horizon,
        "events": sorted([list(iv) for iv in result["provenance"]["id_versions"]]),
        "proposals": sorted(
            [
                [str(p["id"]), int(p["version"]), canonical_json(p.get("refs") or [])]
                for p in relation_inputs["proposals"]
            ]
        ),
        "links": sorted(
            [[str(l["proposal_id"]), str(l["knowledge_id"])] for l in relation_inputs["links"]]
        ),
        "v1_proposals": sorted(relation_inputs["v1_proposal_ids"]),
        "knowledge_nodes": sorted(relation_inputs["knowledge_node_ids"]),
        "existing_knowledge_edges": relation_inputs["existing_knowledge_edges"],
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def _load_basis(conn: sqlite3.Connection, workspace: str, project: str) -> str | None:
    try:
        row = conn.execute(
            "SELECT value FROM compaction_state WHERE key = ?",
            (state_key(workspace, project),),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        if _is_no_such_table(exc):
            return None
        raise
    if not row:
        return None
    try:
        data = json.loads(row[0])
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("compactor") != VERSION:
        return None  # version drift → rebuild
    return str(data.get("basis", "")) or None


def _default_horizon(rows: Sequence[Mapping[str, Any]]) -> str:
    """``max(occurred_at) − 48h`` over the scope's rows (protects active
    sessions).  Deterministic; identical for identical input."""
    horizon_ts = max(_epoch(str(r["occurred_at"])) for r in rows) - HORIZON_LAG_S
    return datetime.fromtimestamp(horizon_ts, tz=timezone.utc).isoformat()


def _digest_block(day: str, text: str, meta: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "digest/day",
        "compactor": VERSION,
        "day": day,
        "text": text,
        "meta": dict(meta),
    }
    payload["content_hash"] = content_hash({k: v for k, v in payload.items()})
    return payload


def _relation_id(
    workspace: str, project: str, row: Mapping[str, Any]
) -> str:
    return hashlib.sha256(
        canonical_json(
            [
                workspace,
                project,
                row["rule"],
                row["from_type"],
                str(row["from_id"]),
                row["from_version"],
                row["to_type"],
                str(row["to_id"]),
                row["to_version"],
            ]
        ).encode()
    ).hexdigest()


def _table_column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.OperationalError as exc:
        if _is_no_such_table(exc):
            return set()
        raise
    return {str(row[1]) for row in rows}


def _preserved_review_states(
    conn: sqlite3.Connection, workspace: str, project: str
) -> dict[str, str]:
    """Non-open states that a review rebuild must put back.

    The decisions sidecar is operator-owned. A missing table, a table
    with no id column, or a decided row that is still ``open`` contributes
    nothing. Review ids are the content hash of ``(workspace, project,
    day, kind, ref)``, so a decision recorded against that id still
    matches the row this rebuild is about to insert.
    """
    columns = _table_column_names(conn, "compaction_review_decisions")
    if "review_id" in columns:
        id_column = "review_id"
    elif "id" in columns:
        id_column = "id"
    else:
        return {}

    where = ""
    params: tuple[str, ...] = ()
    if "principal_workspace" in columns and "principal_project" in columns:
        where = " WHERE principal_workspace = ? AND principal_project = ?"
        params = (workspace, project)
    try:
        decided = {
            str(row[0])
            for row in conn.execute(
                f"SELECT {id_column} FROM compaction_review_decisions{where}",
                params,
            )
            if row[0] is not None
        }
    except sqlite3.OperationalError as exc:
        if _is_no_such_table(exc):
            return {}
        raise
    if not decided:
        return {}

    try:
        current = conn.execute(
            "SELECT id, state FROM compaction_review"
            " WHERE principal_workspace = ? AND principal_project = ?",
            (workspace, project),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _is_no_such_table(exc):
            return {}
        raise
    return {
        str(review_id): str(state)
        for review_id, state in current
        if str(review_id) in decided and str(state) != "open"
    }


def _persist(
    conn: sqlite3.Connection,
    result: Mapping[str, Any],
    relations: Mapping[str, Any],
    *,
    workspace: str,
    project: str,
    basis: str,
    budget: int = DEFAULT_CHAR_BUDGET,
    horizon: str = "",
) -> dict[str, int]:
    """Replace this scope's derived rows in a single transaction.

    The derived tables are rebuildable by definition: on every changed
    basis the scope's old ``compaction_blocks`` / ``compaction_review`` /
    ``compaction_relations`` rows are deleted and the freshly computed
    rows inserted, so no stale or duplicate derived rows can survive.
    No other table is ever written. Decided review states are read from
    ``compaction_review_decisions`` before the delete and applied to the
    new rows; the sidecar itself is left untouched.
    """
    cur = conn.cursor()
    for ddl in _DDL:
        cur.execute(ddl)
    cur.execute("BEGIN IMMEDIATE")
    scope = (workspace, project)
    preserved_review_states = _preserved_review_states(conn, workspace, project)
    try:
        cur.execute(
            "DELETE FROM compaction_blocks WHERE principal_workspace = ? AND principal_project = ?",
            scope,
        )
        cur.execute(
            "DELETE FROM compaction_review WHERE principal_workspace = ? AND principal_project = ?",
            scope,
        )
        cur.execute(
            "DELETE FROM compaction_relations WHERE principal_workspace = ? AND principal_project = ?",
            scope,
        )

        blocks_new = 0
        block_rows: list[tuple[int, str, dict[str, Any]]] = (
            [(1, b["t0"][:10], dict(b)) for b in result["tier1"]]
            + [(2, b["day"], dict(b)) for b in result["tier2"]]
            + [
                (3, d["day"], _digest_block(d["day"], d["text"], d["meta"]))
                for d in result["digests"]
            ]
        )
        for tier, day, payload in block_rows:
            cur.execute(
                "INSERT INTO compaction_blocks("
                "content_hash, tier, day, payload, created_at,"
                " principal_workspace, principal_project) VALUES (?,?,?,?,?,?,?)",
                (
                    payload["content_hash"],
                    tier,
                    day,
                    canonical_json(payload),
                    _now_iso(),
                    workspace,
                    project,
                ),
            )
            blocks_new += cur.rowcount

        review_new = 0
        review_rows = [
            (shadow.get("day", ""), shadow["kind"], shadow["ref"])
            for shadow in result["shadows"]
        ] + [
            ("all", entry["kind"], entry["ref"]) for entry in relations.get("overflow", [])
        ]
        for day, kind, ref in review_rows:
            review_id = hashlib.sha256(
                canonical_json([workspace, project, day, kind, ref]).encode()
            ).hexdigest()
            cur.execute(
                "INSERT INTO compaction_review("
                "id, day, kind, ref, state, created_at,"
                " principal_workspace, principal_project) VALUES (?,?,?,?,?,?,?,?)",
                (
                    review_id,
                    day,
                    kind,
                    ref,
                    preserved_review_states.get(review_id, "open"),
                    _now_iso(),
                    workspace,
                    project,
                ),
            )
            review_new += cur.rowcount

        relations_new = 0
        for row in relations.get("rows", []):
            cur.execute(
                "INSERT INTO compaction_relations("
                "relation_id, rule, rule_version, from_type, from_id, from_version,"
                " to_type, to_id, to_version, edge_scope, state, confidence, basis_digest,"
                " basis_ref, created_at, principal_workspace, principal_project)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    _relation_id(workspace, project, row),
                    row["rule"],
                    RELATION_RULE_VERSION,
                    row["from_type"],
                    row["from_id"],
                    row["from_version"],
                    row["to_type"],
                    row["to_id"],
                    row["to_version"],
                    row["edge_scope"],
                    row["state"],
                    row["confidence"],
                    row["basis_digest"],
                    row["basis_ref"],
                    _now_iso(),
                    workspace,
                    project,
                ),
            )
            relations_new += cur.rowcount

        cur.execute(
            "INSERT OR REPLACE INTO compaction_state(key, value) VALUES (?, ?)",
            (
                state_key(workspace, project),
                canonical_json(
                    {
                        "compactor": VERSION,
                        "basis": basis,
                        "budget": budget,
                        "horizon": horizon,
                    }
                ),
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"blocks_new": blocks_new, "review_new": review_new, "relations_new": relations_new}


def _summary(
    result: Mapping[str, Any],
    relation_inputs: Mapping[str, Any],
    relations: Mapping[str, Any],
    *,
    workspace: str,
    project: str,
    horizon: str,
    mode: str,
    full: bool,
    written: Mapping[str, int] | None,
    status_override: str | None = None,
) -> dict[str, Any]:
    block_hashes = sorted(
        [b["content_hash"] for b in result["tier1"]]
        + [b["content_hash"] for b in result["tier2"]]
        + [
            _digest_block(d["day"], d["text"], d["meta"])["content_hash"]
            for d in result["digests"]
        ]
    )
    return {
        "status": status_override or result["status"],
        "mode": mode,
        "dry_run": mode == "dry-run",
        "full": full,
        "workspace": workspace,
        "project": project,
        "horizon": horizon,
        "processed": result["processed"],
        "sessions": len(result["tier1"]),
        "blocks": len(block_hashes),
        "blocks_new": (written or {}).get("blocks_new", 0),
        "review_total": len(result["shadows"]) + len(relations.get("overflow", [])),
        "review_new": (written or {}).get("review_new", 0),
        "relations": {
            "total": relations["total"],
            "cap": relations["cap"],
            "by_rule": {rule: dict(stats) for rule, stats in relations["stats"].items()},
            "existing_knowledge_edges": relation_inputs["existing_knowledge_edges"],
        },
        "relations_new": (written or {}).get("relations_new", 0),
        "block_hashes": block_hashes,
        "digest_chars": {d["day"]: d["meta"]["chars"] for d in result["digests"]},
    }


def compact_experience(
    db_path: str | Path,
    *,
    workspace: str,
    project: str,
    dry_run: bool = False,
    full: bool = False,
    budget: int = DEFAULT_CHAR_BUDGET,
    horizon_iso: str | None = None,
) -> dict[str, Any]:
    """Compact the principal's ``source_events`` into shadow-only artifacts.

    Reads the scope's full event history (latest revision per id), rebuilds
    the window up to ``horizon`` (default: max event − 48h), derives
    candidate relations, and:

    * ``dry_run`` — opens the database read-only; zero writes, not even
      table creation.  The summary previews exactly what a write run
      would store (same content hashes).
    * normal — if the input basis digest is unchanged since the last run,
      the run is a physical noop.  Otherwise the scope's derived rows are
      replaced in one transaction (idempotent; ``full`` forces it).
      Only the four derived compaction tables are ever written.

    Schema drift (anything other than a missing source table) raises
    ``sqlite3.OperationalError`` — it is never reported as success.
    """
    db = Path(db_path)
    if not workspace or not project:
        return {
            "status": "error",
            "error": "workspace and project are required (principal scoping)",
        }
    if not db.exists():
        return {"status": "error", "error": f"database not found: {db}"}

    conn = _connect(db, read_only=dry_run)
    try:
        rows = _scope_rows(conn, workspace, project)
        horizon = (
            horizon_iso
            if horizon_iso is not None
            else (_default_horizon(rows) if rows else "")
        )
        result = compact_window(
            rows, horizon_iso=(horizon if horizon else None), budget=budget
        )

        relation_inputs = _load_relation_inputs(conn, workspace, project)
        event_versions = {
            str(iv[0]): int(iv[1]) for iv in result["provenance"]["id_versions"]
        }
        relations = build_relations(
            result["tier1"],
            event_versions=event_versions,
            proposals=relation_inputs["proposals"],
            proposal_knowledge_links=relation_inputs["links"],
            v1_proposal_ids=relation_inputs["v1_proposal_ids"],
            knowledge_node_ids=relation_inputs["knowledge_node_ids"],
        )
        basis = _basis_digest(result, relation_inputs, budget=budget, horizon=horizon)

        mode = "dry-run" if dry_run else "write"
        if dry_run:
            return _summary(
                result,
                relation_inputs,
                relations,
                workspace=workspace,
                project=project,
                horizon=horizon,
                mode=mode,
                full=full,
                written=None,
            )

        if result["status"] == "noop" and relations["total"] == 0 and not full:
            # Empty window and no relation candidates: nothing to derive.
            return _summary(
                result,
                relation_inputs,
                relations,
                workspace=workspace,
                project=project,
                horizon=horizon,
                mode=mode,
                full=full,
                written=None,
            )

        if not full and _load_basis(conn, workspace, project) == basis:
            return _summary(
                result,
                relation_inputs,
                relations,
                workspace=workspace,
                project=project,
                horizon=horizon,
                mode=mode,
                full=full,
                written=None,
                status_override="noop",
            )

        written = _persist(
            conn,
            result,
            relations,
            workspace=workspace,
            project=project,
            basis=basis,
            budget=budget,
            horizon=horizon,
        )
        summary = _summary(
            result,
            relation_inputs,
            relations,
            workspace=workspace,
            project=project,
            horizon=horizon,
            mode=mode,
            full=full,
            written=written,
        )
        summary["coverage"] = verify_coverage(result, rows)
        return summary
    finally:
        conn.close()


def compact_experience_cli(
    db_path: str | Path,
    *,
    workspace: str | None,
    project: str | None,
    dry_run: bool = False,
    full: bool = False,
    json_output: bool = False,
) -> int:
    """``compact-experience`` CLI entry point.  Returns a shell exit code."""
    if not workspace or not project:
        print(
            "compact-experience: --workspace and --project are required"
            " (or BRAIN_V2_WORKSPACE / BRAIN_V2_PROJECT)"
        )
        return 2
    try:
        summary = compact_experience(
            db_path,
            workspace=workspace,
            project=project,
            dry_run=dry_run,
            full=full,
        )
    except Exception as exc:  # schema drift etc.: explicit failure, nonzero exit
        print(f"compact-experience: error: {exc}", file=sys.stderr)
        return 1
    if json_output:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(
            f"experience compactor: status={summary['status']}"
            f" mode={'dry-run' if summary['dry_run'] else 'write'}"
            f" scope={workspace}/{project}"
        )
        print(
            f"processed={summary['processed']} sessions={summary['sessions']}"
            f" horizon={summary['horizon'] or '-'}"
        )
        print(
            f"blocks={summary['blocks']} blocks_new={summary['blocks_new']}"
            f" review_new={summary['review_new']}"
            f" (queue total this run: {summary['review_total']})"
        )
        rel = summary.get("relations", {})
        print(
            f"relations total={rel.get('total', 0)} new={summary.get('relations_new', 0)}"
            f" cap={rel.get('cap', 0)} (candidate-only; never written to the official graph)"
        )
        for rule, stats in sorted(rel.get("by_rule", {}).items()):
            print(
                f"relation {rule} exact={stats['exact']}"
                f" unavailable={stats['unavailable']} dropped={stats['dropped']}"
            )
        existing = rel.get("existing_knowledge_edges")
        print(f"existing kn-kn edges={existing if existing is not None else 'n/a'}")
        for day, chars in sorted(summary["digest_chars"].items()):
            print(f"digest day={day} chars={chars}")
    return 0 if summary["status"] in ("ok", "noop") else 1
