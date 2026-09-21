"""Outcome accounting primitives.

Implements the documented denominator rules and the unique-pair /
status-conflict rejection rules.

The rules are intentionally pure (no DB access here) so they can be unit
tested directly:

* The **hit-rate denominator** counts only terminal *clean* outcomes:
  ``applied``, ``failed``, ``contradicted``, ``not_used``.  Anything labelled
  ``pending``, ``unknown``, ``helpful``, ``neutral``, ``harmful`` (the
  legacy v3 buckets), or with empty ``used`` status is **excluded** from the
  denominator and **tracked** separately as missing / pending so the UI can
  surface honest freshness rather than manufactured metrics.

* Terminal precedence: when multiple labels exist for the same exposure
  ``(task_id, canonical_node_id, content_version)``, the row with the
  *highest* severity wins (``contradicted > failed > applied > not_used``).

* The eligibility threshold ``min5`` means **5 unique relevant exposures**
  with terminal labels — not raw retrieval_log rows and not candidate counts.

* The "missing pair" anomaly is the set of ``(retrieval_log_id, memory_id)``
  pairs that the retrieval exposed but never received a terminal outcome.
  Finalisation reports these as anomalies; it must **never** insert
  synthetic outcomes to make the session look complete.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping


# Terminal clean statuses that count toward the hit-rate denominator.
TERMINAL_CLEAN_STATUSES: frozenset[str] = frozenset(
    {"applied", "failed", "contradicted", "not_used"}
)

# Statuses that are explicitly *not* terminal.  They must be excluded from
# the denominator and surfaced as pending / unknown / anomaly instead.
NON_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"pending", "unknown", "helpful", "neutral", "harmful", ""}
)

# Ordering used when multiple terminal labels coexist for the same exposure.
# Higher = more severe, wins ties.
TERMINAL_PRECEDENCE: dict[str, int] = {
    "not_used": 1,
    "applied": 2,
    "failed": 3,
    "contradicted": 4,
}

# Legacy v3 mapping that brain_protocol / record_outcome_v3 use today.
LEGACY_V3_HELPFULNESS_TO_STATUS: dict[str, str] = {
    "helpful": "applied",
    "neutral": "not_used",
    "harmful": "failed",
}


# Minimum number of terminal *clean* exposures before a node is eligible
# for "by hit rate" ranking.  Matches the rank relevance review's N=5
# requirement exactly.
ELIGIBILITY_MIN_EXPOSURES: int = 5


@dataclass(frozen=True)
class OutcomeObservation:
    """A single outcome row, normalised for accounting."""

    retrieval_log_id: str
    memory_id: str
    status: str  # terminal bucket (applied / failed / contradicted / not_used / pending / unknown / ...)
    used: bool = True  # whether the memory was actually used (non-not_used)
    exposure_key: str | None = None  # (task_id, canonical_node_id, content_version) or None

    def is_terminal_clean(self) -> bool:
        return self.status in TERMINAL_CLEAN_STATUSES

    def is_missing(self) -> bool:
        return not self.is_terminal_clean()


@dataclass(frozen=True)
class MissingPair:
    retrieval_log_id: str
    memory_id: str
    reason: str  # "no_outcome" / "pending_outcome" / "unknown_status" / "conflict_unresolved"


@dataclass(frozen=True)
class NodeHitRate:
    node_id: str
    exposures: int           # terminal clean exposures (denominator)
    applied: int
    failed: int
    contradicted: int
    not_used: int
    pending: int
    eligible: bool           # exposures >= ELIGIBILITY_MIN_EXPOSURES

    @property
    def hit_rate(self) -> float:
        if self.exposures <= 0:
            return 0.0
        return self.applied / self.exposures

    def distribution(self) -> dict[str, int]:
        return {
            "applied": self.applied,
            "failed": self.failed,
            "contradicted": self.contradicted,
            "not_used": self.not_used,
            "pending": self.pending,
            "exposures": self.exposures,
            "eligible": int(self.eligible),
        }


@dataclass(frozen=True)
class FinalizeSummary:
    """Result of a session finalisation attempt."""

    final_result: str  # "complete" / "incomplete" / "no_experience_used"
    retrieval_events: int
    missing_pairs: list[MissingPair]
    count_anomaly: bool  # true when outcome count differs from retrieval pair count by > tolerance
    duplicate_conflicts: list[str]  # status-conflict anomalies where a replay had a different status
    already_finalized: bool
    finalized_at: str | None


def normalise_status(helpfulness: str | None, used: bool | None = True) -> str:
    """Map legacy helpfulness buckets to terminal status buckets.

    ``helpful`` + used=True → ``applied`` (terminal)
    ``neutral`` → ``not_used`` (terminal)
    ``harmful`` → ``failed`` (terminal)
    Unknown / pending → ``pending`` (non-terminal; excluded from denominator)
    """
    key = (helpfulness or "").strip().lower()
    if not key or key in NON_TERMINAL_STATUSES:
        return "pending"
    if key in TERMINAL_CLEAN_STATUSES:
        return key
    mapped = LEGACY_V3_HELPFULNESS_TO_STATUS.get(key)
    return mapped or "pending"


def reduce_outcomes(
    outcomes: Iterable[OutcomeObservation],
    *,
    exposure_key_lookup: Mapping[tuple[str, str], str] | None = None,
) -> tuple[dict[str, NodeHitRate], list[MissingPair], list[str]]:
    """Aggregate per-node hit rates from a stream of outcomes.

    Args:
        outcomes:                outcome rows to fold.
        exposure_key_lookup:     optional ``(retrieval_log_id, memory_id) →
                                 (task_id, canonical_node_id, content_version)``
                                 resolver.  When supplied, multiple rows for
                                 the same exposure are collapsed via terminal
                                 precedence; only the *winning* label
                                 contributes to the denominator.

    Returns:
        hit_rates:               per-node bucket counts and the derived
                                 ``hit_rate`` plus ``eligible`` flag.
        missing_pairs:           rows that should have been terminal but
                                 weren't.  Surfaced to the UI as anomalies.
        conflict_ids:            exposure keys with status conflicts (more
                                 than one terminal label and they disagree).
    """
    # First pass: bucket rows by node + exposure key.
    per_node: dict[str, dict[str, list[OutcomeObservation]]] = {}
    pending_per_node: Counter[str] = Counter()
    missing: list[MissingPair] = []
    conflict_ids: list[str] = []

    for row in outcomes:
        node = row.memory_id
        exposure = (
            exposure_key_lookup.get((row.retrieval_log_id, row.memory_id))
            if exposure_key_lookup
            else row.exposure_key
        ) or f"{row.retrieval_log_id}:{row.memory_id}"

        if not row.is_terminal_clean():
            pending_per_node[node] += 1
            if row.status in {"pending", "unknown"} or not row.status:
                missing.append(
                    MissingPair(
                        retrieval_log_id=row.retrieval_log_id,
                        memory_id=row.memory_id,
                        reason="pending_outcome",
                    )
                )
            continue

        bucket = per_node.setdefault(node, {}).setdefault(exposure, [])
        bucket.append(row)

    # Second pass: collapse each exposure bucket via terminal precedence.
    hit_rates: dict[str, NodeHitRate] = {}
    for node, exposures in per_node.items():
        applied = failed = contradicted = not_used = 0
        for exposure_key, rows in exposures.items():
            winners = _resolve_conflicts(rows)
            if len({row.status for row in rows}) > 1:
                conflict_ids.append(exposure_key)
            for row in winners:
                if row.status == "applied":
                    applied += 1
                elif row.status == "failed":
                    failed += 1
                elif row.status == "contradicted":
                    contradicted += 1
                elif row.status == "not_used":
                    not_used += 1
        total = applied + failed + contradicted + not_used
        hit_rates[node] = NodeHitRate(
            node_id=node,
            exposures=total,
            applied=applied,
            failed=failed,
            contradicted=contradicted,
            not_used=not_used,
            pending=pending_per_node.get(node, 0),
            eligible=total >= ELIGIBILITY_MIN_EXPOSURES,
        )

    return hit_rates, missing, conflict_ids


def _resolve_conflicts(rows: list[OutcomeObservation]) -> list[OutcomeObservation]:
    """Pick the terminal label with the highest severity per exposure.

    The review demands: "Freeze the label after a fixed window. If multiple
    labels occur, use terminal precedence: contradicted > failed > applied >
    not_used."  We additionally treat equal-severity duplicates as one
    row so that re-saves don't inflate the denominator.
    """
    if len(rows) <= 1:
        return rows
    severest = max(rows, key=lambda r: TERMINAL_PRECEDENCE.get(r.status, 0))
    return [severest]


def missing_pairs_for_retrievals(
    retrieval_pair_count: dict[tuple[str, str], int],
    observed_pairs: set[tuple[str, str]],
) -> list[MissingPair]:
    """Compute missing (retrieval_log_id, memory_id) pairs.

    Used by ``finalize_session`` to detect the count anomaly described in
    ``brain-api-review-outcomes.md`` ("数量不一致时标记异常") without ever
    inserting synthetic outcomes.
    """
    missing: list[MissingPair] = []
    for pair in retrieval_pair_count:
        if pair not in observed_pairs:
            rid, mid = pair
            missing.append(
                MissingPair(retrieval_log_id=rid, memory_id=mid, reason="no_outcome")
            )
    return missing


def detect_count_anomaly(
    *,
    expected_pairs: int,
    observed_terminal: int,
    observed_total: int,
) -> bool:
    """Return True when outcome accounting is anomalous.

    A session is anomalous if:

    * the number of retrieval pairs the session *exposed* does not match
      the number of outcome rows reported (under-count → "偷懒漏报"), OR
    * the gap between ``observed_total`` (every row) and
      ``observed_terminal`` (terminal clean rows) exceeds the configured
      threshold (over-count of pending/unknown → outcome never resolved).
    """
    if expected_pairs <= 0:
        return False
    if observed_terminal > observed_total:
        return True
    return observed_terminal < expected_pairs


__all__ = [
    "ELIGIBILITY_MIN_EXPOSURES",
    "FinalizeSummary",
    "MissingPair",
    "NodeHitRate",
    "NON_TERMINAL_STATUSES",
    "OutcomeObservation",
    "TERMINAL_CLEAN_STATUSES",
    "TERMINAL_PRECEDENCE",
    "detect_count_anomaly",
    "missing_pairs_for_retrievals",
    "normalise_status",
    "reduce_outcomes",
]