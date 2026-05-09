"""Hermes Brain V2: Embedding-based semantic similarity.

Uses fastembed (BAAI/bge-small-en-v1.5) for local embedding.
Falls back to text similarity if fastembed is unavailable.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded model singleton
_model = None
_model_dim = 384  # bge-small-en-v1.5 dimension


def _get_model():
    """Lazy-load the embedding model."""
    global _model
    if _model is not None:
        return _model
    
    # Check if embedding is explicitly disabled
    if os.environ.get("BRAIN_DISABLE_EMBEDDINGS", "").lower() in ("1", "true", "yes"):
        logger.info("Embeddings disabled by BRAIN_DISABLE_EMBEDDINGS env var")
        return None
    
    try:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        logger.info("Loaded fastembed model BAAI/bge-small-en-v1.5 (dim=%d)", _model_dim)
        return _model
    except ImportError:
        logger.warning("fastembed not available, falling back to text similarity")
        return None
    except Exception as e:
        logger.warning("Failed to load embedding model: %s, falling back to text similarity", e)
        return None


def embed_texts(texts: list[str]) -> list[np.ndarray] | None:
    """Embed a list of texts. Returns None if embedding is unavailable."""
    model = _get_model()
    if model is None or not texts:
        return None
    
    try:
        embeddings = list(model.embed(texts))
        return [np.array(e) for e in embeddings]
    except Exception as e:
        logger.warning("Embedding failed: %s", e)
        return None


def embed_text(text: str) -> np.ndarray | None:
    """Embed a single text. Returns None if embedding is unavailable."""
    results = embed_texts([text])
    if results is None:
        return None
    return results[0]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def embedding_similarity(text_a: str, text_b: str) -> float | None:
    """Compute embedding-based similarity between two texts.
    
    Returns None if embeddings are unavailable.
    Returns a float in [0, 1] if available.
    """
    embs = embed_texts([text_a, text_b])
    if embs is None:
        return None
    return cosine_similarity(embs[0], embs[1])


def batch_embedding_similarity(query: str, candidates: list[str]) -> list[tuple[int, float]] | None:
    """Compute similarity between a query and multiple candidates.
    
    Returns list of (index, similarity) sorted by similarity descending,
    or None if embeddings are unavailable.
    """
    if not candidates:
        return []
    
    all_texts = [query] + candidates
    embs = embed_texts(all_texts)
    if embs is None:
        return None
    
    query_emb = embs[0]
    results = []
    for i, emb in enumerate(embs[1:]):
        sim = cosine_similarity(query_emb, emb)
        results.append((i, sim))
    
    results.sort(key=lambda x: x[1], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Hybrid similarity: embedding + text
# ---------------------------------------------------------------------------

from hermes.integrate import _text_similarity

def hybrid_similarity(text_a: str, text_b: str, *, embedding_weight: float = 0.7) -> float:
    """Compute hybrid similarity combining embedding and text similarity.
    
    When embeddings are available:
        hybrid = embedding_weight * embedding_sim + (1 - embedding_weight) * text_sim
    When embeddings are unavailable:
        hybrid = text_sim (fallback)
    
    Args:
        text_a: First text
        text_b: Second text
        embedding_weight: Weight for embedding similarity (0.0-1.0). Default 0.7.
    
    Returns:
        Similarity score in [0, 1]
    """
    emb_sim = embedding_similarity(text_a, text_b)
    txt_sim = _text_similarity(text_a, text_b)
    
    if emb_sim is not None:
        return embedding_weight * emb_sim + (1 - embedding_weight) * txt_sim
    else:
        return txt_sim