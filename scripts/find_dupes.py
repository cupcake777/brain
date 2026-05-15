#!/usr/bin/env python3
"""Find duplicate knowledge nodes using text + embedding similarity."""

import re
import sys
import sqlite3
import gc

sys.path.insert(0, '/root/ops/brain')

from hermes.integrate import _text_similarity

# --- Step 1: Load active nodes ---
DB = '/root/hermes-sync/hermes.sqlite3'
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT id, summary, stage, category FROM knowledge_nodes WHERE stage != 'deprecated'")
rows = cur.fetchall()
nodes = [dict(r) for r in rows]
conn.close()

print(f"Loaded {len(nodes)} active knowledge nodes")

# --- Step 2: Compute text similarity for all pairs, collect candidates ---
NUM_RE = re.compile(r'\b\d{2,}\b')  # 2+ digit numbers

def get_numeric_tokens(text):
    return set(NUM_RE.findall(text))

candidates = []  # (i, j, text_sim)
total_pairs = len(nodes) * (len(nodes) - 1) // 2
print(f"Computing text similarity for {total_pairs} pairs...")

for i in range(len(nodes)):
    for j in range(i + 1, len(nodes)):
        ts = _text_similarity(nodes[i]['summary'], nodes[j]['summary'])
        # Check if text_sim > 0.35 OR shared 2+ digit numeric tokens
        if ts > 0.35:
            candidates.append((i, j, ts, 'text_sim'))
        else:
            nums_i = get_numeric_tokens(nodes[i]['summary'])
            nums_j = get_numeric_tokens(nodes[j]['summary'])
            if nums_i and nums_j and (nums_i & nums_j):
                candidates.append((i, j, ts, 'shared_nums'))

print(f"Found {len(candidates)} candidate pairs for embedding check")
if not candidates:
    print("No candidates found. Exiting.")
    sys.exit(0)

# --- Step 3: Load embedding model and compute embedding similarity ---
print("Loading embedding model...")
from hermes.embedding import _get_model, cosine_similarity
model = _get_model()
if model is None:
    print("ERROR: Could not load embedding model")
    sys.exit(1)
print("Embedding model loaded.")

# Collect all unique node indices involved in candidates
needed_indices = set()
for i, j, ts, reason in candidates:
    needed_indices.add(i)
    needed_indices.add(j)

needed_list = sorted(needed_indices)
print(f"Need to embed {len(needed_list)} unique node summaries")

# Embed in batches of 20
BATCH = 20
embeddings = {}  # index -> numpy array

for batch_start in range(0, len(needed_list), BATCH):
    batch_indices = needed_list[batch_start:batch_start + BATCH]
    texts = [nodes[idx]['summary'] for idx in batch_indices]
    try:
        embs = list(model.embed(texts))
        for idx, emb in zip(batch_indices, embs):
            import numpy as np
            embeddings[idx] = np.array(emb)
        print(f"  Embedded batch {batch_start//BATCH + 1}: nodes {batch_indices[0]}-{batch_indices[-1]}")
    except Exception as e:
        print(f"  ERROR in batch {batch_start//BATCH + 1}: {e}")
    gc.collect()

print(f"Embedded {len(embeddings)} / {len(needed_list)} nodes")

# --- Step 4: Compute embedding similarity for candidates ---
results = []
for i, j, ts, reason in candidates:
    if i not in embeddings or j not in embeddings:
        continue
    emb_sim = float(cosine_similarity(embeddings[i], embeddings[j]))
    if emb_sim > 0.70:
        results.append((emb_sim, ts, i, j, reason))

results.sort(key=lambda x: x[0], reverse=True)

# --- Report ---
print(f"\n{'='*120}")
print(f"DUPLICATE PAIRS (embedding similarity > 0.70): {len(results)} found")
print(f"{'='*120}")
print(f"{'EmbSim':>7} {'TxtSim':>7} {'ID_A':>38} {'ID_B':>38} {'Stage_A':>10} {'Stage_B':>10}  Summary_A ~ Summary_B")
print(f"{'-'*7} {'-'*7} {'-'*38} {'-'*38} {'-'*10} {'-'*10}  {'-'*60}")

for emb_sim, ts, i, j, reason in results:
    a = nodes[i]
    b = nodes[j]
    sa = a['summary'][:80] if a['summary'] else ''
    sb = b['summary'][:80] if b['summary'] else ''
    print(f"{emb_sim:7.4f} {ts:7.4f} {a['id']:>38} {b['id']:>38} {a['stage']:>10} {b['stage']:>10}  {sa}")
    print(f"{'':>7} {'':>7} {'':>38} {'':>38} {'':>10} {'':>10}  {sb}")
    print()

print(f"\nTotal duplicate pairs found: {len(results)}")
