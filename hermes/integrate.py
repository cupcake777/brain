"""Hermes Brain V2: Knowledge Integration Engine.

Core pipeline for ingesting new knowledge into the knowledge tree:
  1. Semantic dedup check
  2. Contradiction detection
  3. Auto-refinement
  4. Confidence computation
  5. Thought chain recording

Replaces the simple propose() → approved → export pipeline with:
  integrate() → draft → refined → verified → canonized lifecycle
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Literal

from hermes.repository import HermesRepository, KnowledgeNode, ThoughtChain

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM availability check
# ---------------------------------------------------------------------------

_LLM_AVAILABLE = os.environ.get("BRAIN_LLM_ENABLED", "1").lower() not in ("0", "false", "no")

# ---------------------------------------------------------------------------
# Confidence computation (replaces static weight)
# ---------------------------------------------------------------------------

_CATEGORY_BASE = {"rule": 0.7, "workflow_hint": 0.6, "preference": 0.5, "fact": 0.4}
_SOURCE_BONUS = {"user_direct": 0.3, "verified": 0.2, "migration": 0.15, "reflection": 0.1, "conversation": 0.1}
_EVIDENCE_BONUS_PER = 0.05
_EVIDENCE_BONUS_CAP = 0.2
_RETRIEVAL_BONUS_PER = 0.02
_RETRIEVAL_BONUS_CAP = 0.1
_CORRECTION_PENALTY = 0.1
_TIME_BONUS_PER_30D = 0.02
_TIME_BONUS_CAP = 0.1
_AGE_PENALTY_PER_30D = 0.05
_AGE_THRESHOLD_DAYS = 90


def compute_confidence(
    *,
    category: str,
    source: str,
    evidence_count: int = 0,
    retrieval_count: int = 0,
    correction_count: int = 0,
    days_since_creation: int = 0,
    days_since_controversy: int = 0,
) -> float:
    """Compute dynamic confidence score for a knowledge node.

    Formula:
        base(category) + source_bonus + evidence_bonus + retrieval_bonus
        - correction_penalty + time_bonus - age_penalty

    Clamped to [0.0, 1.0].
    """
    base = _CATEGORY_BASE.get(category, 0.4)
    # Extract source type (format: "type:details" or just "type")
    source_type = source.split(":")[0] if ":" in source else source
    source_bonus = _SOURCE_BONUS.get(source_type, 0.1)
    evidence_bonus = min(evidence_count * _EVIDENCE_BONUS_PER, _EVIDENCE_BONUS_CAP)
    retrieval_bonus = min(retrieval_count * _RETRIEVAL_BONUS_PER, _RETRIEVAL_BONUS_CAP)
    correction_penalty = correction_count * _CORRECTION_PENALTY
    time_bonus = min(days_since_controversy // 30 * _TIME_BONUS_PER_30D, _TIME_BONUS_CAP) if days_since_controversy > 0 else 0.0
    age_penalty = max(0, (days_since_creation - _AGE_THRESHOLD_DAYS) // 30) * _AGE_PENALTY_PER_30D if days_since_creation > _AGE_THRESHOLD_DAYS else 0.0

    raw = base + source_bonus + evidence_bonus + retrieval_bonus - correction_penalty + time_bonus - age_penalty
    return max(0.0, min(1.0, round(raw, 3)))


def recompute_confidence(node: KnowledgeNode, repo: HermesRepository) -> float:
    """Recompute confidence for an existing node based on current stats."""
    now = datetime.now(timezone.utc)
    created = datetime.fromisoformat(node.created_at) if node.created_at else now
    days_since_creation = max(0, (now - created).days)

    evidence_list = json.loads(node.evidence) if isinstance(node.evidence, str) and node.evidence.strip().startswith("[") else (node.evidence if isinstance(node.evidence, list) else [])
    verified_list = json.loads(node.verified_by) if isinstance(node.verified_by, str) and node.verified_by.strip().startswith("[") else (node.verified_by if isinstance(node.verified_by, list) else [])

    return compute_confidence(
        category=node.category,
        source=node.source,
        evidence_count=len(evidence_list) + len(verified_list),
        retrieval_count=node.retrieval_count,
        correction_count=node.correction_count,
        days_since_creation=days_since_creation,
        days_since_controversy=days_since_creation,  # Approximation: use age as proxy
    )


# ---------------------------------------------------------------------------
# Dedup check result
# ---------------------------------------------------------------------------

class DedupResult:
    """Result of a dedup check."""

    def __init__(self, action: Literal["create", "merge", "review"], target: KnowledgeNode | None = None, candidates: list[KnowledgeNode] | None = None, similarity: float = 0.0):
        self.action = action  # create / merge / review
        self.target = target  # Best matching node (for merge)
        self.candidates = candidates or []  # Top-N candidates (for review)
        self.similarity = similarity  # Similarity score with best match


class ContradictionResult:
    """Result of a contradiction check."""

    def __init__(self, contradicts: list[KnowledgeNode], resolution: str, explanation: str):
        self.contradicts = contradicts
        self.resolution = resolution  # prefer_new / prefer_existing / both_valid / merge
        self.explanation = explanation


class IntegrateResult:
    """Result of an integrate() call."""

    def __init__(self, action: str, node_id: str, stage: str, confidence: float, merged_from: list[str] | None = None, superseded: str | None = None):
        self.action = action  # created / merged / created_with_contradiction
        self.node_id = node_id
        self.stage = stage
        self.confidence = confidence
        self.merged_from = merged_from or []
        self.superseded = superseded


# ---------------------------------------------------------------------------
# Semantic similarity engine (hybrid: text + fastembed embeddings)
# ---------------------------------------------------------------------------

_CJK_PATTERN = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")


def _tokenize_unicode(text: str) -> set[str]:
    """Unicode-aware tokenization: splits CJK characters individually,
    keeps Latin words/numbers together. Handles mixed CJK+Latin text
    that ``re.findall(r'\\w+', ...)`` silently mis-tokenizes.

    Examples::

        _tokenize_unicode("SSH端口50022是DO")
        → {'ssh', '端', '口', '50022', '是', 'do'}

        _tokenize_unicode("SSH port for DO is 50022")
        → {'ssh', 'port', 'for', 'do', 'is', '50022'}
    """
    # Pattern: Latin words/numbers | individual CJK characters
    return set(_CJK_PATTERN.findall(text.lower()))


def _text_similarity(text_a: str, text_b: str) -> float:
    """Compute text similarity between two strings.

    Multi-signal approach:
    1. Word Jaccard similarity (Unicode-aware tokenization for CJK)
    2. Bigram Jaccard (catches reorder like "SSH port DO" ≈ "DO SSH port")
    3. Prefix match (catches near-identical entries)
    4. Containment bonus (one contains the other)
    5. Shared numeric tokens (port numbers, IPs are key identifiers)

    Text component of hybrid dedup. Embedding similarity is applied downstream
    in dedup_check() via batch_embedding_similarity() (hybrid: 70% emb + 30% text).
    """
    if not text_a or not text_b:
        return 0.0

    # 1. Word-level Jaccard (Unicode-aware)
    words_a = _tokenize_unicode(text_a)
    words_b = _tokenize_unicode(text_b)
    if not words_a or not words_b:
        return 0.0
    word_jaccard = len(words_a & words_b) / len(words_a | words_b)

    # 2. Bigram Jaccard (character-level, catches reorder)
    def _bigrams(s: str) -> set[str]:
        s = s.lower().strip()
        return {s[i:i+2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}

    bigrams_a = _bigrams(text_a)
    bigrams_b = _bigrams(text_b)
    bigram_jaccard = len(bigrams_a & bigrams_b) / len(bigrams_a | bigrams_b) if (bigrams_a | bigrams_b) else 0.0

    # 3. Numeric token matching (ports, IPs, version numbers are key identifiers)
    nums_a = set(re.findall(r"\d+", text_a))
    nums_b = set(re.findall(r"\d+", text_b))
    if nums_a and nums_b:
        # Numbers are highly discriminative — different numbers → much less similar
        shared_nums = nums_a & nums_b
        all_nums = nums_a | nums_b
        if nums_a != nums_b:
            # Penalty: missing or extra numbers significantly reduce similarity
            num_match_ratio = len(shared_nums) / len(all_nums)
            # If any numbers are different, apply a heavy penalty (×0.5)
            # This prevents "port 50022" from matching "port 50023"
            num_match_ratio *= 0.5
        else:
            # All numbers match — strong positive signal
            num_match_ratio = 1.0
    else:
        num_match_ratio = 0.5  # neutral if no numbers

    # 4. Prefix containment
    prefix_a = text_a[:60].lower().strip()
    prefix_b = text_b[:60].lower().strip()
    prefix_match = 1.0 if prefix_a == prefix_b else 0.0

    # 5. Substring containment bonus
    shorter = min(text_a, text_b, key=len).lower()
    longer = max(text_a, text_b, key=len).lower()
    contains_bonus = 0.3 if shorter in longer and len(shorter) > 10 else 0.0

    # Weighted: bigram_jaccard catches reorder, word_jaccard catches topical overlap,
    # num_match penalizes wrong numbers, prefix catches near-duplicates
    score = (0.25 * word_jaccard
             + 0.25 * bigram_jaccard
             + 0.25 * num_match_ratio
             + 0.15 * prefix_match
             + 0.10 * contains_bonus)
    return min(1.0, round(score, 4))


def dedup_check(
    summary: str,
    content: str,
    existing_nodes: list[KnowledgeNode],
    *,
    merge_threshold: float = 0.85,
    review_threshold: float = 0.55,
) -> DedupResult:
    """Check if new knowledge duplicates existing knowledge.

    Thresholds:
    - similarity > merge_threshold: highly similar → merge
    - similarity > review_threshold: moderately similar → review (LLM decides)
    - similarity ≤ review_threshold: new knowledge → create

    Uses hybrid similarity (embedding + text) when embeddings are available,
    falls back to pure text similarity otherwise.
    """
    if not existing_nodes:
        return DedupResult(action="create")

    best_node = None
    best_sim = 0.0
    candidates_for_review: list[tuple[KnowledgeNode, float]] = []

    # Try embedding-based similarity for the top candidates
    # Strategy: text similarity pre-filter (fast) → embedding refinement (accurate)
    # This avoids embedding 100+ candidates on every integrate() call
    MAX_EMBEDDING_CANDIDATES = 20

    # Step 1: Fast text pre-filter to find top candidates
    text_candidates: list[tuple[KnowledgeNode, float]] = []
    for node in existing_nodes:
        if node.stage == "deprecated":
            continue
        sim_sum = _text_similarity(summary, node.summary)
        sim_con = _text_similarity(content, node.content)
        sim = max(sim_sum, sim_con)
        text_candidates.append((node, sim))

    text_candidates.sort(key=lambda x: x[1], reverse=True)

    # Step 2: Try embedding-based dedup
    # Strategy: use embeddings as the PRIMARY similarity signal when available.
    # Text pre-filter is used to narrow candidates, but we ALSO include nodes
    # that share key numeric tokens (ports, IPs) even if text sim is low,
    # because CJK vs Latin text similarity is unreliable.
    import os as _os
    use_embeddings = _os.environ.get("BRAIN_DISABLE_EMBEDDINGS", "").lower() not in ("1", "true", "yes")

    if use_embeddings and len(text_candidates) > 0:
        try:
            from hermes.embedding import batch_embedding_similarity

            # Build candidate set: text top-N + numeric-overlap extras
            text_top = text_candidates[:MAX_EMBEDDING_CANDIDATES]
            text_top_ids = {n.id for n, _ in text_top}

            # Find nodes sharing key numeric tokens (≥2 digits) that text sim missed
            query_nums = set(re.findall(r"\d{2,}", summary + " " + content))
            numeric_extras: list[tuple[KnowledgeNode, float]] = []
            if query_nums:
                for node, txt_sim in text_candidates[MAX_EMBEDDING_CANDIDATES:]:
                    node_nums = set(re.findall(r"\d{2,}", node.summary + " " + node.content))
                    if query_nums & node_nums:  # shared multi-digit numbers
                        numeric_extras.append((node, txt_sim))

            # Combine: text top-N + numeric extras
            all_emb_candidates = text_top + numeric_extras[:10]  # cap extras
            top_nodes_list = [n for n, _ in all_emb_candidates]
            candidate_summaries = [n.summary for n in top_nodes_list]

            # Embed query vs candidate summaries
            sim_by_summary = batch_embedding_similarity(summary, candidate_summaries)

            if sim_by_summary is not None:
                # Hybrid: 70% embedding + 30% text
                for i, (node, txt_sim) in enumerate(all_emb_candidates):
                    emb_sim = next((s for idx, s in sim_by_summary if idx == i), txt_sim)
                    hybrid_sim = 0.7 * emb_sim + 0.3 * txt_sim
                    candidates_for_review.append((node, hybrid_sim))
                    if hybrid_sim > best_sim:
                        best_sim = hybrid_sim
                        best_node = node
                candidates_for_review.sort(key=lambda x: x[1], reverse=True)
            else:
                # Embedding failed, use text similarity results
                candidates_for_review = text_candidates[:MAX_EMBEDDING_CANDIDATES]
                if text_candidates:
                    best_sim = text_candidates[0][1]
                    best_node = text_candidates[0][0]

        except Exception:
            # Embedding import/execution failed, use text-only results
            candidates_for_review = text_candidates[:MAX_EMBEDDING_CANDIDATES]
            if text_candidates:
                best_sim = text_candidates[0][1]
                best_node = text_candidates[0][0]
    else:
        # Embeddings disabled, use text-only results
        candidates_for_review = text_candidates[:MAX_EMBEDDING_CANDIDATES]
        if text_candidates:
            best_sim = text_candidates[0][1]
            best_node = text_candidates[0][0]

    if best_sim > merge_threshold and best_node:
        return DedupResult(action="merge", target=best_node, similarity=best_sim)

    if best_sim > review_threshold and best_node:
        top_candidates = [n for n, s in candidates_for_review[:3] if s > review_threshold]
        return DedupResult(action="review", target=best_node, candidates=top_candidates, similarity=best_sim)

    return DedupResult(action="create")


# ---------------------------------------------------------------------------
# Contradiction detection (text heuristic, will upgrade to LLM)
# ---------------------------------------------------------------------------

_NEGATION_WORDS = {"not", "no", "never", "don't", "dont", "isn't", "isnt", "wasn't", "wasnt",
                   "shouldn't", "shouldnt", "can't", "cant", "won't", "wont", "cannot", "incorrect",
                   "wrong", "错误", "禁止", "不可", "不能", "不再"}

def _has_negation(text: str) -> bool:
    """Quick check if text contains negation words."""
    words = set(text.lower().split())
    return bool(words & _NEGATION_WORDS)


def check_contradiction(
    new_content: str,
    existing_nodes: list[KnowledgeNode],
    *,
    similarity_threshold: float = 0.50,
) -> ContradictionResult | None:
    """Check if new knowledge contradicts existing knowledge.

    Heuristic approach: find nodes with moderate similarity where one has
    negation pattern the other doesn't. Full LLM-driven detection is P1.
    """
    contradictions: list[KnowledgeNode] = []

    for node in existing_nodes:
        if node.stage == "deprecated":
            continue
        sim = _text_similarity(new_content, node.content)
        if sim < similarity_threshold:
            continue

        new_neg = _has_negation(new_content)
        old_neg = _has_negation(node.content)

        # One negates, the other affirms → likely contradiction
        if new_neg != old_neg and sim > 0.3:
            contradictions.append(node)

    if not contradictions:
        return None

    # Sort by similarity (most similar first)
    contradictions.sort(key=lambda n: _text_similarity(new_content, n.content), reverse=True)

    # Default resolution: prefer newer knowledge (can be overridden by LLM)
    return ContradictionResult(
        contradicts=contradictions[:3],
        resolution="prefer_new",
        explanation=f"Found {len(contradictions)} contradicting node(s). "
                    f"New content has negation pattern difference with most similar node.",
    )


# ---------------------------------------------------------------------------
# Core integrate() function
# ---------------------------------------------------------------------------

def integrate(
    content: str,
    source: str,
    *,
    category: str = "fact",
    domain: str = "general",
    parent_id: str | None = None,
    evidence: list[str] | None = None,
    repo: HermesRepository,
) -> IntegrateResult:
    """Integrate new knowledge into the knowledge tree.

    Pipeline:
    1. Dedup check — is this knowledge already known?
    2. Contradiction check — does it conflict with existing knowledge?
    3. Create/merge/refine node
    4. Record thought chain
    5. Return result
    """
    now = datetime.now(timezone.utc).isoformat()
    node_id = str(uuid.uuid4())
    summary = content[:120].rstrip()  # Auto-generate summary from content

    # Get all active (non-deprecated) nodes for comparison
    existing_nodes = repo.list_knowledge_nodes(limit=500)  # Active nodes
    existing_active = [n for n in existing_nodes if n.stage != "deprecated"]

    # Step 1: Dedup check
    dedup = dedup_check(summary, content, existing_active)

    thought_steps: list[dict] = []

    if dedup.action == "merge" and dedup.target:
        # Merge into existing node — create a refine child
        target = dedup.target
        merged_content = _merge_content(target.content, content)
        merged_summary = _merge_content(target.summary, summary)

        # Update existing node with merged content
        repo.update_knowledge_node(
            target.id,
            content=merged_content,
            summary=merged_summary,
            stage="refined",
            refined_at=now,
            merged_from=json.dumps(json.loads(target.merged_from) + [node_id]),
        )

        # Record thought chain
        tc = ThoughtChain(
            id=str(uuid.uuid4()),
            node_id=target.id,
            action="merge",
            reasoning=f"Merged with new knowledge (similarity={dedup.similarity:.3f}). "
                       f"Original: '{target.summary[:60]}…' → Merged: '{merged_summary[:60]}…'",
            evidence_used=json.dumps([target.id]),
            decision="merge",
            confidence_in_decision=round(dedup.similarity, 3),
            created_at=now,
        )
        repo.insert_thought_chain(tc)

        # Compute updated confidence
        updated_node = repo.get_knowledge_node(target.id)
        if updated_node:
            new_conf = recompute_confidence(updated_node, repo)
            repo.update_knowledge_node(target.id, confidence=new_conf)

        return IntegrateResult(
            action="merged",
            node_id=target.id,
            stage="refined",
            confidence=updated_node.confidence if updated_node else target.confidence,
            merged_from=[node_id],
        )

    # Step 2: Contradiction check (for new or review-action nodes)
    # First: fast heuristic check
    contradiction = check_contradiction(content, existing_active)

    # Second: LLM-powered deep check on top similar nodes (if heuristic found potential)
    llm_contradictions = None
    if _LLM_AVAILABLE:
        try:
            from hermes.llm_contradiction import batch_llm_contradiction_check
            llm_contradictions = batch_llm_contradiction_check(
                content, existing_active, max_candidates=3
            )
        except Exception as e:
            logger.warning("LLM contradiction check failed: %s", e)

    # Use LLM result if available, otherwise heuristic
    contradict_ids: list[str] = []
    superseded_id: str | None = None
    contradiction_explanation = ""

    if llm_contradictions:
        # LLM found contradictions
        for lc in llm_contradictions:
            contradict_ids.append(lc["node_id"])
            contradiction_explanation += f"vs '{lc['node_summary']}…': {lc['explanation']} ({lc['severity']}). "

        # Auto-deprecate if LLM says prefer_new
        for lc in llm_contradictions:
            if lc["resolution"] == "prefer_new" and lc["severity"] == "critical":
                old_node = repo.get_knowledge_node(lc["node_id"])
                if old_node and old_node.stage != "deprecated":
                    repo.update_knowledge_node(
                        lc["node_id"], stage="deprecated", deprecated_at=now,
                    )
                    superseded_id = lc["node_id"]
                    break  # Only deprecate one node per integrate

        if contradict_ids:
            tc = ThoughtChain(
                id=str(uuid.uuid4()),
                node_id=node_id,
                action="contradiction_detect",
                reasoning=f"LLM detected contradiction: {contradiction_explanation}",
                evidence_used=json.dumps(contradict_ids),
                decision="flag_contradiction",
                confidence_in_decision=0.85,
                created_at=now,
            )
            repo.insert_thought_chain(tc)

    elif contradiction:
        # Fallback to heuristic result
        contradict_ids = [c.id for c in contradiction.contradicts[:3]]
        contradiction_explanation = contradiction.explanation

        # If resolution is "prefer_new", mark contradicted nodes as deprecated
        if contradiction.resolution == "prefer_new" and contradiction.contradicts:
            for old_node in contradiction.contradicts[:1]:  # Only deprecate the most similar
                repo.update_knowledge_node(
                    old_node.id,
                    stage="deprecated",
                    deprecated_at=now,
                )
                superseded_id = old_node.id

        if contradict_ids:
            tc = ThoughtChain(
                id=str(uuid.uuid4()),
                node_id=node_id,
                action="contradiction_detect",
                reasoning=f"Heuristic: {contradiction.explanation}",
                evidence_used=json.dumps(contradict_ids),
                decision="flag_contradiction",
                confidence_in_decision=0.6,
                created_at=now,
            )
            repo.insert_thought_chain(tc)

    # Determine confidence
    evidence_list = evidence or []
    conf = compute_confidence(
        category=category,
        source=source,
        evidence_count=len(evidence_list),
    )

    # Determine initial stage
    # - High confidence sources (user_direct, verified, migration, proposal) → refined
    # - Contradictions → draft (needs review)
    # - Everything else → draft
    # Proposals from agents have already been reviewed by the submitting agent,
    # so they start at refined (immediately visible in exports).
    source_type = source.split(":")[0] if ":" in source else source
    if contradict_ids:
        initial_stage = "draft"  # Needs review if contradicts existing
    else:
        initial_stage = "refined" if source_type in ("user_direct", "verified", "migration", "proposal") else "draft"

    # Step 3: Create new node
    node = KnowledgeNode(
        id=node_id,
        parent_id=parent_id,
        content=content,
        summary=summary,
        category=category,
        domain=domain,
        stage=initial_stage,
        operation="draft",
        confidence=conf,
        source=source,
        evidence=json.dumps(evidence_list),
        supersedes=superseded_id,
        merged_from="[]",
        contradicts=json.dumps(contradict_ids),
        verified_by="[]",
        created_at=now,
        refined_at=now if initial_stage == "refined" else None,
        verified_at=None,
        deprecated_at=None,
        retrieval_count=0,
        last_used_at=None,
        correction_count=0,
    )
    repo.insert_knowledge_node(node)

    # If dedup result was "review", record the review thought
    if dedup.action == "review" and dedup.target:
        tc = ThoughtChain(
            id=str(uuid.uuid4()),
            node_id=node_id,
            action="dedup_check",
            reasoning=f"Moderate similarity ({dedup.similarity:.3f}) with node '{dedup.target.summary[:40]}…'. "
                       f"Created as new node pending review.",
            evidence_used=json.dumps([dedup.target.id]),
            decision="create",
            confidence_in_decision=round(1.0 - dedup.similarity, 3),
            created_at=now,
        )
        repo.insert_thought_chain(tc)

    action = "created_with_contradiction" if contradict_ids else "created"
    return IntegrateResult(
        action=action,
        node_id=node_id,
        stage=initial_stage,
        confidence=conf,
        superseded=superseded_id,
    )


# ---------------------------------------------------------------------------
# Retrospect — periodic knowledge maintenance
# ---------------------------------------------------------------------------

def retrospect(repo: HermesRepository, *, dry_run: bool = False) -> dict:
    """Periodic knowledge maintenance — replaces manual dedup/reweight.

    Actions:
    1. Stale draft detection (>90 days unused)
    2. Auto-canonize (>7 days refined, no contradictions)
    3. Confidence recomputation for all nodes
    4. Find merge clusters (semantic grouping)

    Returns summary of actions taken.
    """
    now = datetime.now(timezone.utc)
    actions = {
        "stale_flagged": 0,
        "canonized": 0,
        "refined": 0,
        "confidence_updated": 0,
        "merge_candidates": 0,
    }

    def _parse_dt(dt_str: str | None, fallback: datetime) -> datetime:
        """Parse datetime string, ensuring timezone-aware UTC result."""
        if not dt_str:
            return fallback
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    all_nodes = repo.list_knowledge_nodes(limit=10000)

    # 1. Stale detection
    for node in all_nodes:
        if node.stage not in ("draft", "refined"):
            continue
        created = _parse_dt(node.created_at, now)
        age_days = (now - created).days
        last_used = _parse_dt(node.last_used_at, created)
        unused_days = (now - last_used).days

        if age_days > 90 and node.retrieval_count == 0:
            actions["stale_flagged"] += 1
            if not dry_run:
                repo.update_knowledge_node(node.id, stage="deprecated", deprecated_at=now.isoformat())

    # 2. Auto-canonize
    for node in all_nodes:
        if node.stage not in ("refined", "draft"):
            continue
        created = _parse_dt(node.created_at, now)

        # draft → refined: after 1 day with no contradictions
        if node.stage == "draft":
            age_days = (now - created).days
            if age_days < 1:
                continue
            contradict_ids = json.loads(node.contradicts) if isinstance(node.contradicts, str) else node.contradicts
            has_active_contradiction = any(
                (repo.get_knowledge_node(cid) and repo.get_knowledge_node(cid).stage != "deprecated")
                for cid in contradict_ids
            )
            if not has_active_contradiction:
                actions.setdefault("refined", 0)
                actions["refined"] = actions.get("refined", 0) + 1
                if not dry_run:
                    repo.update_knowledge_node(node.id, stage="refined", refined_at=now.isoformat())
            continue

        # refined → canonized: after 2 days, no contradictions
        refined_at = _parse_dt(node.refined_at, created)
        days_refined = (now - refined_at).days

        if days_refined < 2:
            continue

        # Check no active contradictions
        contradict_ids = json.loads(node.contradicts) if isinstance(node.contradicts, str) else node.contradicts
        has_active_contradiction = False
        for cid in contradict_ids:
            c_node = repo.get_knowledge_node(cid)
            if c_node and c_node.stage != "deprecated":
                has_active_contradiction = True
                break

        if not has_active_contradiction:
            actions["canonized"] += 1
            if not dry_run:
                repo.update_knowledge_node(node.id, stage="canonized", verified_at=now.isoformat())

    # 3. Confidence recomputation
    for node in all_nodes:
        if node.stage == "deprecated":
            continue
        new_conf = recompute_confidence(node, repo)
        if abs(new_conf - node.confidence) > 0.05:
            actions["confidence_updated"] += 1
            if not dry_run:
                repo.update_knowledge_node(node.id, confidence=new_conf)

    # 4. Find merge candidates using hybrid similarity (embedding + text)
    # Strategy: text pre-filter → embedding refinement, same as dedup_check()
    active_nodes = [n for n in all_nodes if n.stage != "deprecated"]
    merge_candidates = 0
    merge_pairs_list: list[tuple[str, str, float]] = []  # (id_a, id_b, sim)
    review_pairs_list: list[tuple[str, str, float]] = []
    seen_pairs: set[frozenset[str]] = set()

    import os as _os
    use_embeddings = _os.environ.get("BRAIN_DISABLE_EMBEDDINGS", "").lower() not in ("1", "true", "yes")

    if use_embeddings:
        try:
            from hermes.embedding import embed_texts
            summaries = [n.summary for n in active_nodes]
            embs = embed_texts(summaries)
            if embs is not None:
                import numpy as _np
                emb_matrix = _np.array(embs)
                norms = _np.linalg.norm(emb_matrix, axis=1, keepdims=True)
                norms[norms == 0] = 1
                emb_matrix = emb_matrix / norms

                for i in range(len(active_nodes)):
                    for j in range(i + 1, len(active_nodes)):
                        pair_key = frozenset({active_nodes[i].id, active_nodes[j].id})
                        if pair_key in seen_pairs:
                            continue
                        text_sim = _text_similarity(active_nodes[i].summary, active_nodes[j].summary)
                        emb_sim = float(emb_matrix[i] @ emb_matrix[j])
                        hybrid_sim = 0.7 * emb_sim + 0.3 * text_sim
                        if hybrid_sim > 0.85:
                            merge_candidates += 1
                            merge_pairs_list.append((active_nodes[i].id, active_nodes[j].id, hybrid_sim))
                            seen_pairs.add(pair_key)
                        elif hybrid_sim > 0.55:
                            review_pairs_list.append((active_nodes[i].id, active_nodes[j].id, hybrid_sim))
                            seen_pairs.add(pair_key)
            else:
                use_embeddings = False  # Fall through to text-only below
        except Exception:
            use_embeddings = False

    if not use_embeddings:
        # Text-only fallback
        for i, node_a in enumerate(active_nodes):
            for node_b in active_nodes[i + 1:]:
                pair_key = frozenset({node_a.id, node_b.id})
                if pair_key in seen_pairs:
                    continue
                sim = _text_similarity(node_a.summary, node_b.summary)
                if sim > 0.70:
                    merge_candidates += 1
                    merge_pairs_list.append((node_a.id, node_b.id, sim))
                    seen_pairs.add(pair_key)

    actions["merge_candidates"] = merge_candidates
    actions["review_candidates"] = len(review_pairs_list)

    # Log top merge and review pairs
    if merge_pairs_list:
        merge_pairs_list.sort(key=lambda x: x[2], reverse=True)
        for id_a, id_b, sim in merge_pairs_list[:5]:
            node_a = next((n for n in active_nodes if n.id == id_a), None)
            node_b = next((n for n in active_nodes if n.id == id_b), None)
            if node_a and node_b:
                logger.info("retrospect merge candidate: sim=%.3f [%s] %s ↔ [%s] %s",
                            sim, node_a.stage, node_a.summary[:50], node_b.stage, node_b.summary[:50])
    if review_pairs_list:
        review_pairs_list.sort(key=lambda x: x[2], reverse=True)
        for id_a, id_b, sim in review_pairs_list[:5]:
            node_a = next((n for n in active_nodes if n.id == id_a), None)
            node_b = next((n for n in active_nodes if n.id == id_b), None)
            if node_a and node_b:
                logger.info("retrospect review candidate: sim=%.3f [%s] %s ↔ [%s] %s",
                            sim, node_a.stage, node_a.summary[:50], node_b.stage, node_b.summary[:50])

    return actions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _merge_content(existing: str, new: str) -> str:
    """Merge two content strings, preferring more detailed version."""
    if not existing:
        return new
    if not new:
        return existing
    # If new content is a superset of existing, prefer new
    if existing.lower().strip() in new.lower():
        return new
    # If existing is a superset of new, prefer existing
    if new.lower().strip() in existing.lower():
        return existing
    # Otherwise concatenate with separator
    return f"{existing}\n— Updated: {new}"