"""Persistent embedding support for Brain proposals and knowledge nodes.

The production provider is an OpenAI-compatible remote endpoint.  The module
uses only httpx and the standard library so the Brain service does not need a
local model or numpy.  Callers can fall back to lexical search when the
provider is disabled or temporarily unavailable.
"""
from __future__ import annotations

from array import array
import hashlib
import logging
import math
import os
from typing import Sequence

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"
_embed_cache: dict[str, list[float]] = {}


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def provider_config() -> dict[str, object]:
    """Return non-secret provider configuration and readiness."""
    disabled = _truthy(os.environ.get("BRAIN_DISABLE_EMBEDDINGS"))
    base_url = os.environ.get("EMBED_BASE_URL", "").rstrip("/")
    model = os.environ.get("EMBED_MODEL", DEFAULT_MODEL)
    has_auth = bool(os.environ.get("EMBED_API_KEY") or (
        os.environ.get("EMBED_USERNAME") and os.environ.get("EMBED_PASSWORD")
    ))
    return {
        "enabled": not disabled and bool(base_url) and has_auth,
        "disabled": disabled,
        "configured": bool(base_url) and has_auth,
        "provider": "openai-compatible-remote",
        "model": model,
        "base_url": base_url,
    }


def _endpoint(base_url: str) -> str:
    return base_url if base_url.endswith("/embeddings") else f"{base_url}/embeddings"


def _headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        # This endpoint is protected by Cloudflare; keep the known-good UA.
        "User-Agent": "python-httpx/0.28.1",
    }
    api_key = os.environ.get("EMBED_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _cache_key(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}\0{text}".encode("utf-8")).hexdigest()


def embed_texts(texts: Sequence[str]) -> list[list[float]] | None:
    """Embed texts through the configured provider; return None if disabled.

    Provider errors are raised so backfill code can persist an actionable
    failure state.  Empty input returns an empty list.
    """
    if not texts:
        return []
    config = provider_config()
    if not config["enabled"]:
        return None

    model = str(config["model"])
    cleaned = [str(text).strip() for text in texts]
    missing: list[str] = []
    for text in cleaned:
        key = _cache_key(text, model)
        if key not in _embed_cache:
            missing.append(text)

    if missing:
        auth = None
        if "Authorization" not in _headers():
            username = os.environ.get("EMBED_USERNAME", "")
            password = os.environ.get("EMBED_PASSWORD", "")
            if username and password:
                auth = httpx.BasicAuth(username, password)
        timeout = httpx.Timeout(45.0, connect=10.0)
        with httpx.Client(timeout=timeout, auth=auth, follow_redirects=True) as client:
            response = client.post(
                _endpoint(str(config["base_url"])),
                headers=_headers(),
                json={"model": model, "input": missing},
            )
            response.raise_for_status()
            payload = response.json()
        rows = sorted(payload.get("data", []), key=lambda item: int(item.get("index", 0)))
        if len(rows) != len(missing):
            raise RuntimeError(f"embedding provider returned {len(rows)} vectors for {len(missing)} texts")
        for text, row in zip(missing, rows):
            vector = [float(value) for value in row.get("embedding", [])]
            if not vector:
                raise RuntimeError("embedding provider returned an empty vector")
            _embed_cache[_cache_key(text, model)] = vector

    return [_embed_cache[_cache_key(text, model)] for text in cleaned]


def embed_text(text: str) -> list[float] | None:
    vectors = embed_texts([text])
    return None if vectors is None else vectors[0]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def vector_to_blob(vector: Sequence[float]) -> bytes:
    values = array("f", (float(value) for value in vector))
    return values.tobytes()


def blob_to_vector(blob: bytes, dimension: int) -> list[float]:
    values = array("f")
    values.frombytes(blob)
    if len(values) != int(dimension):
        raise ValueError(f"stored vector dimension mismatch: expected {dimension}, got {len(values)}")
    return list(values)


def embedding_similarity(text_a: str, text_b: str) -> float | None:
    vectors = embed_texts([text_a, text_b])
    if vectors is None:
        return None
    return cosine_similarity(vectors[0], vectors[1])


def batch_embedding_similarity(query: str, candidates: list[str]) -> list[tuple[int, float]] | None:
    if not candidates:
        return []
    vectors = embed_texts([query, *candidates])
    if vectors is None:
        return None
    ranked = [(index, cosine_similarity(vectors[0], vector)) for index, vector in enumerate(vectors[1:])]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def hybrid_similarity(text_a: str, text_b: str, *, embedding_weight: float = 0.7) -> float:
    from hermes.integrate import _text_similarity

    semantic = embedding_similarity(text_a, text_b)
    lexical = _text_similarity(text_a, text_b)
    return lexical if semantic is None else embedding_weight * semantic + (1.0 - embedding_weight) * lexical
