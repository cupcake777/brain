"""Chinese entry point for the shared-experience workspace."""
from __future__ import annotations

from .workspace import home


def home_page(*, node_counts: dict[str, int], chart_count: int, health_summary: dict,
              recent_nodes: list | None = None, proposal_counts: dict | None = None,
              knowledge_health: dict | None = None, lifecycle_overview: dict | None = None,
              pending_proposals: list | None = None, reviewed_count: int = 0,
              topic_counts: dict | None = None) -> str:
    return home(nodes=recent_nodes or [], counts=node_counts,
                pending=int((proposal_counts or {}).get('pending',0)),
                reviewed=reviewed_count, topic_counts=topic_counts or {})
