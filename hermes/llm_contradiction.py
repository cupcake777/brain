"""Hermes Brain V2: LLM-powered contradiction detection.

Uses the local api_server (Hermes gateway) for LLM calls.
Falls back to heuristic detection if LLM is unavailable.
"""
from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_API_BASE_URL = os.environ.get("BRAIN_API_URL", "http://127.0.0.1:8642")
_API_KEY = os.environ.get("BRAIN_API_KEY", "hermes-webui-2026")
_LLM_MODEL = os.environ.get("BRAIN_LLM_MODEL", "glm-5.1")
_LLM_TIMEOUT = int(os.environ.get("BRAIN_LLM_TIMEOUT", "15"))
_LLM_ENABLED = os.environ.get("BRAIN_LLM_ENABLED", "1").lower() not in ("0", "false", "no")

# ---------------------------------------------------------------------------
# Contradiction detection prompt
# ---------------------------------------------------------------------------

CONTRADICTION_PROMPT = """You are a knowledge consistency checker. Given a new knowledge claim and existing knowledge claims, determine if they contradict each other.

New claim: {new_content}
Existing claim: {existing_content}

Respond with ONLY a JSON object (no markdown, no explanation outside JSON):
{{
  "is_contradiction": true/false,
  "severity": "critical" | "minor" | "none",
  "resolution": "prefer_new" | "prefer_existing" | "both_valid" | "merge",
  "explanation": "brief explanation of the relationship"
}}"""


def llm_check_contradiction(
    new_content: str,
    existing_content: str,
    *,
    model: str | None = None,
    timeout: int | None = None,
) -> dict | None:
    """Check if new knowledge contradicts existing knowledge using LLM.

    Returns dict with keys: is_contradiction, severity, resolution, explanation.
    Returns None if LLM is unavailable or disabled.
    """
    if not _LLM_ENABLED:
        return None

    model = model or _LLM_MODEL
    timeout = timeout or _LLM_TIMEOUT

    prompt = CONTRADICTION_PROMPT.format(
        new_content=new_content[:500],
        existing_content=existing_content[:500],
    )

    try:
        response = httpx.post(
            f"{_API_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.1,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"].strip()

        # Parse JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)

        # Validate required fields
        if "is_contradiction" in result:
            return {
                "is_contradiction": bool(result.get("is_contradiction", False)),
                "severity": result.get("severity", "minor"),
                "resolution": result.get("resolution", "both_valid"),
                "explanation": result.get("explanation", ""),
            }

    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning("LLM contradiction check failed: %s", e)
    except Exception as e:
        logger.warning("Unexpected error in LLM contradiction check: %s", e)

    return None


def batch_llm_contradiction_check(
    new_content: str,
    existing_nodes: list,
    *,
    max_candidates: int = 3,
) -> list[dict]:
    """Check new knowledge against multiple existing nodes for contradictions.

    Returns list of dicts with: node_id, node_summary, result (from llm_check_contradiction).
    Only checks top candidates (by text similarity).
    """
    from hermes.integrate import _text_similarity

    results = []
    # Sort by similarity and take top candidates
    candidates = []
    for node in existing_nodes:
        if node.stage == "deprecated":
            continue
        sim = max(
            _text_similarity(new_content, node.summary),
            _text_similarity(new_content, node.content),
        )
        if sim > 0.3:  # Only check somewhat similar nodes
            candidates.append((node, sim))

    candidates.sort(key=lambda x: x[1], reverse=True)

    for node, sim in candidates[:max_candidates]:
        llm_result = llm_check_contradiction(new_content, node.content)
        if llm_result and llm_result.get("is_contradiction"):
            results.append({
                "node_id": node.id,
                "node_summary": node.summary[:80],
                "severity": llm_result["severity"],
                "resolution": llm_result["resolution"],
                "explanation": llm_result["explanation"],
                "similarity": round(sim, 3),
            })

    return results