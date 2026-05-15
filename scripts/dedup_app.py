"""Gradio app for Brain dedup — deploy as HF Space.

1. Upload hermes.sqlite3
2. Choose mode (embedding/text-only) and thresholds
3. Run dedup
4. Review merge/review pairs
5. Download updated DB
"""

import gradio as gr
import sqlite3
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass

# --- Core logic (inline, no hermes dependency) ---

@dataclass(frozen=True)
class Node:
    id: str
    summary: str
    content: str
    stage: str
    confidence: float
    domain: str


def load_nodes(db_path: str) -> list[Node]:
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
    tokens = set()
    for part in re.findall(r'[a-z0-9_]+|[\u4e00-\u9fff]', text.lower()):
        tokens.add(part)
    return tokens


def text_similarity(a: str, b: str) -> float:
    ta, tb = _tokenize_unicode(a), _tokenize_unicode(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def run_dedup(db_path: str, use_embedding: bool, merge_th: float, review_th: float):
    nodes = load_nodes(db_path)
    log = [f"Loaded {len(nodes)} active nodes"]

    merge_pairs = []
    review_pairs = []
    deprecated_ids = set()

    if use_embedding:
        try:
            from fastembed import TextEmbedding
            import numpy as np

            log.append("Loading fastembed model...")
            model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            summaries = [n.summary for n in nodes]
            log.append(f"Embedding {len(summaries)} summaries...")
            emb_list = list(model.embed(summaries))
            emb_matrix = np.array(emb_list, dtype=np.float32)
            norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1
            emb_matrix = emb_matrix / norms
            log.append("Computing pairwise similarity...")
            sim_matrix = emb_matrix @ emb_matrix.T

            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    sim = float(sim_matrix[i, j])
                    if sim > merge_th:
                        merge_pairs.append((sim, nodes[i], nodes[j]))
                    elif sim > review_th:
                        review_pairs.append((sim, nodes[i], nodes[j]))

            # CJK rescue
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    sim = float(sim_matrix[i, j])
                    if sim < review_th:
                        txt_sim = max(text_similarity(nodes[i].summary, nodes[j].summary),
                                      text_similarity(nodes[i].content, nodes[j].content))
                        nums_i = set(re.findall(r'\d{2,}', nodes[i].summary + ' ' + nodes[i].content))
                        nums_j = set(re.findall(r'\d{2,}', nodes[j].summary + ' ' + nodes[j].content))
                        if nums_i and nums_j and nums_i & nums_j:
                            hybrid = 0.7 * sim + 0.3 * txt_sim
                            if hybrid > merge_th:
                                merge_pairs.append((hybrid, nodes[i], nodes[j]))
                            elif hybrid > review_th:
                                review_pairs.append((hybrid, nodes[i], nodes[j]))
            log.append(f"Embedding mode: {len(merge_pairs)} merge, {len(review_pairs)} review")
        except Exception as e:
            log.append(f"Embedding failed: {e}, falling back to text-only")
            use_embedding = False
            merge_th = max(merge_th, 0.55)
            review_th = max(review_th, 0.35)

    if not use_embedding:
        merge_th = max(merge_th, 0.55)
        review_th = max(review_th, 0.35)
        log.append(f"Text-only mode: merge={merge_th:.2f}, review={review_th:.2f}")
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                sim = max(text_similarity(nodes[i].summary, nodes[j].summary),
                          text_similarity(nodes[i].content, nodes[j].content))
                if sim > merge_th:
                    merge_pairs.append((sim, nodes[i], nodes[j]))
                elif sim > review_th:
                    review_pairs.append((sim, nodes[i], nodes[j]))

    merge_pairs.sort(key=lambda x: -x[0])
    review_pairs.sort(key=lambda x: -x[0])

    # Build report
    lines = [f"## Results: {len(merge_pairs)} merge, {len(review_pairs)} review\n"]
    lines.append(f"### MERGE pairs (auto-deprecate lower confidence):\n")
    for sim, a, b in merge_pairs:
        keep, drop = (a, b) if a.confidence >= b.confidence else (b, a)
        lines.append(f"- sim={sim:.3f} **KEEP** [{keep.stage}] c={keep.confidence:.2f}: {keep.summary[:80]}")
        lines.append(f"  ~~DROP~~ [{drop.stage}] c={drop.confidence:.2f}: {drop.summary[:80]}")
        if drop.id not in deprecated_ids:
            deprecated_ids.add(drop.id)

    lines.append(f"\n### REVIEW pairs (manual check):\n")
    for sim, a, b in review_pairs[:30]:
        lines.append(f"- sim={sim:.3f}")
        lines.append(f"  [{a.stage}] c={a.confidence:.2f}: {a.summary[:80]}")
        lines.append(f"  [{b.stage}] c={b.confidence:.2f}: {b.summary[:80]}")
    if len(review_pairs) > 30:
        lines.append(f"\n... and {len(review_pairs) - 30} more review pairs")

    lines.append(f"\n**Will deprecate {len(deprecated_ids)} nodes**")

    return "\n".join(log), "\n".join(lines), list(deprecated_ids), db_path


def apply_dedup(db_path: str, ids_to_deprecate: str):
    """Apply deprecation to DB and return updated file path."""
    if not ids_to_deprecate or ids_to_deprecate.strip() == "[]":
        return db_path, "No changes to apply"

    import ast
    try:
        ids = ast.literal_eval(ids_to_deprecate)
    except:
        return db_path, "Error parsing ID list"

    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    placeholders = ','.join('?' * len(ids))
    conn.execute(
        f"UPDATE knowledge_nodes SET stage='deprecated', deprecated_at=? "
        f"WHERE id IN ({placeholders}) AND stage != 'deprecated'",
        [now] + ids
    )
    conn.commit()
    count = conn.total_changes
    conn.close()
    return db_path, f"Deprecated {count} nodes"


# --- Gradio UI ---

with gr.Blocks(title="Brain Dedup", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🧠 Brain Knowledge Dedup\nUpload hermes.sqlite3, run dedup, download updated DB.")

    with gr.Row():
        db_file = gr.File(label="Upload hermes.sqlite3", file_types=[".sqlite3", ".db"])
        mode = gr.Radio(["Embedding (fastembed)", "Text-only"], value="Embedding (fastembed)", label="Mode")
        merge_th = gr.Slider(0.5, 1.0, value=0.85, step=0.05, label="Merge threshold")
        review_th = gr.Slider(0.3, 0.85, value=0.55, step=0.05, label="Review threshold")

    run_btn = gr.Button("🔍 Run Dedup", variant="primary")
    log_out = gr.Textbox(label="Log", lines=5)
    report_out = gr.Markdown(label="Results")
    ids_state = gr.State(value="[]")
    db_state = gr.State(value=None)

    apply_btn = gr.Button("✅ Apply Deprecation & Download", variant="secondary")
    apply_out = gr.Textbox(label="Apply result")
    download_file = gr.File(label="Download updated DB")

    def on_run(file, mode, merge, review):
        if file is None:
            return "Error: upload a DB file first", "", "[]", None
        use_emb = mode.startswith("Embedding")
        import shutil, tempfile
        tmp = tempfile.mktemp(suffix=".sqlite3")
        shutil.copy2(file.name, tmp)
        log, report, ids, db = run_dedup(tmp, use_emb, merge, review)
        return log, report, str(ids), db

    run_btn.click(on_run, [db_file, mode, merge_th, review_th],
                  [log_out, report_out, ids_state, db_state])

    def on_apply(db_path, ids_str):
        if db_path is None:
            return "No DB loaded", None
        updated_path, msg = apply_dedup(db_path, ids_str)
        return msg, updated_path

    apply_btn.click(on_apply, [db_state, ids_state], [apply_out, download_file])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)