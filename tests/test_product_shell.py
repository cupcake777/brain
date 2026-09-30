from hermes.templates import (
    proposal_lifecycle_page,
    review_detail_page,
    review_queue_page,
)


def test_knowledge_proposal_pages_use_product_shell() -> None:
    proposal = {
        "proposal_id": "proposal-1",
        "state": "pending",
        "domain": "tech",
        "project_key": "brain",
        "category": "rule",
        "risk_level": "low",
        "summary": "Keep the product shell bounded.",
    }
    pages = (
        review_queue_page(
            proposals=[proposal],
            counts={"pending": 1},
            active_state="pending",
        ),
        review_detail_page(proposal=proposal),
        proposal_lifecycle_page({}, graph_data={"nodes": [], "edges": []}),
    )

    forbidden = (
        'data-i18n="nav_workbench"',
        ">Hub<",
        ">Control<",
        ">Settings<",
        'id="welcomeOverlay"',
        "Go to Workbench",
        "Go to Hub",
        "Go to Control",
        "Go to Settings",
    )
    for page in pages:
        assert 'href="/"' in page
        assert 'href="/knowledge"' in page
        assert 'href="/gallery"' in page
        assert all(marker not in page for marker in forbidden)
        assert 'href="/" class="sidebar-nav-item' in page
