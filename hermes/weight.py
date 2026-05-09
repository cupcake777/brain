"""Weight computation for Brain proposals.

Weight is a composite score (0.5–5.0) that determines:
- Export ordering: higher weight → appears first in CLAUDE.md
- Eviction priority: lower weight → demoted first when budget pressure occurs
- Manual override: can be set directly via API or CLI

Formula:
    weight = clamp(base(category) + risk_bonus(risk_level) + retrieval_bonus, 0.5, 5.0)

Where:
    base_score:  rule=2.0, workflow_hint=1.5, preference=1.0, fact=0.5
    risk_bonus:  high=+1.5, medium=+1.0, low=+0.0
    retrieval:   +0.1 per retrieval in last 30d, capped at +1.0
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Category base scores (foundation of importance)
# ---------------------------------------------------------------------------
_CATEGORY_SCORES: dict[str, float] = {
    "rule": 2.0,           # Hard rules are most important
    "workflow_hint": 1.5,  # Useful but less critical
    "preference": 1.0,    # User preferences, moderate importance
    "fact": 0.5,          # Ambient facts, lowest priority
}

# ---------------------------------------------------------------------------
# Risk level bonuses (urgency / impact multiplier)
# ---------------------------------------------------------------------------
_RISK_BONUSES: dict[str, float] = {
    "high": 1.5,    # Must-not-break rules
    "medium": 1.0,  # Should-follow rules
    "low": 0.0,     # Nice-to-know
}

# ---------------------------------------------------------------------------
# Retrieval bonus configuration
# ---------------------------------------------------------------------------
_RETRIEVAL_BONUS_PER_HIT = 0.1
_RETRIEVAL_BONUS_CAP = 1.0

# ---------------------------------------------------------------------------
# Weight bounds
# ---------------------------------------------------------------------------
_WEIGHT_MIN = 0.5
_WEIGHT_MAX = 5.0


def compute_weight(
    *,
    category: str,
    risk_level: str,
    retrieval_count_30d: int = 0,
) -> float:
    """Compute composite weight for a proposal.

    Returns a float in [0.5, 5.0].
    """
    base = _CATEGORY_SCORES.get(category, 1.0)
    risk = _RISK_BONUSES.get(risk_level, 0.0)
    retrieval = min(retrieval_count_30d * _RETRIEVAL_BONUS_PER_HIT, _RETRIEVAL_BONUS_CAP)

    raw = base + risk + retrieval
    return max(_WEIGHT_MIN, min(_WEIGHT_MAX, round(raw, 2)))


def weight_label(weight: float) -> str:
    """Human-readable label for a weight score."""
    if weight >= 4.0:
        return "critical"
    if weight >= 3.0:
        return "high"
    if weight >= 2.0:
        return "medium"
    if weight >= 1.0:
        return "low"
    return "minimal"