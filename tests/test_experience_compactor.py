"""Tests for the deterministic, shadow-only experience compactor (Phase 2).

Contract under test (see ``hermes/experience_compactor.py``):

* Pure compaction is a deterministic function of its input rows: same rows
  (in any order, in any timezone offsets) => byte-identical content-addressed
  blocks, ordered by UTC epoch -- never by raw timestamp strings.
* Only the **latest version** of each ``source_events`` id is compacted;
  provenance and relation endpoints carry ``(event_id, version)``.
* Explicit ``failed`` events form failure->recovery chains; only an
  **explicitly completed** event can close a chain -- ``unknown`` never
  recovers anything.  Unrecovered failures become review items, never
  silent losses; legacy hint-fields only ever become
  ``possible_failure_legacy`` shadows.
* The context digest respects a hard char budget that includes the header
  and is enforced on the **final redacted** text (redaction may grow text);
  a budget smaller than the header yields an explicitly truncated empty
  digest.
* Persistence is scope-isolated and rebuild-based: per
  ``(workspace, project)`` the derived tables
  (``compaction_state``, ``compaction_blocks``, ``compaction_review``,
  ``compaction_relations``) are deterministically rebuilt in one
  transaction when the input basis digest changes, and left untouched
  (noop) when it has not.  Identical block content in two scopes must be
  storable in both.  An operator-owned ``compaction_review_decisions``
  sidecar is never created or written; a rebuild restores each decided
  row's non-open state and leaves every other review row ``open``.
  Anything other than a missing table in
  ``source_events``/relation sources is a hard error, not an empty result.
* Shadow graph relations (``compaction_relations``) are candidate-only and
  derived from exact evidence only:
  ``tier1_block -> event_revision`` (run projections),
  ``proposal_revision -> event_revision`` (same-scope ``type=execution``
  source_refs only), and V1 ``proposal -> knowledge_node`` (exact
  projection of ``proposal_knowledge_links``, marked ``global`` bridge --
  never an event bridge).  knowledge<->knowledge edges are reported as an
  existing count only, never copied.  Overflow beyond the hard cap goes to
  ``compaction_review`` -- never silently truncated.
* ``dry_run`` is physically read-only: zero table creation, zero writes.

All fixtures are synthetic.  No production data or secrets are used.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hermes.event_store import EventStore, StaticPrincipalAdapter
from hermes.experience_compactor import (
    DEFAULT_CHAR_BUDGET,
    HORIZON_LAG_S,
    SESSION_GAP_S,
    compact_experience,
    compact_window,
    redact,
    verify_coverage,
)
from hermes.cli import main as cli_main


# ---------------------------------------------------------------------------
# Synthetic fixtures (deterministic; uuid5-derived ids)
# ---------------------------------------------------------------------------

WS = "ws-test"
PROJ = "proj-test"
ACTOR = "seeder"
HORIZON_ALL = "2026-06-05T00:00:00+00:00"
DAY1_END = "2026-06-01T23:59:59+00:00"

A_BASH = "codex PostToolUse Bash completed"
A_BASH_FAIL = "codex PostToolUse Bash failed"
A_READ = "codex PostToolUse Read completed"
A_DEPLOY_FAIL = "codex PostToolUse Deploy failed"
A_VISION = "codex PostToolUse vision_analyze completed"
A_HERMES = "hermes post_tool_call read_file completed"
A_CLAUDE = "claude-code PostToolUse Edit completed"

R_OK = "completed"
R_FAIL_RUNTIME = "failed; exit_code=1; error_type=RuntimeError; tail text"
R_FAIL_TIMEOUT = "failed; exit_code=2; error_type=TimeoutError; tail text"
R_LEGACY_ISERROR = "completed; response fields: isError"
R_LEGACY_FNF = "completed; response fields: FileNotFound"


def _rid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "brain-compactor-synthetic:" + name))


def _row(name: str, dt: datetime, action: str, result: str, agent: str = "codex") -> dict:
    return {
        "id": _rid(name),
        "version": 1,
        "project_id": PROJ,
        "agent_id": agent,
        "occurred_at": dt.isoformat(),
        "action": action,
        "result": result,
        "payload_digest": "synthetic-" + name,
    }


def _spec() -> list[dict]:
    """133 synthetic rows: 2 sessions on day 1, 1 session on day 2."""
    rows: list[dict] = []
    base = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    # session 1 (continuous, <= 600s gaps): 3 unrelated + 120 mega-run + 2 fails + recovery
    for i in range(3):
        rows.append(_row(f"b{i}", base + timedelta(seconds=10 * i), "codex PostToolUse Grep completed", R_OK))
    mega_start = datetime(2026, 6, 1, 9, 1, tzinfo=timezone.utc)
    for i in range(120):
        rows.append(_row(f"m{i:03d}", mega_start + timedelta(seconds=5 * i), A_BASH, R_OK))
    rows.append(_row("f1", datetime(2026, 6, 1, 9, 12, tzinfo=timezone.utc), A_BASH_FAIL, R_FAIL_RUNTIME))
    rows.append(_row("f2", datetime(2026, 6, 1, 9, 13, tzinfo=timezone.utc), A_BASH_FAIL, R_FAIL_RUNTIME))
    rows.append(_row("r1", datetime(2026, 6, 1, 9, 14, tzinfo=timezone.utc), A_BASH, R_OK))
    # session 2 (51-minute idle gap from r1)
    rows.append(_row("u1", datetime(2026, 6, 1, 10, 5, tzinfo=timezone.utc), A_DEPLOY_FAIL, R_FAIL_TIMEOUT))
    rows.append(_row("l1", datetime(2026, 6, 1, 10, 6, tzinfo=timezone.utc), A_READ, R_LEGACY_ISERROR))
    rows.append(_row("l2", datetime(2026, 6, 1, 10, 6, 30, tzinfo=timezone.utc), A_READ, R_LEGACY_FNF))
    rows.append(_row("v1", datetime(2026, 6, 1, 10, 10, tzinfo=timezone.utc), A_VISION, R_OK))
    # session 3 on day 2, different agent
    day2 = datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)
    for i, sec in enumerate((0, 30, 60)):
        rows.append(
            _row(
                f"d{i}",
                day2 + timedelta(seconds=sec),
                A_HERMES,
                R_OK,
                agent="hermes",
            )
        )
    return rows


def _spec_with_tail() -> list[dict]:
    """_spec() plus a day-3 tail (2 events) used to exercise the 48h horizon lag."""
    return _spec() + [
        _row("t0", datetime(2026, 6, 4, 9, 4, 30, tzinfo=timezone.utc), A_CLAUDE, R_OK, agent="claude-code"),
        _row("t1", datetime(2026, 6, 4, 9, 5, 0, tzinfo=timezone.utc), A_CLAUDE, R_OK, agent="claude-code"),
    ]


def _spec_ids(rows: list[dict]) -> set[str]:
    return {r["id"] for r in rows}


def _seed_db(
    tmp_path: Path,
    rows: list[dict],
    *,
    ws: str = WS,
    proj: str = PROJ,
    db_name: str = "hermes.sqlite3",
) -> Path:
    """Seed synthetic rows through the real EventStore ingest path."""
    db = tmp_path / db_name
    store = EventStore(db, principal=StaticPrincipalAdapter(actor=ACTOR, workspace=ws, project=proj))
    for r in rows:
        store.record_event(
            id=r["id"],
            project_id=proj,
            agent_id=r["agent_id"],
            occurred_at=datetime.fromisoformat(r["occurred_at"]),
            action=r["action"],
            result=r["result"],
        )
    store._conn.close()
    return db


def _insert_event_row(
    db: Path,
    name: str,
    *,
    ws: str,
    proj: str,
    dt: datetime,
    action: str = A_BASH,
    result: str = R_OK,
    version: int = 1,
    agent: str = "codex",
) -> str:
    """Direct SQL insert (bypasses EventStore UTC normalisation and scoping)."""
    eid = _rid(name)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO source_events("
            " id, version, project_id, agent_id, occurred_at, client_digest,"
            " action, result, origin, classification, payload_digest,"
            " principal_actor, principal_workspace, principal_project,"
            " received_at, source_refs) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                eid, version, proj, agent, dt.isoformat(), "",
                action, result, "hook", "production", "synthetic-" + name,
                ACTOR, ws, proj, "2026-06-01T00:00:00+00:00", "[]",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return eid


def _insert_proposal_row(
    db: Path,
    pid: str,
    *,
    ws: str,
    proj: str,
    refs: list[dict],
    version: int = 1,
) -> None:
    """Direct SQL proposal revision (allows refs EventStore would reject)."""
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO proposal_revisions("
            " id, version, project_id, agent_id, occurred_at, action, result,"
            " lesson, draft, source_refs, workflow_state, payload_digest,"
            " principal_actor, principal_workspace, principal_project, received_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                pid, version, proj, "codex", "2026-06-01T10:00:00+00:00",
                "codex ProposalCreate proposal created", "ready", None, 0,
                json.dumps(refs), "ready", "digest-" + pid,
                ACTOR, ws, proj, "2026-06-01T10:00:01+00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _add_v1_graph(
    db: Path,
    *,
    proposals: list[str] = (),
    nodes: list[str] = (),
    links: list[tuple[str, str]] = (),
    edges: list[tuple[str, str, str]] = (),
) -> None:
    """Create the V1 tables via the real repository and seed graph rows."""
    from hermes.repository import HermesRepository

    HermesRepository(db)  # additive schema creation only
    now = "2026-06-01T00:00:00+00:00"
    conn = sqlite3.connect(str(db))
    try:
        for pid in proposals:
            conn.execute(
                "INSERT OR REPLACE INTO proposals("
                " proposal_id, source_agent, source_host, created_at, project_key,"
                " category, risk_level, summary, observation, why_it_matters,"
                " suggested_memory, scope, evidence, state, semantic_hash, inserted_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid, "codex", "h", now, "proj", "lesson", "low",
                 "s", "o", "w", "m", "project", "[]", "open", "sem-" + pid, now),
            )
        for nid in nodes:
            conn.execute(
                "INSERT OR REPLACE INTO knowledge_nodes("
                " id, content, summary, source, created_at)"
                " VALUES (?,?,?,?,?)",
                (nid, "content " + nid, "summary " + nid, "proposal", now),
            )
        for pid, kid in links:
            conn.execute(
                "INSERT OR REPLACE INTO proposal_knowledge_links("
                " proposal_id, knowledge_id, sync_action, synced_at) VALUES (?,?,?,?)",
                (pid, kid, "created", now),
            )
        for a, b, etype in edges:
            conn.execute(
                "INSERT OR REPLACE INTO memory_edges("
                " from_id, to_id, edge_type, created_at) VALUES (?,?,?,?)",
                (a, b, etype, now),
            )
        conn.commit()
    finally:
        conn.close()


def _table_names(db: Path) -> list[str]:
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def _table_counts(db: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db))
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {n: conn.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in names}
    finally:
        conn.close()


def _blocks(db: Path, tier: int | None = None) -> list[dict]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        if tier is None:
            rows = conn.execute(
                "SELECT * FROM compaction_blocks"
                " ORDER BY principal_workspace, principal_project, content_hash"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM compaction_blocks WHERE tier=?"
                " ORDER BY principal_workspace, principal_project, content_hash",
                (tier,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _relations(db: Path, ws: str = WS, proj: str = PROJ) -> list[dict]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM compaction_relations"
            " WHERE principal_workspace=? AND principal_project=?"
            " ORDER BY rule, from_type, from_id, from_version, to_type, to_id, to_version",
            (ws, proj),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _state_keys(db: Path) -> list[str]:
    conn = sqlite3.connect(str(db))
    try:
        return sorted(r[0] for r in conn.execute("SELECT key FROM compaction_state").fetchall())
    finally:
        conn.close()


def _block_event_ids(db: Path, ws: str = WS, proj: str = PROJ) -> set[str]:
    """Every event id carried verbatim inside stored tier-1 run payloads."""
    ids: set[str] = set()
    for block in _blocks(db, tier=1):
        if block["principal_workspace"] != ws or block["principal_project"] != proj:
            continue
        payload = json.loads(block["payload"])
        for run in payload["runs"]:
            ids.update(run["ids"])
    return ids


# ---------------------------------------------------------------------------
# Pure compaction: determinism, versions, timezones, folding, chains
# ---------------------------------------------------------------------------


def test_pure_compaction_is_deterministic_and_order_independent() -> None:
    rows = _spec()
    a = compact_window(rows, horizon_iso=HORIZON_ALL)
    b = compact_window(list(reversed(rows)), horizon_iso=HORIZON_ALL)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert [t["content_hash"] for t in a["tier2"]] == [t["content_hash"] for t in b["tier2"]]
    assert [t["content_hash"] for t in a["tier1"]] == [t["content_hash"] for t in b["tier1"]]


def test_exact_source_ids_and_versions_preserved() -> None:
    rows = _spec()
    r = compact_window(rows, horizon_iso=HORIZON_ALL)
    cov = verify_coverage(r, rows)
    assert cov["ids_exact"] is True, cov
    assert cov["counts_conserve"] is True, cov
    assert {i for i, _ in r["provenance"]["id_versions"]} == _spec_ids(rows)
    assert dict(r["provenance"]["id_versions"]) == {row["id"]: 1 for row in rows}
    tier1_ids: set[str] = set()
    for block in r["tier1"]:
        for run in block["runs"]:
            tier1_ids.update(run["ids"])
            assert len(run["id_versions"]) == len(run["ids"])
            assert [i for i, _ in run["id_versions"]] == run["ids"]
    assert tier1_ids == _spec_ids(rows)


def test_only_latest_version_per_event_id_is_compacted() -> None:
    rows = _spec()
    v2 = dict(rows[0])
    v2["version"] = 2
    v2["result"] = R_FAIL_RUNTIME
    v2["payload_digest"] = "synthetic-b0-v2"
    r = compact_window(rows + [v2], horizon_iso=HORIZON_ALL)
    # 133 events, not 134: v1 of the revised id must be superseded
    assert r["processed"] == 133
    assert dict(r["provenance"]["id_versions"])[_rid("b0")] == 2
    seen: dict[str, int] = {}
    for block in r["tier1"]:
        for run in block["runs"]:
            for eid, ver in run["id_versions"]:
                seen[eid] = ver
    assert seen[_rid("b0")] == 2


def test_mixed_timezone_rows_ordered_by_utc_epoch() -> None:
    def raw(name: str, iso: str, agent: str = "codex") -> dict:
        return {
            "id": _rid(name), "version": 1, "project_id": PROJ, "agent_id": agent,
            "occurred_at": iso, "action": A_BASH, "result": R_OK,
            "payload_digest": "synthetic-" + name,
        }

    # All three instants within one 30-min session, and the raw-string
    # lexical order is the EXACT REVERSE of the UTC order (a naive string
    # sort would fold the run backwards).
    rows = [
        raw("tz-p8", "2026-06-01T09:10:00+08:00"),  # 01:10Z -- earliest instant, lexically LAST
        raw("tz-u", "2026-06-01T01:20:00+00:00"),   # 01:20Z -- middle
        raw("tz-n4", "2026-05-31T21:25:00-04:00"),  # 01:25Z -- latest instant, lexically FIRST
    ]
    r = compact_window(rows, horizon_iso=HORIZON_ALL)
    assert [i for i, _ in r["provenance"]["id_versions"]] == [
        _rid("tz-p8"), _rid("tz-u"), _rid("tz-n4"),
    ]
    run = r["tier1"][0]["runs"][0]  # one session, one run: identical signature
    assert run["first_id"] == _rid("tz-p8")
    assert run["last_id"] == _rid("tz-n4")
    assert run["ids"] == [_rid("tz-p8"), _rid("tz-u"), _rid("tz-n4")]
    # the horizon is compared on the UTC instant, not the raw string
    h = compact_window(rows, horizon_iso="2026-06-01T01:22:00+00:00")
    assert [i for i, _ in h["provenance"]["id_versions"]] == [_rid("tz-p8"), _rid("tz-u")]


def test_run_folding_mega_run_single_block() -> None:
    rows = _spec()
    r = compact_window(rows, horizon_iso=HORIZON_ALL)
    mega_ids = {_rid(f"m{i:03d}") for i in range(120)}
    mega_runs = [
        run
        for block in r["tier1"]
        for run in block["runs"]
        if set(run["ids"]) == mega_ids
    ]
    assert len(mega_runs) == 1
    run = mega_runs[0]
    assert run["count"] == 120
    assert len(set(run["ids"])) == 120
    assert run["first_id"] == _rid("m000")
    assert run["last_id"] == _rid("m119")


def test_sessionization_splits_on_idle_gap() -> None:
    rows = _spec()
    a = compact_window(rows, horizon_iso=HORIZON_ALL)
    b = compact_window(list(reversed(rows)), horizon_iso=HORIZON_ALL)
    assert len(a["tier1"]) == 3
    assert [t["session_id"] for t in a["tier1"]] == [t["session_id"] for t in b["tier1"]]
    counts = sorted(t["n_events"] for t in a["tier1"])
    assert counts == [3, 4, 126]


def test_explicit_failure_recovery_chain() -> None:
    rows = _spec()
    r = compact_window(rows, horizon_iso=HORIZON_ALL)
    chains = [c for b in r["tier1"] for c in b["chains"]]
    assert len(chains) == 1
    chain = chains[0]
    assert chain["tool"] == "Bash"
    assert chain["fail_ids"] == [_rid("f1"), _rid("f2")]
    assert chain["recovery_id"] == _rid("r1")
    assert chain["error_types"] == ["RuntimeError"]
    assert chain["duration_s"] is not None and chain["duration_s"] > 0


def test_recovery_requires_explicit_completed_unknown_never_recovers() -> None:
    base = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    rows = [
        _row("c-f1", base, A_BASH_FAIL, R_FAIL_RUNTIME),
        _row("c-u1", base + timedelta(seconds=120), "codex PostToolUse Bash", "weird adapter output"),
        _row("c-f2", base + timedelta(seconds=5 * 60), A_BASH_FAIL, R_FAIL_TIMEOUT),
        _row("c-u2", base + timedelta(seconds=6 * 60), "codex PostToolUse Bash", "still unknown shape"),
    ]
    r = compact_window(rows, horizon_iso=HORIZON_ALL)
    chains = [c for b in r["tier1"] for c in b["chains"]]
    assert chains == [], "unknown-status events must never close a failed chain"
    unrec = {s["ref"] for s in r["shadows"] if s["kind"] == "unrecovered_failure"}
    assert unrec == {_rid("c-f1"), _rid("c-f2")}

    rows2 = rows + [_row("c-r", base + timedelta(seconds=10 * 60), A_BASH, R_OK)]
    r2 = compact_window(rows2, horizon_iso=HORIZON_ALL)
    chains2 = [c for b in r2["tier1"] for c in b["chains"]]
    assert len(chains2) == 1
    assert chains2[0]["recovery_id"] == _rid("c-r")
    assert chains2[0]["fail_ids"] == [_rid("c-f1"), _rid("c-f2")]


def test_unrecovered_failure_is_shadow_not_loss() -> None:
    rows = _spec()
    r = compact_window(rows, horizon_iso=HORIZON_ALL)
    unrec = [s for s in r["shadows"] if s["kind"] == "unrecovered_failure"]
    assert len(unrec) == 1
    assert unrec[0]["ref"] == _rid("u1")


def test_legacy_possible_failure_shadow_never_chain() -> None:
    rows = _spec()
    r = compact_window(rows, horizon_iso=HORIZON_ALL)
    legacy = [s for s in r["shadows"] if s["kind"] == "possible_failure_legacy"]
    assert {s["ref"] for s in legacy} == {_rid("l1"), _rid("l2")}
    explicit_fail_ids = {_rid("f1"), _rid("f2"), _rid("u1")}
    for b in r["tier1"]:
        for chain in b["chains"]:
            assert set(chain["fail_ids"]) <= explicit_fail_ids


def test_unknown_status_never_becomes_failure() -> None:
    row = dict(_spec()[0])
    row["id"] = _rid("unknown-status")
    row["action"] = "codex PostToolUse Bash"  # no status token
    row["result"] = "weird new adapter output shape"
    r = compact_window([row], horizon_iso=HORIZON_ALL)
    assert r["processed"] == 1
    assert not any(b["chains"] for b in r["tier1"])
    assert not any(s["kind"] == "unrecovered_failure" for s in r["shadows"])


# ---------------------------------------------------------------------------
# Budget + redaction (final text <= budget, header counted, growth accounted)
# ---------------------------------------------------------------------------


def test_char_budget_enforced_review_priority_and_token_estimate() -> None:
    rows = _spec()
    tight = compact_window(rows, horizon_iso=HORIZON_ALL, budget=600)
    assert tight["digests"], "expected per-day digests"
    by_day = {d["day"]: d for d in tight["digests"]}
    for d in tight["digests"]:
        assert len(d["text"]) <= 600
        assert d["meta"]["token_estimate"] == d["meta"]["chars"] // 4
    heavy = by_day["2026-06-01"]
    assert heavy["meta"]["truncated"] is True
    assert heavy["meta"]["overflow_keys"]
    first_lines = heavy["text"].splitlines()
    assert any(line.startswith("REVIEW") for line in first_lines[:6]), first_lines[:6]
    assert by_day["2026-06-02"]["meta"]["chars"] <= 600


def test_tiny_budget_header_counted_defined_behavior() -> None:
    rows = _spec()
    for budget in (0, 5, 20):
        r = compact_window(rows, horizon_iso=HORIZON_ALL, budget=budget)
        for d in r["digests"]:
            assert len(d["text"]) <= budget
            assert d["meta"]["truncated"] is True
            assert "header" in d["meta"]["overflow_keys"]
    # a budget below the header length yields an explicitly empty digest
    r0 = compact_window(rows, horizon_iso=HORIZON_ALL, budget=8)
    assert all(d["text"] == "" for d in r0["digests"])


def test_budget_holds_after_redaction_growth() -> None:
    # Redaction can GROW text (short email "a@b.co" -> "<email>").  The
    # budget must be enforced on the final redacted text.
    base = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    rows: list[dict] = []
    for i in range(3):
        rows.append(_row(f"em{i}", base + timedelta(hours=i), A_BASH, R_OK, agent="a@b.co"))
    full = compact_window(rows, horizon_iso=HORIZON_ALL, budget=DEFAULT_CHAR_BUDGET)
    full_len = max(len(d["text"]) for d in full["digests"])
    assert full_len > 0
    for budget in range(30, full_len + 5, 7):
        r = compact_window(rows, horizon_iso=HORIZON_ALL, budget=budget)
        for d in r["digests"]:
            assert len(d["text"]) <= budget, (budget, len(d["text"]))
            assert "<email>" in d["text"] or d["meta"]["truncated"]


def test_redaction_masks_secret_shapes_without_leaking_values() -> None:
    cases = {
        "bearer abcdef1234567890": "<bearer>",
        "api_key=livetest123456": "<secret>",
        "«redacted:sk-abcdef0123456789»": "<key>",
        "contact ops@example.com now": "<email>",
        "connect 10.1.2.3:5432": "<ip>",
        "open /home/secretuser/notes.txt": "~/notes.txt",
        "/root/ops/brain/x.py": "~/ops/brain/x.py",
    }
    for raw, expected in cases.items():
        out, hits = redact(raw)
        assert expected in out, (raw, out)
        assert hits and all(set(h) == {"kind"} for h in hits), "hits must carry kind only, never values"

    rows = [dict(_spec()[0])]
    rows[0] = dict(rows[0])
    rows[0]["result"] = "completed; api_key=livetest123456"
    r = compact_window(rows, horizon_iso=HORIZON_ALL)
    for d in r["digests"]:
        assert "livetest123456" not in d["text"]


def test_rare_signature_shadow_but_mega_run_normal() -> None:
    rows = _spec()
    r = compact_window(rows, horizon_iso=HORIZON_ALL)
    rare_refs = [s["ref"] for s in r["shadows"] if s["kind"] == "rare_signature"]
    assert any("vision_analyze" in ref for ref in rare_refs), rare_refs
    assert len(r["provenance"]["ids"]) == r["processed"]
    assert not any("run" in s["kind"] for s in r["shadows"])


def test_horizon_limits_window_pure() -> None:
    rows = _spec()
    r = compact_window(rows, horizon_iso=DAY1_END)
    day1_ids = {row["id"] for row in rows if row["occurred_at"] <= DAY1_END}
    assert r["processed"] == len(day1_ids) == 130
    assert set(r["provenance"]["ids"]) == day1_ids


# ---------------------------------------------------------------------------
# Pure relation building (shadow graph candidates)
# ---------------------------------------------------------------------------


def test_pure_relations_exact_unavailable_and_typed_endpoints() -> None:
    from hermes.experience_compactor import build_relations

    rows = _spec()
    r = compact_window(rows, horizon_iso=HORIZON_ALL)
    event_versions = {row["id"]: row["version"] for row in rows}
    proposals = [
        {
            "id": _rid("p1"),
            "version": 1,
            "refs": [
                {"type": "execution", "id": _rid("f1")},
                {"type": "execution", "id": _rid("no-such-event")},
                {"type": "document", "id": _rid("doc-1")},  # not an event ref
            ],
        },
        {"id": _rid("p2"), "version": 3, "refs": []},
    ]
    out = build_relations(
        r["tier1"],
        event_versions=event_versions,
        proposals=proposals,
        proposal_knowledge_links=[
            {"proposal_id": "pv1", "knowledge_id": "k1"},
            {"proposal_id": "pv-gone", "knowledge_id": "k1"},
        ],
        v1_proposal_ids={"pv1"},
        knowledge_node_ids={"k1", "k2"},
    )
    assert out["total"] == 133 + 1 + 1
    stats = out["stats"]
    assert stats["block_event_exact"] == {"exact": 133, "unavailable": 0, "dropped": 0}
    assert stats["proposal_event_exact"] == {"exact": 1, "unavailable": 1, "dropped": 0}
    assert stats["proposal_v1_knowledge_existing"] == {"exact": 1, "unavailable": 1, "dropped": 0}

    be = [row for row in out["rows"] if row["rule"] == "block_event_exact"]
    assert {(row["to_id"], row["to_version"]) for row in be} == set(event_versions.items())
    assert all(row["from_type"] == "tier1_block" for row in be)
    assert all(row["to_type"] == "event_revision" for row in be)
    assert all(row["state"] == "candidate" and row["edge_scope"] == "principal" for row in be)
    assert all(row["confidence"] == 1.0 for row in out["rows"])
    assert all(row["basis_ref"].startswith("tier1:") and row["basis_digest"] for row in be)

    pe = [row for row in out["rows"] if row["rule"] == "proposal_event_exact"]
    assert len(pe) == 1
    assert pe[0]["from_id"] == _rid("p1") and pe[0]["from_version"] == 1
    assert pe[0]["to_id"] == _rid("f1") and pe[0]["to_version"] == 1
    assert "proposal_revisions" in pe[0]["basis_ref"]

    c = [row for row in out["rows"] if row["rule"] == "proposal_v1_knowledge_existing"]
    assert len(c) == 1
    assert c[0]["from_id"] == "pv1" and c[0]["to_id"] == "k1"
    assert c[0]["to_type"] == "knowledge_node"
    assert c[0]["edge_scope"] == "global"

    # knowledge<->knowledge edges are never generated
    assert not any(row["from_type"] == "knowledge_node" for row in out["rows"])


def test_relation_overflow_is_explicit_never_silent() -> None:
    from hermes.experience_compactor import build_relations

    rows = _spec()[:20]
    r = compact_window(rows, horizon_iso=HORIZON_ALL)
    out = build_relations(
        r["tier1"],
        event_versions={row["id"]: row["version"] for row in rows},
        proposals=[],
        proposal_knowledge_links=[],
        v1_proposal_ids=set(),
        knowledge_node_ids=set(),
        rel_cap=5,
    )
    assert out["total"] == 5
    assert out["stats"]["block_event_exact"]["dropped"] == 15
    assert {"kind": "relation_overflow", "ref": "block_event_exact:15"} in out["overflow"]


# ---------------------------------------------------------------------------
# Persistence driver: scope isolation, rebuilds, idempotency, drift errors
# ---------------------------------------------------------------------------

COMPACT_TABLES = {"compaction_state", "compaction_blocks", "compaction_review", "compaction_relations"}


def test_dry_run_makes_zero_db_writes(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, _spec())
    tables_before = _table_names(db)
    counts_before = _table_counts(db)

    summary = compact_experience(db, workspace=WS, project=PROJ, dry_run=True, horizon_iso=HORIZON_ALL)

    assert summary["mode"] == "dry-run"
    assert summary["processed"] == 133
    assert summary["blocks_new"] == 0 and summary["review_new"] == 0
    assert summary.get("relations_new", 0) == 0
    assert summary["relations"]["by_rule"]["block_event_exact"]["exact"] == 133
    assert _table_names(db) == tables_before
    assert not COMPACT_TABLES & set(tables_before)
    assert _table_counts(db) == counts_before


def test_normal_run_writes_exactly_four_new_tables(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, _spec())
    before = set(_table_names(db))
    source_events_before = _table_counts(db)["source_events"]

    summary = compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)

    assert summary["status"] == "ok"
    after = set(_table_names(db))
    assert after - before == COMPACT_TABLES
    counts = _table_counts(db)
    assert counts["source_events"] == source_events_before == 133
    assert counts["compaction_blocks"] == summary["blocks"]
    assert counts["compaction_review"] == summary["review_total"]
    assert counts["compaction_relations"] == summary["relations"]["total"]


def test_tier1_payloads_in_db_preserve_exact_ids_and_versions(tmp_path: Path) -> None:
    rows = _spec()
    db = _seed_db(tmp_path, rows)
    compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)

    assert _block_event_ids(db) == _spec_ids(rows)
    conn = sqlite3.connect(str(db))
    try:
        review = conn.execute(
            "SELECT kind, ref FROM compaction_review WHERE kind IN ('unrecovered_failure','possible_failure_legacy')"
        ).fetchall()
    finally:
        conn.close()
    assert ("unrecovered_failure", _rid("u1")) in review
    assert {ref for kind, ref in review if kind == "possible_failure_legacy"} == {_rid("l1"), _rid("l2")}


def test_review_decision_survives_compactor_rebuild(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, _spec())
    compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, day, kind, ref FROM compaction_review ORDER BY id LIMIT 1"
        ).fetchone()
        assert row is not None
        conn.execute(
            """
            CREATE TABLE compaction_review_decisions (
                id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL UNIQUE,
                day TEXT NOT NULL,
                kind TEXT NOT NULL,
                ref TEXT NOT NULL,
                decision TEXT NOT NULL,
                decided_by TEXT NOT NULL,
                decided_at TEXT NOT NULL,
                basis TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "UPDATE compaction_review SET state='resolved' WHERE id=?",
            (row["id"],),
        )
        conn.execute(
            """
            INSERT INTO compaction_review_decisions
                (id, review_id, day, kind, ref, decision, decided_by, decided_at, basis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("decision-1", row["id"], row["day"], row["kind"], row["ref"],
             "acknowledged", "operator", "2026-10-21T00:00:00+00:00", "test"),
        )
        conn.commit()
    finally:
        conn.close()

    compact_experience(
        db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL, full=True
    )
    conn = sqlite3.connect(str(db))
    try:
        state = conn.execute(
            "SELECT state FROM compaction_review WHERE id=?", (row["id"],)
        ).fetchone()[0]
        assert state == "resolved"
        others = conn.execute(
            "SELECT state FROM compaction_review WHERE id != ?", (row["id"],)
        ).fetchall()
        assert others
        assert {item[0] for item in others} == {"open"}
        assert conn.execute(
            "SELECT count(*) FROM compaction_review_decisions"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_repeated_normal_run_is_noop_with_identical_rowcounts(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, _spec())
    first = compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)
    counts_after_first = _table_counts(db)
    assert first["status"] == "ok" and first["processed"] == 133
    assert first["blocks_new"] > 0

    second = compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)

    assert second["status"] == "noop"
    assert second["blocks_new"] == 0 and second["review_new"] == 0
    assert second.get("relations_new", -1) == 0
    assert _table_counts(db) == counts_after_first


def test_full_flag_is_idempotent(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, _spec())
    first = compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)
    counts_first = _table_counts(db)
    hashes_first = sorted(b["content_hash"] for b in _blocks(db))

    full = compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL, full=True)

    assert full["status"] == "ok"
    assert _table_counts(db) == counts_first
    assert sorted(b["content_hash"] for b in _blocks(db)) == hashes_first


def test_rebuild_after_event_revision_replaces_stale_no_duplicates(tmp_path: Path) -> None:
    rows = _spec()
    db = _seed_db(tmp_path, rows)
    first = compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)
    assert first["status"] == "ok" and first["processed"] == 133

    store = EventStore(db, principal=StaticPrincipalAdapter(actor=ACTOR, workspace=WS, project=PROJ))
    # f1 revised to v2 (payload differs), plus one brand-new event
    store.record_event(
        id=_rid("f1"), project_id=PROJ, agent_id="codex",
        occurred_at=datetime(2026, 6, 1, 9, 12, tzinfo=timezone.utc),
        action=A_BASH, result=R_OK,
    )
    store.record_event(
        id=_rid("new1"), project_id=PROJ, agent_id="codex",
        occurred_at=datetime(2026, 6, 1, 9, 15, tzinfo=timezone.utc),
        action=A_READ, result=R_OK,
    )
    store._conn.close()

    second = compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)
    assert second["status"] == "ok" and second["processed"] == 134

    rel = _relations(db)
    be = [r for r in rel if r["rule"] == "block_event_exact"]
    assert len(be) == 134
    to_versions = {(r["to_id"], r["to_version"]) for r in be}
    assert (_rid("f1"), 2) in to_versions
    assert (_rid("f1"), 1) not in to_versions, "stale v1 relation must not survive the rebuild"
    assert _rid("new1") in {i for i, _ in to_versions}

    # no stale or duplicate tier-1 blocks: exactly this rebuild's sessions
    t1 = _blocks(db, tier=1)
    assert len(t1) == len({b["content_hash"] for b in t1}) == second["sessions"] == 3
    for block in t1:
        payload = json.loads(block["payload"])
        for run in payload["runs"]:
            versions = dict(run["id_versions"])
            assert versions.get(_rid("f1"), 2) == 2


def test_identical_block_content_is_storable_in_two_scopes(tmp_path: Path) -> None:
    from hermes.experience_compactor import _persist, compact_window

    rows = _spec()[:10]
    db = _seed_db(tmp_path, rows)
    result = compact_window(rows, horizon_iso=HORIZON_ALL)
    empty_relations = {
        "rows": [],
        "stats": {},
        "total": 0,
        "cap": 0,
        "overflow": [],
    }
    conn = sqlite3.connect(str(db))
    try:
        _persist(conn, result, empty_relations, workspace="ws-1", project="p-1",
                 basis="b-1", budget=DEFAULT_CHAR_BUDGET, horizon=HORIZON_ALL)
        _persist(conn, result, empty_relations, workspace="ws-2", project="p-2",
                 basis="b-2", budget=DEFAULT_CHAR_BUDGET, horizon=HORIZON_ALL)
        grouped = conn.execute(
            "SELECT principal_workspace, principal_project, COUNT(*) FROM compaction_blocks"
            " GROUP BY principal_workspace, principal_project ORDER BY 1, 2"
        ).fetchall()
    finally:
        conn.close()
    n_blocks = len(result["tier1"]) + len(result["tier2"]) + len(result["digests"])
    assert [(g[0], g[1], g[2]) for g in grouped] == [
        ("ws-1", "p-1", n_blocks),
        ("ws-2", "p-2", n_blocks),
    ], "identical content must be storable per scope, not deduped away by a global hash PK"


def test_state_key_is_collision_free(tmp_path: Path) -> None:
    from hermes.experience_compactor import state_key

    assert state_key("a|b", "c") != state_key("a", "b|c")
    assert state_key("a|b", "c").startswith("compaction|")


def test_pipe_scope_names_do_not_collide(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, _spec())
    _insert_event_row(db, "pipe-a", ws="a|b", proj="c", dt=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc))
    _insert_event_row(db, "pipe-b", ws="a", proj="b|c", dt=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc))

    s1 = compact_experience(db, workspace="a|b", project="c", horizon_iso=HORIZON_ALL)
    s2 = compact_experience(db, workspace="a", project="b|c", horizon_iso=HORIZON_ALL)
    assert s1["status"] == "ok" and s1["processed"] == 1
    assert s2["status"] == "ok" and s2["processed"] == 1

    keys = _state_keys(db)
    assert len(keys) == 2, f"scopes must get distinct state keys, got {keys}"

    counts = _table_counts(db)
    again1 = compact_experience(db, workspace="a|b", project="c", horizon_iso=HORIZON_ALL)
    again2 = compact_experience(db, workspace="a", project="b|c", horizon_iso=HORIZON_ALL)
    assert again1["status"] == "noop" and again2["status"] == "noop"
    assert _table_counts(db) == counts


def test_scope_rows_schema_drift_raises_not_silent_empty(tmp_path: Path) -> None:
    db = tmp_path / "drift.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE source_events ("
        " id TEXT, version INTEGER, project_id TEXT, agent_id TEXT, occurred_at TEXT,"
        " action TEXT, result TEXT, payload_digest TEXT)"
    )
    conn.commit()
    conn.close()

    with pytest.raises(sqlite3.OperationalError):
        compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)


def test_missing_relation_source_tables_are_tolerated(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, _spec())
    conn = sqlite3.connect(str(db))
    conn.execute("DROP TABLE proposal_revisions")
    conn.commit()
    conn.close()

    s = compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)
    assert s["status"] == "ok"
    by = s["relations"]["by_rule"]
    assert by["proposal_event_exact"] == {"exact": 0, "unavailable": 0, "dropped": 0}
    assert by["proposal_v1_knowledge_existing"] == {"exact": 0, "unavailable": 0, "dropped": 0}
    assert s["relations"]["existing_knowledge_edges"] is None  # memory_edges table absent


def test_default_horizon_excludes_last_48_hours(tmp_path: Path) -> None:
    rows = _spec_with_tail()
    db = _seed_db(tmp_path, rows)

    summary = compact_experience(db, workspace=WS, project=PROJ)  # no explicit horizon

    assert summary["status"] == "ok"
    assert summary["processed"] == 133, "the day-3 tail (within 48h of max) must be excluded"
    assert _rid("t0") not in _block_event_ids(db)
    assert _rid("t1") not in _block_event_ids(db)


def test_dry_run_previews_normal_run_content_hashes(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, _spec())
    dry = compact_experience(db, workspace=WS, project=PROJ, dry_run=True, horizon_iso=HORIZON_ALL)
    assert dry["mode"] == "dry-run"

    compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)

    stored = {b["content_hash"] for b in _blocks(db)}
    assert set(dry["block_hashes"]) == stored


def test_principal_scopes_never_mix(tmp_path: Path) -> None:
    rows_a = _spec()
    db = _seed_db(tmp_path, rows_a)
    _insert_event_row(db, "b-0", ws="ws-b", proj="proj-b", dt=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc), agent="codex-b")
    _insert_event_row(db, "b-1", ws="ws-b", proj="proj-b", dt=datetime(2026, 6, 1, 9, 0, 10, tzinfo=timezone.utc), agent="codex-b")

    summary_a = compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)
    assert summary_a["processed"] == 133
    assert _block_event_ids(db) == _spec_ids(rows_a), "scope A blocks must contain only scope A ids"

    conn = sqlite3.connect(str(db))
    try:
        state_keys = [r[0] for r in conn.execute("SELECT key FROM compaction_state").fetchall()]
        scoping = conn.execute(
            "SELECT DISTINCT principal_workspace, principal_project FROM compaction_blocks"
        ).fetchall()
    finally:
        conn.close()
    assert len(state_keys) == 1
    assert set(scoping) == {(WS, PROJ)}

    blocks_a_before = _blocks(db)
    summary_b = compact_experience(db, workspace="ws-b", project="proj-b", horizon_iso=HORIZON_ALL)
    assert summary_b["status"] == "ok" and summary_b["processed"] == 2

    blocks_after = _blocks(db)
    hashes_a = {b["content_hash"] for b in blocks_a_before}
    hashes_b_now = {b["content_hash"] for b in blocks_after}
    assert hashes_a <= hashes_b_now
    assert _block_event_ids(db) == _spec_ids(rows_a)
    assert _block_event_ids(db, "ws-b", "proj-b") == {_rid("b-0"), _rid("b-1")}
    assert len(_state_keys(db)) == 2


# ---------------------------------------------------------------------------
# Shadow graph relations (integration)
# ---------------------------------------------------------------------------


def test_block_event_edges_cover_every_window_event_exactly(tmp_path: Path) -> None:
    rows = _spec()
    db = _seed_db(tmp_path, rows)
    compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)

    be = [r for r in _relations(db) if r["rule"] == "block_event_exact"]
    latest = {row["id"]: row["version"] for row in rows}
    assert len(be) == 133
    assert {(r["to_id"], r["to_version"]) for r in be} == set(latest.items())
    block_hashes = {b["content_hash"] for b in _blocks(db, tier=1)}
    assert {r["from_id"] for r in be} <= block_hashes
    assert all(r["from_type"] == "tier1_block" for r in be)
    assert all(r["to_type"] == "event_revision" for r in be)
    assert all(r["state"] == "candidate" for r in be)
    assert all(r["basis_ref"].startswith("tier1:") and r["basis_digest"] for r in be)
    # relation ids are deterministic and scope-safe (rebuild reproduces them)
    ids_first = sorted(r["relation_id"] for r in be)
    compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL, full=True)
    ids_second = sorted(r["relation_id"] for r in _relations(db) if r["rule"] == "block_event_exact")
    assert ids_first == ids_second


def test_proposal_event_edges_exact_same_scope_only(tmp_path: Path) -> None:
    rows = _spec()
    db = _seed_db(tmp_path, rows)
    store = EventStore(db, principal=StaticPrincipalAdapter(actor=ACTOR, workspace=WS, project=PROJ))
    pr1 = _rid("p1")
    store.create_proposal(
        id=pr1, project_id=PROJ, agent_id="codex",
        occurred_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        action="codex ProposalCreate proposal created", result="ready", lesson="keep",
        source_refs=[{"type": "execution", "id": _rid("f1")}, {"type": "execution", "id": _rid("u1")}],
    )
    pr2 = _rid("p2")  # no evidence refs at all
    store.create_proposal(
        id=pr2, project_id=PROJ, agent_id="codex",
        occurred_at=datetime(2026, 6, 1, 10, 1, tzinfo=timezone.utc),
        action="codex ProposalCreate proposal created", result="ready", lesson="none",
        source_refs=[],
    )
    store._conn.close()
    # unresolvable execution ref (EventStore would reject it; store it directly)
    _insert_proposal_row(db, _rid("p3"), ws=WS, proj=PROJ,
                         refs=[{"type": "execution", "id": _rid("ghost-event")}])

    s = compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)
    assert s["relations"]["by_rule"]["proposal_event_exact"] == {
        "exact": 2, "unavailable": 1, "dropped": 0,
    }
    pe = [r for r in _relations(db) if r["rule"] == "proposal_event_exact"]
    assert len(pe) == 2
    assert {(r["from_id"], r["from_version"]) for r in pe} == {(pr1, 1)}
    assert {r["to_id"] for r in pe} == {_rid("f1"), _rid("u1")}
    assert all(r["to_type"] == "event_revision" for r in pe)
    assert all("source_refs" in r["basis_ref"] for r in pe)
    # proposals without evidence never gain edges
    assert not any(r["from_id"] == pr2 for r in _relations(db))
    assert not any(r["from_id"] == _rid("p3") for r in _relations(db))


def test_cross_scope_execution_ref_is_not_connected(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, _spec())
    _insert_event_row(db, "b-0", ws="ws-b", proj="proj-b", dt=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc))
    # a proposal in scope B referencing scope A's event (never resolvable in B)
    _insert_proposal_row(db, _rid("pb1"), ws="ws-b", proj="proj-b",
                         refs=[{"type": "execution", "id": _rid("f1")}])

    compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)
    s_b = compact_experience(db, workspace="ws-b", project="proj-b", horizon_iso=HORIZON_ALL)

    by = s_b["relations"]["by_rule"]["proposal_event_exact"]
    assert by == {"exact": 0, "unavailable": 1, "dropped": 0}
    rel_b = _relations(db, "ws-b", "proj-b")
    assert not any(r["to_id"] == _rid("f1") for r in rel_b)
    assert {r["rule"] for r in rel_b} == {"block_event_exact"}


def test_v1_proposal_knowledge_links_projected_exactly(tmp_path: Path) -> None:
    rows = _spec()
    db = _seed_db(tmp_path, rows)
    _add_v1_graph(
        db,
        proposals=["pv1", "pv2"],
        nodes=["k1", "k2"],
        links=[("pv1", "k1"), ("pv2", "k2"), ("pv-gone", "k1")],
        edges=[("k1", "k2", "related_to")],
    )

    s = compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)
    assert s["relations"]["by_rule"]["proposal_v1_knowledge_existing"] == {
        "exact": 2, "unavailable": 1, "dropped": 0,
    }
    rel = _relations(db)
    c = [r for r in rel if r["rule"] == "proposal_v1_knowledge_existing"]
    assert {(r["from_id"], r["to_id"], r["edge_scope"]) for r in c} == {
        ("pv1", "k1", "global"), ("pv2", "k2", "global"),
    }
    assert all(r["from_type"] == "proposal_v1" and r["to_type"] == "knowledge_node" for r in c)
    assert all("proposal_knowledge_links" in r["basis_ref"] for r in c)
    # V1 proposals have no execution evidence: they NEVER get event edges
    assert not any(
        r["from_type"] == "proposal_v1" and r["to_type"] == "event_revision" for r in rel
    )
    # knowledge<->knowledge edges stay in memory_edges: report-only, not copied
    assert not any(r["from_type"] == "knowledge_node" for r in rel)
    assert s["relations"]["existing_knowledge_edges"] == 1


def test_relation_overflow_writes_explicit_review_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hermes.experience_compactor as ec

    db = _seed_db(tmp_path, _spec())
    monkeypatch.setattr(ec, "RELATION_MAX", 10)

    s = ec.compact_experience(db, workspace=WS, project=PROJ, horizon_iso=HORIZON_ALL)

    assert s["relations"]["total"] == 10
    assert s["relations"]["by_rule"]["block_event_exact"]["dropped"] == 123
    assert len(_relations(db)) == 10
    conn = sqlite3.connect(str(db))
    try:
        overflow = conn.execute(
            "SELECT kind, ref FROM compaction_review WHERE kind='relation_overflow'"
        ).fetchall()
    finally:
        conn.close()
    assert ("relation_overflow", "block_event_exact:123") in overflow


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_dry_run_json_zero_writes(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    db = _seed_db(tmp_path, _spec_with_tail())
    tables_before = _table_names(db)

    code = cli_main(
        [
            "--sync-root", str(tmp_path),
            "compact-experience",
            "--dry-run",
            "--json",
            "--workspace", WS,
            "--project", PROJ,
        ]
    )

    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["dry_run"] is True
    assert summary["processed"] == 133
    assert summary["relations"]["by_rule"]["block_event_exact"]["exact"] == 133
    assert _table_names(db) == tables_before


def test_cli_write_then_repeat_idempotent(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    db = _seed_db(tmp_path, _spec_with_tail())
    argv = [
        "--sync-root", str(tmp_path),
        "compact-experience",
        "--json",
        "--workspace", WS,
        "--project", PROJ,
    ]
    code = cli_main(argv)
    assert code == 0
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "ok" and first["processed"] == 133
    counts_first = _table_counts(db)

    code = cli_main(argv)
    assert code == 0
    second = json.loads(capsys.readouterr().out)
    assert second["status"] == "noop"
    assert second["blocks_new"] == 0
    assert _table_counts(db) == counts_first


def test_cli_human_output_includes_relation_counts(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    db = _seed_db(tmp_path, _spec_with_tail())
    _add_v1_graph(db, proposals=["pv1"], nodes=["k1"], links=[("pv1", "k1")])

    code = cli_main(
        [
            "--sync-root", str(tmp_path),
            "compact-experience",
            "--workspace", WS,
            "--project", PROJ,
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "processed=133" in out
    assert "relations" in out
    assert "block_event_exact" in out and "exact=133" in out
    assert "proposal_v1_knowledge_existing" in out
    assert "existing kn-kn edges=0" in out


def test_cli_schema_drift_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    db = tmp_path / "hermes.sqlite3"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE source_events ("
        " id TEXT, version INTEGER, project_id TEXT, agent_id TEXT, occurred_at TEXT,"
        " action TEXT, result TEXT, payload_digest TEXT)"
    )
    conn.commit()
    conn.close()

    code = cli_main(
        [
            "--sync-root", str(tmp_path),
            "compact-experience",
            "--workspace", WS,
            "--project", PROJ,
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "error" in (captured.out + captured.err).lower()
    assert "Traceback" not in captured.err


def test_cli_requires_principal_scope(tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _seed_db(tmp_path, _spec())
    monkeypatch.delenv("BRAIN_V2_WORKSPACE", raising=False)
    monkeypatch.delenv("BRAIN_V2_PROJECT", raising=False)
    tables_before = _table_names(db)

    code = cli_main(["--sync-root", str(tmp_path), "compact-experience"])

    assert code == 2
    assert _table_names(db) == tables_before


def test_constants_are_explicit() -> None:
    assert SESSION_GAP_S == 1800.0
    assert HORIZON_LAG_S == 48 * 3600.0
    assert DEFAULT_CHAR_BUDGET == 8000
