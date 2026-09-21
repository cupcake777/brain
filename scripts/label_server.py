#!/usr/bin/env python3
"""Local web UI for labeling Brain gold pairs.

  .venv/bin/python scripts/label_server.py
  # open http://127.0.0.1:8789/

Saves to eval/gold_pairs.labeled.jsonl (creates from gold_pairs.jsonl if missing).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "eval"
GOLD_SRC = EVAL / "gold_pairs.jsonl"
GOLD_LABELED = EVAL / "gold_pairs.labeled.jsonl"
GOLD_SUGGESTED = EVAL / "gold_pairs.suggested.jsonl"
HTML_PATH = EVAL / "label_ui.html"

app = FastAPI(title="Brain Gold Labeler", docs_url=None, redoc_url=None)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
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
    # optional seed from suggested
    sug = {r["pair_id"]: r for r in _load_jsonl(GOLD_SUGGESTED)}
    for r in rows:
        s = sug.get(r["pair_id"])
        if s and s.get("suggested_label") and not r.get("label"):
            r["suggested_label"] = s.get("suggested_label") or r.get("suggested_label")
    _save_jsonl(GOLD_LABELED, rows)
    return rows


class LabelBody(BaseModel):
    pair_id: str
    label: str = Field(..., pattern="^(exact_dup|related|unrelated)$")
    labeler: str = "web"
    notes: str = ""


class MetaBody(BaseModel):
    labeler: str = "web"


@app.get("/", response_class=HTMLResponse)
def index():
    if not HTML_PATH.exists():
        raise HTTPException(500, f"missing UI {HTML_PATH}")
    return HTML_PATH.read_text(encoding="utf-8")


@app.get("/api/state")
def state():
    rows = ensure_labeled()
    labeled = sum(1 for r in rows if (r.get("label") or "") in ("exact_dup", "related", "unrelated"))
    by_stratum: dict[str, dict[str, int]] = {}
    by_label = {"exact_dup": 0, "related": 0, "unrelated": 0, "unlabeled": 0}
    for r in rows:
        st = r.get("stratum") or "unknown"
        lab = r.get("label") or ""
        if st not in by_stratum:
            by_stratum[st] = {"total": 0, "labeled": 0}
        by_stratum[st]["total"] += 1
        if lab in by_label:
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
        "path": str(GOLD_LABELED.relative_to(ROOT)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/pairs")
def pairs(filter: str = "all", stratum: str = ""):
    rows = ensure_labeled()
    out = []
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
        item = dict(r)
        item["_index"] = i
        out.append(item)
    return {"pairs": out, "count": len(out)}


@app.post("/api/label")
def label(body: LabelBody):
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


@app.post("/api/clear")
def clear(pair_id: str):
    rows = ensure_labeled()
    for r in rows:
        if r.get("pair_id") == pair_id:
            r["label"] = ""
            r["notes"] = r.get("notes") or ""
            r.pop("labeled_at", None)
            _save_jsonl(GOLD_LABELED, rows)
            return {"ok": True}
    raise HTTPException(404, "pair_id not found")


@app.post("/api/seed_suggested")
def seed_suggested(only_empty: bool = True):
    """Copy suggested_label into label for empty rows (optional helper)."""
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


def main():
    host = os.environ.get("LABEL_HOST", "127.0.0.1")
    port = int(os.environ.get("LABEL_PORT", "8789"))
    ensure_labeled()
    print(f"Brain Gold Labeler → http://{host}:{port}/")
    print(f"Saving to {GOLD_LABELED.relative_to(ROOT)}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
