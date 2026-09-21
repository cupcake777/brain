# Brain threshold / constellation evaluation

All commands below run from the repository root.

## Why

Batch dedup / related edges used heuristic thresholds (merge hybrid 0.85, related cos 0.78→0.86).
There is no public benchmark for *this* knowledge base. This folder holds:

1. **L1 hygiene** — automatic regression (junk nodes, exact dups, cos floor, emb coverage)
2. **Gold pairs** — stratified samples for human labels
3. **Threshold sweep** — precision/recall/F1 on labeled gold

## Label schema

| label | meaning |
|-------|---------|
| `exact_dup` | Same durable rule → safe merge |
| `related` | Same topic family → constellation OK, do **not** merge |
| `unrelated` | No link / no merge |

## Workflow

```bash
# 1) (re)export stratified pairs
.venv/bin/python scripts/export_gold_pairs.py

# 2) label
cp eval/gold_pairs.jsonl eval/gold_pairs.labeled.jsonl
# edit each line: "label":"exact_dup|related|unrelated", "labeler":"you"
# optional seed: start from eval/gold_pairs.suggested.jsonl and correct

# 3) L1 hygiene only
.venv/bin/python scripts/eval_brain_thresholds.py --hygiene-only

# 4) threshold PR sweep (suggested seeds = dry run only)
.venv/bin/python scripts/eval_brain_thresholds.py \
  --gold eval/gold_pairs.suggested.jsonl --tag suggested --allow-suggested

# real gold
.venv/bin/python scripts/eval_brain_thresholds.py \
  --gold eval/gold_pairs.labeled.jsonl --tag v1

# 5) pytest hygiene
.venv/bin/pytest tests/test_knowledge_hygiene.py -q
```

## Acceptance targets (after human gold)

| task | target |
|------|--------|
| Merge @ hybrid | P ≥ 0.95, R ≥ 0.80 |
| Related @ emb | P ≥ 0.80 (prefer high P) |
| Hygiene | pass = true |

## Files

- `gold_pairs.jsonl` — unlabeled
- `gold_pairs.suggested.jsonl` — heuristic seed labels (not ground truth)
- `gold_meta.json` — stratum counts
- `threshold_eval_*.json` — sweep outputs
- `../scripts/export_gold_pairs.py`
- `../scripts/eval_brain_thresholds.py`
- `../tests/test_knowledge_hygiene.py`


## Web labeler

```bash
.venv/bin/python scripts/label_server.py
# open http://127.0.0.1:8789/
```

- Left sidebar: label rules + keyboard shortcuts (always visible)
- Saves to `eval/gold_pairs.labeled.jsonl` on every label
- Keys: `1` exact_dup · `2` related · `3` unrelated · `j/k` next/prev

Remote access example:

```bash
ssh -L 8789:127.0.0.1:8789 YOUR-BRAIN-HOST
# then http://127.0.0.1:8789/
```

To expose the labeler through an authenticated Brain deployment, add an operator-owned route and use that deployment's URL. No public hostname is embedded in this repository.
