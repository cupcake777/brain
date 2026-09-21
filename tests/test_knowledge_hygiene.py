"""L1 knowledge hygiene regression checks.

These do NOT prove threshold optimality; they catch graph/DB regressions.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

import pytest

DEFAULT_DB = Path(os.environ.get("HERMES_SYNC_DB", "data/hermes.sqlite3"))
RELATED_COS_FLOOR = float(os.environ.get("BRAIN_RELATED_COS_FLOOR", "0.86"))


@pytest.fixture(scope="module")
def db_path() -> Path:
    if not DEFAULT_DB.exists():
        pytest.skip(f"DB not found: {DEFAULT_DB}")
    return DEFAULT_DB


@pytest.fixture(scope="module")
def conn(db_path: Path):
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def test_no_protocol_junk_active(conn):
    rows = conn.execute(
        """
        SELECT id, summary FROM knowledge_nodes
        WHERE stage != 'deprecated'
          AND (
            summary LIKE '%brain-protocol-v3%'
            OR content LIKE '%brain-protocol-v3-evidence%'
            OR summary LIKE '- source_type:%'
            OR summary LIKE '%source_type: user_correction%'
          )
        """
    ).fetchall()
    assert rows == [], f"junk active nodes: {[r['id'][:8] for r in rows]}"


def test_no_content_equal_active_duplicates(conn):
    act = conn.execute(
        "SELECT id, content FROM knowledge_nodes WHERE stage != 'deprecated'"
    ).fetchall()
    by_content = {}
    for r in act:
        c = (r["content"] or "").strip()
        if not c:
            continue
        by_content.setdefault(c, []).append(r["id"])
    dups = {k[:40]: v for k, v in by_content.items() if len(v) > 1}
    assert not dups, f"content-equal active groups: { {k: [x[:8] for x in v] for k,v in dups.items()} }"


def test_related_cosine_floor(conn):
    rows = conn.execute(
        "SELECT evidence_id FROM memory_edges WHERE edge_type='related_to'"
    ).fetchall()
    if not rows:
        pytest.skip("no related_to edges")
    below = []
    for r in rows:
        m = re.search(r"cos=([0-9.]+)", r["evidence_id"] or "")
        if not m:
            below.append(("no_cos", r["evidence_id"]))
            continue
        cos = float(m.group(1))
        if cos < RELATED_COS_FLOOR - 1e-9:
            below.append((cos, r["evidence_id"]))
    assert not below, f"{len(below)} related edges below {RELATED_COS_FLOOR}: {below[:5]}"


def test_embedding_coverage_active(conn):
    active_ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM knowledge_nodes WHERE stage != 'deprecated'"
        )
    ]
    if not active_ids:
        pytest.skip("no active knowledge")
    ready = {
        r["entity_id"]
        for r in conn.execute(
            "SELECT entity_id FROM entity_embeddings "
            "WHERE entity_type='knowledge' AND status='ready'"
        )
    }
    missing = [i for i in active_ids if i not in ready]
    assert not missing, f"{len(missing)} active nodes missing ready embeddings e.g. {missing[:5]}"


def test_stages_sane(conn):
    stages = {
        r["stage"]: r["c"]
        for r in conn.execute(
            "SELECT stage, COUNT(*) c FROM knowledge_nodes GROUP BY stage"
        )
    }
    assert stages.get("canonized", 0) > 0
    assert stages.get("draft", 0) < 50
