#!/usr/bin/env python3
"""Export stratified gold labeling pairs for Brain related/merge evaluation.

Writes:
  eval/gold_pairs.jsonl
  eval/gold_pairs.suggested.jsonl
  eval/gold_meta.json

Usage:
  .venv/bin/python scripts/export_gold_pairs.py
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import random
import re
import sqlite3
import sys
from array import array
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DB = os.environ.get("HERMES_SYNC_DB", "data/hermes.sqlite3")
OUT_DIR = ROOT / "eval"


def _load_hermes_env() -> None:
    try:
        import subprocess
        pid = subprocess.check_output(
            ["systemctl", "show", "-p", "MainPID", "--value", "hermes-serve.service"],
            text=True,
        ).strip()
        if not pid or pid == "0":
            return
        raw = open(f"/proc/{pid}/environ", "rb").read().split(b"\0")
        for item in raw:
            if b"=" not in item:
                continue
            k, v = item.split(b"=", 1)
            os.environ.setdefault(k.decode(), v.decode(errors="replace"))
    except Exception:
        pass


def _text_similarity(a: str, b: str) -> float:
    try:
        from hermes.integrate import _text_similarity as ts
        return float(ts(a, b))
    except Exception:
        ta = set(re.findall(r"\w+", (a or "").lower()))
        tb = set(re.findall(r"\w+", (b or "").lower()))
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)


def decode_vec(blob, dim):
    if blob is None:
        return None
    if len(blob) == dim * 4:
        return list(array("f", blob))
    if len(blob) == dim * 8:
        return list(array("d", blob))
    return None


def pair_id(a: str, b: str) -> str:
    lo, hi = (a, b) if a < b else (b, a)
    return hashlib.sha1(f"{lo}|{hi}".encode()).hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser(description="Export Brain gold pairs for threshold eval")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    _load_hermes_env()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    emb = {}
    for r in cur.execute(
        "SELECT entity_id, dimension, vector FROM entity_embeddings "
        "WHERE entity_type='knowledge' AND status='ready'"
    ):
        v = decode_vec(r["vector"], r["dimension"])
        if v is not None:
            emb[r["entity_id"]] = v

    nodes = {
        r["id"]: dict(r)
        for r in cur.execute(
            "SELECT id, stage, summary, content, domain, category, confidence, "
            "retrieval_count, created_at FROM knowledge_nodes"
        )
    }
    active = [i for i, n in nodes.items() if n["stage"] != "deprecated" and i in emb]
    all_with_emb = [i for i in nodes if i in emb]
    norms = {}
    for i in all_with_emb:
        v = emb[i]
        nrm = math.sqrt(sum(x * x for x in v)) or 1.0
        norms[i] = [x / nrm for x in v]

    def scores(a, b):
        e = sum(x * y for x, y in zip(norms[a], norms[b]))
        t = _text_similarity(nodes[a]["summary"] or "", nodes[b]["summary"] or "")
        h = 0.7 * e + 0.3 * t
        ca = (nodes[a]["content"] or "").strip()
        cb = (nodes[b]["content"] or "").strip()
        return {
            "emb": round(e, 4),
            "text": round(t, 4),
            "hybrid": round(h, 4),
            "content_eq": bool(ca and ca == cb),
            "same_domain": (nodes[a].get("domain") or "general")
            == (nodes[b].get("domain") or "general"),
        }

    def make_item(a, b, stratum, source, suggested=""):
        sc = scores(a, b)
        return {
            "pair_id": pair_id(a, b),
            "stratum": stratum,
            "source": source,
            "label": "",
            "labeler": "",
            "notes": "",
            "suggested_label": suggested,
            "id_a": a,
            "id_b": b,
            "stage_a": nodes[a]["stage"],
            "stage_b": nodes[b]["stage"],
            "domain_a": nodes[a].get("domain") or "general",
            "domain_b": nodes[b].get("domain") or "general",
            "summary_a": (nodes[a]["summary"] or "")[:300],
            "summary_b": (nodes[b]["summary"] or "")[:300],
            "content_a_head": (nodes[a]["content"] or "")[:240].replace("\n", " "),
            "content_b_head": (nodes[b]["content"] or "")[:240].replace("\n", " "),
            **sc,
        }

    seen = set()
    items = []

    def add(item):
        if item["pair_id"] in seen:
            return False
        if item["id_a"] not in norms or item["id_b"] not in norms:
            return False
        if item["id_a"] == item["id_b"]:
            return False
        seen.add(item["pair_id"])
        items.append(item)
        return True

    # Positive exact dups FIRST (keep vs deprecated loser)
    n = 0
    for r in cur.execute(
        "SELECT from_id, to_id FROM memory_edges "
        "WHERE edge_type='supersedes' AND evidence_id='hybrid_exact_dup'"
    ):
        if n >= 12:
            break
        a, b = r["from_id"], r["to_id"]
        if a in norms and b in norms and add(
            make_item(a, b, "positive_exact_dup", "hybrid_exact_dup_edge", "exact_dup")
        ):
            n += 1
    print("positive_exact_dup exported", n)

    cur_rel = list(
        cur.execute(
            "SELECT from_id, to_id, evidence_id FROM memory_edges WHERE edge_type='related_to'"
        )
    )
    bands = {
        "related_0.86_0.88": [],
        "related_0.88_0.90": [],
        "related_0.90_0.92": [],
        "related_ge_0.92": [],
    }
    for r in cur_rel:
        a, b = r["from_id"], r["to_id"]
        if a not in nodes or b not in nodes:
            continue
        if nodes[a]["stage"] == "deprecated" or nodes[b]["stage"] == "deprecated":
            continue
        m = re.search(r"cos=([0-9.]+)", r["evidence_id"] or "")
        if not m:
            continue
        c = float(m.group(1))
        if c < 0.88:
            bands["related_0.86_0.88"].append((a, b, c))
        elif c < 0.90:
            bands["related_0.88_0.90"].append((a, b, c))
        elif c < 0.92:
            bands["related_0.90_0.92"].append((a, b, c))
        else:
            bands["related_ge_0.92"].append((a, b, c))

    quota = {
        "related_0.86_0.88": 20,
        "related_0.88_0.90": 16,
        "related_0.90_0.92": 12,
        "related_ge_0.92": 8,
    }
    for stratum, pairs in bands.items():
        random.shuffle(pairs)
        n = 0
        for a, b, c in pairs:
            if n >= quota[stratum]:
                break
            sug = "related" if c >= 0.90 else ""
            if add(make_item(a, b, stratum, "current_related_edge", sug)):
                n += 1
        print(stratum, "exported", n, "of", len(pairs))

    by_domain = collections.defaultdict(list)
    for i in active:
        by_domain[nodes[i].get("domain") or "general"].append(i)

    near_miss, hard_neg, clear_unrel = [], [], []
    for dom, members in by_domain.items():
        if len(members) < 2:
            continue
        mem = list(members)
        if len(mem) > 60:
            mem = random.sample(mem, 60)
        for i in range(len(mem)):
            for j in range(i + 1, len(mem)):
                a, b = mem[i], mem[j]
                e = sum(x * y for x, y in zip(norms[a], norms[b]))
                t = _text_similarity(nodes[a]["summary"] or "", nodes[b]["summary"] or "")
                h = 0.7 * e + 0.3 * t
                if 0.78 <= e < 0.86:
                    near_miss.append((e, t, h, a, b, dom))
                if e >= 0.85 and t < 0.30:
                    hard_neg.append((e, t, h, a, b, dom))
                if e < 0.70 and t < 0.15:
                    clear_unrel.append((e, t, h, a, b, dom))

    def take(pool, stratum, source, limit, sug_fn):
        random.shuffle(pool)
        n = 0
        for row in pool:
            if n >= limit:
                break
            e, t, h, a, b, dom = row
            if add(make_item(a, b, stratum, source, sug_fn(e, t, h))):
                n += 1
        print(stratum, "exported", n, "pool", len(pool))
        return n

    take(near_miss, "near_miss_0.78_0.86", "domain_pair_scan", 24,
         lambda e, t, h: "unrelated" if t < 0.25 else "")
    take(hard_neg, "hard_neg_emb_high_text_low", "domain_pair_scan", 16,
         lambda e, t, h: "unrelated")
    take(clear_unrel, "clear_unrelated", "domain_pair_scan", 12,
         lambda e, t, h: "unrelated")

    # historical_merge: thought_chains often self-ref evidence; use supersedes/duplicates edges instead
    n = 0
    for r in cur.execute(
        """
        SELECT from_id, to_id, edge_type, evidence_id FROM memory_edges
        WHERE edge_type IN ('supersedes','duplicates')
          AND (evidence_id IS NULL OR evidence_id != 'hybrid_exact_dup')
        ORDER BY created_at DESC
        """
    ):
        if n >= 12:
            break
        a, b = r["from_id"], r["to_id"]
        if a not in norms or b not in norms:
            continue
        sug = ""
        ev = r["evidence_id"] or ""
        if "brain-protocol" in ((nodes[a].get("summary") or "") + (nodes[b].get("summary") or "")):
            sug = "unrelated"
        elif r["edge_type"] == "duplicates" and "cos=" in ev:
            try:
                cos = float(re.search(r"cos=([0-9.]+)", ev).group(1))
                sug = "exact_dup" if cos >= 0.95 else "related"
            except Exception:
                sug = "related"
        elif r["edge_type"] == "supersedes":
            sug = "exact_dup"  # historical keep/deprecate decision
        if add(make_item(a, b, "historical_merge", f"{r['edge_type']}:{ev or 'none'}", sug)):
            n += 1
    # also pull protocol junk pairs if any thought still has distinct ids
    for m in cur.execute(
        "SELECT node_id, reasoning, confidence_in_decision, evidence_used, created_at "
        "FROM thought_chains WHERE action='merge' AND reasoning LIKE '%brain-protocol%' "
        "ORDER BY created_at DESC LIMIT 20"
    ):
        if n >= 16:
            break
        nid = m["node_id"]
        try:
            ev = json.loads(m["evidence_used"] or "[]")
        except Exception:
            ev = []
        others = [e for e in ev if isinstance(e, str) and e != nid and e in norms]
        # if self-ref only, try to pair with another protocol-ish deprecated node
        if not others:
            cont = False
            for r2 in cur.execute(
                "SELECT id FROM knowledge_nodes WHERE id!=? AND stage='deprecated' "
                "AND (summary LIKE '%brain-protocol%' OR content LIKE '%brain-protocol%') LIMIT 5",
                (nid,),
            ):
                if r2["id"] in norms and pair_id(nid, r2["id"]) not in seen:
                    others = [r2["id"]]
                    break
        for other in others:
            if add(make_item(nid, other, "historical_merge",
                             f"thought_merge_protocol@{(m['created_at'] or '')[:10]}", "unrelated")):
                n += 1
                break
    print("historical_merge exported", n)

    stratum_order = [
        "positive_exact_dup", "related_ge_0.92", "related_0.90_0.92",
        "related_0.88_0.90", "related_0.86_0.88", "near_miss_0.78_0.86",
        "hard_neg_emb_high_text_low", "clear_unrelated", "historical_merge",
    ]
    order = {s: i for i, s in enumerate(stratum_order)}
    items.sort(key=lambda x: (order.get(x["stratum"], 99), -x["emb"], x["pair_id"]))

    gold_path = args.out_dir / "gold_pairs.jsonl"
    with gold_path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    pre_path = args.out_dir / "gold_pairs.suggested.jsonl"
    with pre_path.open("w", encoding="utf-8") as f:
        for it in items:
            it2 = dict(it)
            if it2.get("suggested_label"):
                it2["label"] = it2["suggested_label"]
                it2["labeler"] = "auto_suggested"
            f.write(json.dumps(it2, ensure_ascii=False) + "\n")

    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "db": args.db,
        "n_pairs": len(items),
        "seed": args.seed,
        "strata": dict(collections.Counter(i["stratum"] for i in items)),
        "label_schema": ["exact_dup", "related", "unrelated"],
        "label_guide": {
            "exact_dup": "Same durable rule; safe to merge into one node.",
            "related": "Same topic family; constellation link OK, do NOT merge.",
            "unrelated": "Should not link or merge (junk / path-only similarity).",
        },
        "files": {"unlabeled": str(gold_path), "suggested_seed": str(pre_path)},
        "how_to_label": [
            "cp eval/gold_pairs.jsonl eval/gold_pairs.labeled.jsonl",
            "Edit label=exact_dup|related|unrelated; set labeler=you",
            "Or start from gold_pairs.suggested.jsonl and correct mistakes",
            ".venv/bin/python scripts/eval_brain_thresholds.py --gold eval/gold_pairs.labeled.jsonl --tag v1",
        ],
    }
    (args.out_dir / "gold_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("TOTAL", len(items))
    print("strata", meta["strata"])
    print("wrote", gold_path)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
