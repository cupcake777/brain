#!/usr/bin/env python3
"""Standalone Brain dedup script — runs anywhere with Python + fastembed.

Usage:
    python dedup_standalone.py                          # full run on local DB
    python dedup_standalone.py --dry-run                 # preview only
    python dedup_standalone.py --db-path /path/to/db    # custom DB path
    python dedup_standalone.py --merge-threshold 0.85   # custom thresholds
"""

import argparse
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Node:
    """Minimal knowledge node for dedup."""
    id: str
    summary: str
    content: str
    stage: str
    confidence: float
    domain: str


def load_nodes(db_path: str) -> list[Node]:
    """Load active (non-deprecated) knowledge nodes from SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, summary, COALESCE(content,'') as content, stage, "
        "COALESCE(confidence,0.5) as confidence, domain "
        "FROM knowledge_nodes WHERE stage != 'deprecated'"
    ).fetchall()
    conn.close()
    return [Node(r['id'], r['summary'], r['content'], r['stage'],
                  r['confidence'], r['domain']) for r in rows]


def _tokenize_unicode(text: str) -> set[str]:
    """CJK-aware tokenizer: splits CJK chars individually, keeps Latin words."""
    tokens = set()
    for part in re.findall(r'[a-z0-9_]+|[\u4e00-\u9fff]', text.lower()):
        tokens.add(part)
    return tokens


def text_similarity(a: str, b: str) -> float:
    """Jaccard similarity on unicode-aware tokens."""
    ta, tb = _tokenize_unicode(a), _tokenize_unicode(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def deprecate_nodes(db_path: str, node_ids: list[str], dry_run: bool = False) -> int:
    """Mark nodes as deprecated in DB."""
    if dry_run or not node_ids:
        return 0
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    placeholders = ','.join('?' * len(node_ids))
    conn.execute(
        f"UPDATE knowledge_nodes SET stage='deprecated', deprecated_at=? "
        f"WHERE id IN ({placeholders}) AND stage != 'deprecated'",
        [now] + node_ids
    )
    conn.commit()
    count = conn.total_changes
    conn.close()
    return count


def run_dedup(db_path: str, merge_threshold: float, review_threshold: float,
              dry_run: bool = False) -> tuple[list, list, int]:
    """Main dedup logic. Returns (merge_pairs, review_pairs, deprecated_count)."""
    nodes = load_nodes(db_path)
    print(f"Loaded {len(nodes)} active nodes from {db_path}")

    # Try embedding mode
    use_embeddings = os.environ.get("BRAIN_DISABLE_EMBEDDINGS", "").lower() not in ("1", "true", "yes")
    embs = None

    if use_embeddings:
        try:
            from fastembed import TextEmbedding
            import numpy as np

            print("Loading fastembed model...")
            model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            summaries = [n.summary for n in nodes]

            print(f"Embedding {len(summaries)} summaries...")
            emb_list = list(model.embed(summaries))
            emb_matrix = np.array(emb_list, dtype=np.float32)

            # Normalize
            norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1
            emb_matrix = emb_matrix / norms

            print("Computing pairwise similarity...")
            sim_matrix = emb_matrix @ emb_matrix.T
            embs = sim_matrix
            print("Embedding dedup ready.")
        except Exception as e:
            print(f"Embedding failed ({e}), falling back to text-only.")
            embs = None

    merge_pairs = []
    review_pairs = []
    deprecated_ids = set()

    if embs is not None:
        # Embedding-based pairwise comparison
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                sim = float(embs[i, j])
                if sim > merge_threshold:
                    merge_pairs.append((sim, nodes[i], nodes[j]))
                elif sim > review_threshold:
                    review_pairs.append((sim, nodes[i], nodes[j]))

        # Also check CJK↔Latin with text similarity (embedding may miss these)
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                sim = float(embs[i, j])
                if sim < review_threshold:  # embedding says not similar
                    txt_sim = max(text_similarity(nodes[i].summary, nodes[j].summary),
                                  text_similarity(nodes[i].content, nodes[j].content))
                    # Numeric overlap rescue
                    nums_i = set(re.findall(r'\d{2,}', nodes[i].summary + ' ' + nodes[i].content))
                    nums_j = set(re.findall(r'\d{2,}', nodes[j].summary + ' ' + nodes[j].content))
                    if nums_i and nums_j and nums_i & nums_j:
                        hybrid = 0.7 * sim + 0.3 * txt_sim
                        if hybrid > merge_threshold:
                            merge_pairs.append((hybrid, nodes[i], nodes[j]))
                        elif hybrid > review_threshold:
                            review_pairs.append((hybrid, nodes[i], nodes[j]))
    else:
        # Text-only mode with lower thresholds
        merge_threshold = max(merge_threshold, 0.55)
        review_threshold = max(review_threshold, 0.35)
        print(f"Text-only mode: merge={merge_threshold:.2f}, review={review_threshold:.2f}")

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                sim = max(text_similarity(nodes[i].summary, nodes[j].summary),
                          text_similarity(nodes[i].content, nodes[j].content))
                if sim > merge_threshold:
                    merge_pairs.append((sim, nodes[i], nodes[j]))
                elif sim > review_threshold:
                    review_pairs.append((sim, nodes[i], nodes[j]))

    # Sort by similarity descending
    merge_pairs.sort(key=lambda x: -x[0])
    review_pairs.sort(key=lambda x: -x[0])

    # Auto-deprecate merge pairs (keep higher confidence)
    print(f"\n=== MERGE candidates (sim > {merge_threshold:.2f}): {len(merge_pairs)} ===")
    for sim, a, b in merge_pairs:
        keep, drop = (a, b) if a.confidence >= b.confidence else (b, a)
        print(f"  sim={sim:.3f}  KEEP [{keep.stage}] c={keep.confidence:.2f} {keep.summary[:80]}")
        print(f"            DROP [{drop.stage}] c={drop.confidence:.2f} {drop.summary[:80]}")
        if drop.id not in deprecated_ids:
            deprecated_ids.add(drop.id)

    print(f"\n=== REVIEW candidates (sim {review_threshold:.2f}-{merge_threshold:.2f}): {len(review_pairs)} ===")
    for sim, a, b in review_pairs[:15]:
        print(f"  sim={sim:.3f}")
        print(f"    [{a.stage}] c={a.confidence:.2f} {a.summary[:80]}")
        print(f"    [{b.stage}] c={b.confidence:.2f} {b.summary[:80]}")
    if len(review_pairs) > 15:
        print(f"  ... and {len(review_pairs) - 15} more")

    dep_count = 0
    if not dry_run and deprecated_ids:
        dep_count = deprecate_nodes(db_path, list(deprecated_ids))
        print(f"\nDeprecated {dep_count} nodes.")
    elif dry_run:
        print(f"\nDry run: would deprecate {len(deprecated_ids)} nodes.")

    return merge_pairs, review_pairs, dep_count


def main():
    parser = argparse.ArgumentParser(description="Brain knowledge dedup standalone script")
    parser.add_argument("--db-path", default="/root/hermes-sync/hermes.sqlite3",
                        help="Path to SQLite database")
    parser.add_argument("--merge-threshold", type=float, default=0.85,
                        help="Similarity threshold for merge (default: 0.85)")
    parser.add_argument("--review-threshold", type=float, default=0.55,
                        help="Similarity threshold for review (default: 0.55)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, no DB changes")
    args = parser.parse_args()

    if not Path(args.db_path).exists():
        print(f"Error: DB not found at {args.db_path}")
        sys.exit(1)

    merge, review, dep = run_dedup(
        args.db_path, args.merge_threshold, args.review_threshold, args.dry_run
    )
    print(f"\nSummary: {len(merge)} merge, {len(review)} review, {dep} deprecated")


if __name__ == "__main__":
    main()