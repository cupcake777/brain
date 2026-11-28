"""Automatic Proposal → Knowledge materialization pipeline.

Only approved proposals become durable Knowledge nodes. Explicit links make the
pipeline idempotent while legacy source/id matching prevents duplicate nodes.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from hermes.integrate import integrate
from hermes.repository import HermesRepository

logger = logging.getLogger(__name__)
_APPROVED_STATES = ("approved_db_only", "approved_for_export")


def _category(value: object) -> str:
    category = str(value or "fact").strip().lower()
    return category if category in {"rule", "workflow_hint", "preference", "fact"} else "fact"


def _domain(proposal: dict[str, Any]) -> str:
    from hermes.lane import assign_lane, lane_text
    return assign_lane(
        hinted=proposal.get("domain"),
        project_key=proposal.get("project_key"),
        text=lane_text(
            proposal.get("summary"),
            proposal.get("observation"),
            proposal.get("suggested_memory"),
        ),
    )


def _content(proposal: dict[str, Any]) -> str:
    durable = str(proposal.get("suggested_memory") or "").strip()
    observation = str(proposal.get("observation") or "").strip()
    if durable and observation:
        return f"{durable}\n\nObservation: {observation}"
    return durable or observation or str(proposal.get("summary") or "").strip()


def _evidence(value: object) -> list[Any]:
    """Keep structured evidence intact and preserve legacy text verbatim."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return [value]
        return decoded if isinstance(decoded, list) else [value]
    return [value]


def _preserve_evidence(repo: HermesRepository, node_id: str, evidence: list[Any]) -> None:
    """Preserve evidence on first materialization/link or merge, without verification."""
    if not evidence:
        return
    node = repo.get_knowledge_node(node_id)
    if node is None:
        raise ValueError(f"knowledge node missing: {node_id}")
    combined = _evidence(node.evidence)
    original_count = len(combined)
    for item in evidence:
        if item not in combined:
            combined.append(item)
    if len(combined) != original_count:
        repo.update_knowledge_node(node_id, evidence=json.dumps(combined, ensure_ascii=False))


def sync_approved_proposals(repo: HermesRepository, *, limit: int | None = None) -> dict[str, object]:
    """Materialize unlinked approved proposals into Knowledge, idempotently.

    Existing V2 nodes are linked first using the historical exact-id and
    ``proposal:<id-prefix>`` conventions. Unresolved proposals are sent through
    the normal integration engine, so deduplication and contradiction handling
    remain identical to newly ingested approved proposals. Explicitly linked
    nodes are left unchanged: their evidence may already have curated reviews
    and relations tied to its digest. Historical backfills belong in a separate
    maintenance workflow.
    """
    proposals: list[dict[str, Any]] = []
    for state in _APPROVED_STATES:
        proposals.extend(repo.list_proposals_by_state(state))
    proposals.sort(key=lambda item: str(item.get("inserted_at") or ""))
    if limit is not None:
        proposals = proposals[: max(0, int(limit))]

    synced = already_linked = retired = failed = 0
    errors: list[str] = []
    for proposal in proposals:
        proposal_id = str(proposal.get("proposal_id") or "")
        if not proposal_id:
            failed += 1
            errors.append("approved proposal missing proposal_id")
            continue
        try:
            link = repo.get_proposal_knowledge_link(proposal_id)
            if link:
                already_linked += 1
                continue
            if repo.is_proposal_knowledge_retired(proposal_id):
                retired += 1
                continue

            evidence = _evidence(proposal.get("evidence"))
            legacy_id = repo.find_legacy_proposal_knowledge(proposal_id)
            if legacy_id:
                from hermes.environment_scope import get_scope, assign
                with repo._connect() as connection:
                    scope=get_scope(connection,'proposal',proposal_id)
                    node_scope=get_scope(connection,'knowledge',legacy_id)
                    if scope['server_id'] and node_scope['attribution']=='global':
                        assign(connection,'knowledge',legacy_id,scope,scope['attribution'])
                _preserve_evidence(repo, legacy_id, evidence)
                repo.link_proposal_knowledge(proposal_id, legacy_id, action="legacy")
                already_linked += 1
                continue

            from hermes.environment_scope import get_scope
            with repo._connect() as connection:
                environment=get_scope(connection,'proposal',proposal_id)
            result = integrate(
                content=_content(proposal),
                source=f"proposal:{proposal_id[:12]}",
                category=_category(proposal.get("category")),
                domain=_domain(proposal),
                evidence=evidence,
                repo=repo,
                environment=environment,
            )
            # integrate's merge path does not copy incoming evidence.
            _preserve_evidence(repo, result.node_id, evidence)
            repo.link_proposal_knowledge(proposal_id, result.node_id, action=result.action)
            synced += 1
        except Exception as exc:  # noqa: BLE001 - one bad proposal must not break the cycle
            failed += 1
            message = f"{proposal_id}: {exc}"
            errors.append(message[:500])
            logger.warning("proposal knowledge sync failed: %s", message)

    return {
        "eligible": len(proposals),
        "synced": synced,
        "already_linked": already_linked,
        "retired": retired,
        "failed": failed,
        "errors": errors[:5],
        "status": repo.proposal_sync_status(),
    }
