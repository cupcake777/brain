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


def test_review_detail_exposes_structured_proposal_editor() -> None:
    html = review_detail_page(
        proposal={
            "proposal_id": "proposal-editable",
            "state": "pending",
            "project_key": "global",
            "category": "workflow_hint",
            "risk_level": "low",
            "domain": "infrastructure",
            "source_agent": "xiaohe",
            "source_host": "local",
            "created_at": "2026-10-09T00:00:00+00:00",
            "summary": "Structured summary",
            "observation": "Observed fact",
            "why_it_matters": "Operational impact",
            "suggested_memory": "Durable rule",
            "scope": "global",
            "evidence": '[{"source_type":"url","source_uri":"https://example.com","quoted_excerpt":"verified"}]',
        }
    )

    assert 'id="proposal-editor"' in html
    assert 'name="observation"' in html
    assert 'name="why_it_matters"' in html
    assert 'name="suggested_memory"' in html
    assert 'name="evidence-source-type"' in html
    assert 'name="evidence-source-uri"' in html
    assert 'name="evidence-quoted-excerpt"' in html
    assert "/api/review/proposal-editable/edit" in html
    assert "saveProposal" in html
