"""Gold-pair labeling UI + API, mounted under Brain auth.

Page:  GET  /label-gold
API:   GET  /api/label-gold/state
       GET  /api/label-gold/pairs
       POST /api/label-gold/label
       POST /api/label-gold/clear
       POST /api/label-gold/seed_suggested
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "eval"
GOLD_SRC = EVAL / "gold_pairs.jsonl"
GOLD_LABELED = EVAL / "gold_pairs.labeled.jsonl"
GOLD_SUGGESTED = EVAL / "gold_pairs.suggested.jsonl"
HTML_PATH = EVAL / "label_ui.html"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _save_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def ensure_labeled() -> list[dict[str, Any]]:
    if GOLD_LABELED.exists():
        return _load_jsonl(GOLD_LABELED)
    if not GOLD_SRC.exists():
        raise FileNotFoundError(f"missing {GOLD_SRC}")
    rows = _load_jsonl(GOLD_SRC)
    sug = {r["pair_id"]: r for r in _load_jsonl(GOLD_SUGGESTED)}
    for r in rows:
        s = sug.get(r["pair_id"])
        if s and s.get("suggested_label") and not r.get("label"):
            r["suggested_label"] = s.get("suggested_label") or r.get("suggested_label")
    _save_jsonl(GOLD_LABELED, rows)
    return rows



def _db_path() -> Path:
    import os
    env = os.environ.get("HERMES_DB_PATH")
    if env:
        return Path(env)
    sync = Path(os.environ.get("HERMES_SYNC_ROOT", str(Path.home() / "hermes-sync")))
    return sync / "hermes.sqlite3"


def _fetch_node_texts(ids: list[str]) -> dict[str, dict[str, str]]:
    """Load full summary/content for knowledge nodes (for untruncated labeling)."""
    import sqlite3
    out: dict[str, dict[str, str]] = {}
    ids = [i for i in ids if i]
    if not ids:
        return out
    db = _db_path()
    if not db.exists():
        return out
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        # chunk to keep SQL short
        for i in range(0, len(ids), 200):
            chunk = ids[i:i+200]
            qmarks = ",".join("?" for _ in chunk)
            for row in conn.execute(
                f"SELECT id, summary, content, stage, domain FROM knowledge_nodes WHERE id IN ({qmarks})",
                chunk,
            ):
                out[row["id"]] = {
                    "summary": row["summary"] or "",
                    "content": row["content"] or "",
                    "stage": row["stage"] or "",
                    "domain": row["domain"] or "",
                }
    finally:
        conn.close()
    return out


def _enrich_pair(r: dict[str, Any], nodes: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """Attach full texts so UI is not stuck on export truncations."""
    item = dict(r)
    nodes = nodes or {}
    for side, id_key, sum_key, head_key, full_key in (
        ("a", "id_a", "summary_a", "content_a_head", "content_a"),
        ("b", "id_b", "summary_b", "content_b_head", "content_b"),
    ):
        nid = item.get(id_key) or ""
        node = nodes.get(nid) or {}
        if node:
            if node.get("summary"):
                item[sum_key] = node["summary"]
            if node.get("content"):
                item[full_key] = node["content"]
                # keep head as convenience preview, but full is source of truth
                item[head_key] = node["content"]
            if node.get("stage") and not item.get(f"stage_{side}"):
                item[f"stage_{side}"] = node["stage"]
            if node.get("domain") and not item.get(f"domain_{side}"):
                item[f"domain_{side}"] = node["domain"]
        else:
            # fallback: promote head to full if no DB hit
            if not item.get(full_key):
                item[full_key] = item.get(head_key) or ""
    # truncation flags for UI badge
    ca = item.get("content_a") or ""
    cb = item.get("content_b") or ""
    ha = item.get("content_a_head") or ""
    hb = item.get("content_b_head") or ""
    # if we only have head and it looks truncated (export used 240), flag it
    item["full_text"] = bool(ca or cb) and (len(ca) >= len(ha) or len(cb) >= len(hb))
    item["content_a_len"] = len(ca)
    item["content_b_len"] = len(cb)
    return item

class LabelBody(BaseModel):
    pair_id: str
    label: str = Field(..., pattern="^(exact_dup|related|unrelated)$")
    labeler: str = "web"
    notes: str = ""


def register_label_gold_routes(app: FastAPI) -> None:
    @app.get("/label-gold", response_class=HTMLResponse)
    def label_gold_page() -> str:
        if not HTML_PATH.exists():
            raise HTTPException(500, f"missing UI {HTML_PATH}")
        # ensure file exists so first open is ready
        try:
            ensure_labeled()
        except FileNotFoundError as e:
            raise HTTPException(500, str(e)) from e
        return HTML_PATH.read_text(encoding="utf-8")

    @app.get("/api/label-gold/state")
    def label_gold_state():
        rows = ensure_labeled()
        labeled = sum(
            1 for r in rows if (r.get("label") or "") in ("exact_dup", "related", "unrelated")
        )
        by_stratum: dict[str, dict[str, int]] = {}
        by_label = {"exact_dup": 0, "related": 0, "unrelated": 0, "unlabeled": 0}
        for r in rows:
            st = r.get("stratum") or "unknown"
            lab = r.get("label") or ""
            if st not in by_stratum:
                by_stratum[st] = {"total": 0, "labeled": 0}
            by_stratum[st]["total"] += 1
            if lab in ("exact_dup", "related", "unrelated"):
                by_stratum[st]["labeled"] += 1
                by_label[lab] += 1
            else:
                by_label["unlabeled"] += 1
        return {
            "n": len(rows),
            "labeled": labeled,
            "unlabeled": len(rows) - labeled,
            "by_label": by_label,
            "by_stratum": by_stratum,
            "path": str(GOLD_LABELED),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/api/label-gold/pairs")
    def label_gold_pairs(
        filter: str = Query(default="all"),
        stratum: str = Query(default=""),
    ):
        rows = ensure_labeled()
        # first pass: filter indices
        selected: list[tuple[int, dict[str, Any]]] = []
        for i, r in enumerate(rows):
            lab = r.get("label") or ""
            if filter == "unlabeled" and lab in ("exact_dup", "related", "unrelated"):
                continue
            if filter == "labeled" and lab not in ("exact_dup", "related", "unrelated"):
                continue
            if filter == "disagree" and not (
                lab and r.get("suggested_label") and lab != r.get("suggested_label")
            ):
                continue
            if stratum and r.get("stratum") != stratum:
                continue
            selected.append((i, r))

        # batch-load full node texts so labeling is not based on 240-char heads
        ids: list[str] = []
        for _, r in selected:
            ids.append(r.get("id_a") or "")
            ids.append(r.get("id_b") or "")
        nodes = _fetch_node_texts(ids)

        out = []
        for i, r in selected:
            item = _enrich_pair(r, nodes)
            item["_index"] = i
            out.append(item)
        return {"pairs": out, "count": len(out)}

    @app.post("/api/label-gold/label")
    def label_gold_label(body: LabelBody):
        rows = ensure_labeled()
        found = False
        for r in rows:
            if r.get("pair_id") == body.pair_id:
                r["label"] = body.label
                r["labeler"] = body.labeler or "web"
                r["notes"] = body.notes or ""
                r["labeled_at"] = datetime.now(timezone.utc).isoformat()
                found = True
                break
        if not found:
            raise HTTPException(404, "pair_id not found")
        _save_jsonl(GOLD_LABELED, rows)
        return {"ok": True, "pair_id": body.pair_id, "label": body.label}

    @app.post("/api/label-gold/clear")
    def label_gold_clear(pair_id: str = Query(...)):
        rows = ensure_labeled()
        for r in rows:
            if r.get("pair_id") == pair_id:
                r["label"] = ""
                r.pop("labeled_at", None)
                _save_jsonl(GOLD_LABELED, rows)
                return {"ok": True}
        raise HTTPException(404, "pair_id not found")

    @app.post("/api/label-gold/seed_suggested")
    def label_gold_seed(only_empty: bool = Query(default=True)):
        rows = ensure_labeled()
        sug = {r["pair_id"]: r for r in _load_jsonl(GOLD_SUGGESTED)}
        n = 0
        for r in rows:
            if only_empty and (r.get("label") or "") in ("exact_dup", "related", "unrelated"):
                continue
            s = sug.get(r["pair_id"], {}).get("suggested_label") or r.get("suggested_label")
            if s in ("exact_dup", "related", "unrelated"):
                r["label"] = s
                r["labeler"] = "auto_suggested"
                r["labeled_at"] = datetime.now(timezone.utc).isoformat()
                n += 1
        _save_jsonl(GOLD_LABELED, rows)
        return {"ok": True, "seeded": n}
