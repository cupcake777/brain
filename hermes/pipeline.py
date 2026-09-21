"""Automatic Proposal → Knowledge materialization pipeline.

Only approved proposals become durable Knowledge nodes. Explicit links make the
pipeline idempotent while legacy source/id matching prevents duplicate nodes.
"""
from __future__ import annotations

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


def sync_approved_proposals(repo: HermesRepository, *, limit: int | None = None) -> dict[str, object]:
    """Materialize unlinked approved proposals into Knowledge, idempotently.

    Existing V2 nodes are linked first using the historical exact-id and
    ``proposal:<id-prefix>`` conventions. Unresolved proposals are sent through
    the normal integration engine, so deduplication and contradiction handling
    remain identical to newly ingested approved proposals.
    """
    proposals: list[dict[str, Any]] = []
    for state in _APPROVED_STATES:
        proposals.extend(repo.list_proposals_by_state(state))
    proposals.sort(key=lambda item: str(item.get("inserted_at") or ""))
    if limit is not None:
        proposals = proposals[: max(0, int(limit))]

    synced = already_linked = failed = 0
    errors: list[str] = []
    for proposal in proposals:
        proposal_id = str(proposal.get("proposal_id") or "")
        if not proposal_id:
            failed += 1
            errors.append("approved proposal missing proposal_id")
            continue
        if repo.get_proposal_knowledge_link(proposal_id):
            already_linked += 1
            continue

        legacy_id = repo.find_legacy_proposal_knowledge(proposal_id)
        if legacy_id:
            repo.link_proposal_knowledge(proposal_id, legacy_id, action="legacy")
            already_linked += 1
            continue

        try:
            result = integrate(
                content=_content(proposal),
                source=f"proposal:{proposal_id[:12]}",
                category=_category(proposal.get("category")),
                domain=_domain(proposal),
                repo=repo,
            )
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
        "failed": failed,
        "errors": errors[:5],
        "status": repo.proposal_sync_status(),
    }
