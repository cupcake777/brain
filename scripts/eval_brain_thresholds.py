#!/usr/bin/env python3
"""Evaluate Brain related/merge thresholds against a gold JSONL.

Usage:
  .venv/bin/python scripts/eval_brain_thresholds.py --hygiene-only
  .venv/bin/python scripts/eval_brain_thresholds.py \\
      --gold eval/gold_pairs.suggested.jsonl --tag suggested --allow-suggested
  .venv/bin/python scripts/eval_brain_thresholds.py \\
      --gold eval/gold_pairs.labeled.jsonl --tag v1
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
from array import array
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DB = os.environ.get("HERMES_SYNC_DB", "data/hermes.sqlite3")
DEFAULT_OUT = ROOT / "eval"


def decode_vec(blob, dim):
    if blob is None:
        return None
    if len(blob) == dim * 4:
        return list(array("f", blob))
    if len(blob) == dim * 8:
        return list(array("d", blob))
    return None


def prf(y_true, y_pred):
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt and yp)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if (not yt) and yp)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt and (not yp))
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if (not yt) and (not yp))
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
        "support_pos": tp + fn, "support_neg": tn + fp,
    }


def load_gold(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            lab = (obj.get("label") or "").strip()
            if lab not in ("exact_dup", "related", "unrelated"):
                continue
            rows.append(obj)
    return rows


def recompute_scores(rows, db):
    need = any(r.get("emb") is None or r.get("hybrid") is None for r in rows)
    if not need:
        return rows
    try:
        from hermes.integrate import _text_similarity
    except Exception:
        def _text_similarity(a, b):
            ta = set(re.findall(r"\w+", (a or "").lower()))
            tb = set(re.findall(r"\w+", (b or "").lower()))
            if not ta or not tb:
                return 0.0
            return len(ta & tb) / len(ta | tb)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    emb = {}
    for r in cur.execute(
        "SELECT entity_id, dimension, vector FROM entity_embeddings "
        "WHERE entity_type='knowledge' AND status='ready'"
    ):
        v = decode_vec(r["vector"], r["dimension"])
        if v is not None:
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            emb[r["entity_id"]] = [x / n for x in v]
    summaries = {
        r["id"]: (r["summary"] or "")
        for r in cur.execute("SELECT id, summary FROM knowledge_nodes")
    }
    conn.close()
    out = []
    for r in rows:
        rr = dict(r)
        a, b = rr["id_a"], rr["id_b"]
        if a in emb and b in emb:
            e = sum(x * y for x, y in zip(emb[a], emb[b]))
            t = _text_similarity(summaries.get(a, ""), summaries.get(b, ""))
            rr["emb"] = round(e, 4)
            rr["text"] = round(t, 4)
            rr["hybrid"] = round(0.7 * e + 0.3 * t, 4)
        out.append(rr)
    return out


def sweep_merge(rows, score_key, thresholds):
    y_true = [1 if r["label"] == "exact_dup" else 0 for r in rows]
    results = []
    for thr in thresholds:
        y_pred = [1 if float(r.get(score_key) or 0) >= thr else 0 for r in rows]
        m = prf(y_true, y_pred)
        m["threshold"] = thr
        m["score"] = score_key
        results.append(m)
    return results


def sweep_related(rows, thresholds, *, hybrid_gate):
    y_true = [1 if r["label"] in ("exact_dup", "related") else 0 for r in rows]
    results = []
    for thr in thresholds:
        y_pred = []
        for r in rows:
            e = float(r.get("emb") or 0)
            h = float(r.get("hybrid") or 0)
            if hybrid_gate:
                y_pred.append(1 if (e >= thr and (e >= 0.92 or h >= 0.70)) else 0)
            else:
                y_pred.append(1 if e >= thr else 0)
        m = prf(y_true, y_pred)
        m["threshold"] = thr
        m["score"] = "emb+hyb_gate" if hybrid_gate else "emb"
        results.append(m)
    return results


def hygiene_report(db):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    stages = dict(cur.execute("SELECT stage, COUNT(*) c FROM knowledge_nodes GROUP BY stage"))
    active = cur.execute(
        "SELECT COUNT(*) FROM knowledge_nodes WHERE stage!='deprecated'"
    ).fetchone()[0]
    emb_ready = cur.execute(
        "SELECT COUNT(*) FROM entity_embeddings WHERE entity_type='knowledge' AND status='ready'"
    ).fetchone()[0]
    emb_failed = cur.execute(
        "SELECT COUNT(*) FROM entity_embeddings WHERE entity_type='knowledge' AND status!='ready'"
    ).fetchone()[0]
    junk = cur.execute(
        """
        SELECT id, summary FROM knowledge_nodes
        WHERE stage!='deprecated'
          AND (summary LIKE '%brain-protocol-v3%'
               OR content LIKE '%brain-protocol-v3-evidence%'
               OR summary LIKE '- source_type:%'
               OR summary LIKE '%source_type: user_correction%')
        """
    ).fetchall()
    rel = list(cur.execute("SELECT evidence_id FROM memory_edges WHERE edge_type='related_to'"))
    cos_vals = []
    for r in rel:
        m = re.search(r"cos=([0-9.]+)", r["evidence_id"] or "")
        if m:
            cos_vals.append(float(m.group(1)))
    cos_vals.sort()
    act = list(cur.execute("SELECT id, content FROM knowledge_nodes WHERE stage!='deprecated'"))
    content_map = {}
    for r in act:
        c = (r["content"] or "").strip()
        if not c:
            continue
        content_map.setdefault(c, []).append(r["id"])
    content_eq_pairs = sum(len(v) * (len(v) - 1) // 2 for v in content_map.values() if len(v) > 1)
    edges = dict(cur.execute("SELECT edge_type, COUNT(*) c FROM memory_edges GROUP BY edge_type"))
    checks = {
        "active_nodes": active,
        "emb_ready_knowledge": emb_ready,
        "emb_not_ready_knowledge": emb_failed,
        "junk_active_count": len(junk),
        "junk_active_ids": [r["id"] for r in junk[:20]],
        "content_eq_active_pairs": content_eq_pairs,
        "related_count": len(rel),
        "related_cos_min": cos_vals[0] if cos_vals else None,
        "related_cos_p50": cos_vals[len(cos_vals) // 2] if cos_vals else None,
        "related_cos_max": cos_vals[-1] if cos_vals else None,
        "related_cos_floor_ok": (min(cos_vals) >= 0.86 - 1e-6) if cos_vals else True,
        "stages": stages,
        "edges": edges,
    }
    checks["pass"] = (
        checks["junk_active_count"] == 0
        and checks["content_eq_active_pairs"] == 0
        and checks["related_cos_floor_ok"]
        and checks["emb_not_ready_knowledge"] == 0
    )
    conn.close()
    return checks


def print_table(title, rows):
    print(f"\n=== {title} ===")
    print(f"{'thr':>6} {'P':>7} {'R':>7} {'F1':>7} {'tp':>4} {'fp':>4} {'fn':>4}  score")
    for m in rows:
        print(
            f"{m['threshold']:6.2f} {m['precision']:7.3f} {m['recall']:7.3f} {m['f1']:7.3f} "
            f"{m['tp']:4d} {m['fp']:4d} {m['fn']:4d}  {m['score']}"
        )


def main():
    ap = argparse.ArgumentParser(description="Brain threshold evaluation")
    ap.add_argument("--gold", type=Path)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--hygiene-only", action="store_true")
    ap.add_argument("--allow-suggested", action="store_true")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "db": args.db,
        "tag": args.tag,
    }
    hyg = hygiene_report(args.db)
    report["hygiene"] = hyg
    print("=== L1 HYGIENE ===")
    for k in (
        "active_nodes", "emb_ready_knowledge", "emb_not_ready_knowledge",
        "junk_active_count", "content_eq_active_pairs", "related_count",
        "related_cos_min", "related_cos_p50", "related_cos_floor_ok", "pass",
    ):
        print(f"  {k}: {hyg.get(k)}")

    if args.hygiene_only:
        out = args.out_dir / f"hygiene_{args.tag}.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", out)
        return 0 if hyg["pass"] else 2

    if not args.gold or not args.gold.exists():
        print("ERROR: --gold required (or use --hygiene-only)", file=sys.stderr)
        return 1

    rows = load_gold(args.gold)
    if not rows:
        print("ERROR: no labeled rows in", args.gold, file=sys.stderr)
        return 1

    labelers = Counter(r.get("labeler") or "" for r in rows)
    if any(l == "auto_suggested" for l in labelers) and not args.allow_suggested:
        print(
            "WARNING: gold contains auto_suggested labels. "
            "Pass --allow-suggested to eval seeds, or use human-labeled file.",
            file=sys.stderr,
        )
        return 1

    rows = recompute_scores(rows, args.db)
    label_dist = Counter(r["label"] for r in rows)
    print(f"\nGold: {len(rows)} labeled pairs from {args.gold}")
    print("  labels:", dict(label_dist))
    print("  labelers:", dict(labelers))

    merge_thr = [0.70, 0.75, 0.80, 0.85, 0.90, 0.93, 0.95]
    rel_thr = [0.78, 0.80, 0.82, 0.84, 0.86, 0.88, 0.90, 0.92]
    merge_hybrid = sweep_merge(rows, "hybrid", merge_thr)
    merge_text = sweep_merge(rows, "text", merge_thr)
    related_emb = sweep_related(rows, rel_thr, hybrid_gate=False)
    related_gate = sweep_related(rows, rel_thr, hybrid_gate=True)
    print_table("MERGE (score=hybrid, pos=exact_dup)", merge_hybrid)
    print_table("MERGE (score=text-only, pos=exact_dup)", merge_text)
    print_table("RELATED (score=emb, pos=exact_dup|related)", related_emb)
    print_table("RELATED (emb+hybrid_gate, pos=exact_dup|related)", related_gate)

    def pick(rows_m, min_p=0.9):
        ok = [m for m in rows_m if m["precision"] >= min_p]
        pool = ok or rows_m
        return max(pool, key=lambda m: (m["f1"], m["precision"], m["recall"]))

    rec = {
        "merge_hybrid": pick(merge_hybrid, 0.95),
        "related_emb": pick(related_emb, 0.80),
        "related_hybrid_gate": pick(related_gate, 0.80),
    }
    print("\n=== RECOMMENDED (heuristic max F1 under precision floor) ===")
    for k, v in rec.items():
        print(f"  {k}: thr={v['threshold']} P={v['precision']} R={v['recall']} F1={v['f1']}")

    report["gold"] = {
        "path": str(args.gold), "n": len(rows),
        "labels": dict(label_dist), "labelers": dict(labelers),
    }
    report["merge_hybrid"] = merge_hybrid
    report["merge_text"] = merge_text
    report["related_emb"] = related_emb
    report["related_hybrid_gate"] = related_gate
    report["recommended"] = rec
    out = args.out_dir / f"threshold_eval_{args.tag}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
