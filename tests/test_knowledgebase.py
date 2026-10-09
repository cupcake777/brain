from __future__ import annotations

from pathlib import Path
from html import unescape
from urllib.parse import parse_qs, quote, urlsplit

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.knowledgebase import knowledge_tree_page
from hermes.repository import HermesRepository
from fastapi.testclient import TestClient


COUNTS = {
    "draft": 1,
    "refined": 0,
    "verified": 0,
    "canonized": 0,
    "deprecated": 0,
}


def _node(**overrides: object) -> dict[str, object]:
    node: dict[str, object] = {
        "id": "node-1",
        "summary": "Trace a claim to its source",
        "content": "Evidence stays attached to the knowledge node.",
        "stage": "draft",
        "category": "fact",
        "domain": "science",
        "confidence": 0.72,
        "created_at": "2026-09-30T08:00:00Z",
        "retrieval_count": 2,
    }
    node.update(overrides)
    return node


def test_knowledge_graph_list_and_filters_are_one_isolated_module() -> None:
    html = knowledge_tree_page(
        nodes=[_node()],
        counts=COUNTS,
        active_stage="draft",
        active_category="fact",
        active_domain="science",
        domains=["science"],
    )

    assert 'class="engram-knowledge"' in html
    assert 'aria-label="Knowledge views"' in html
    assert 'href="/knowledge?view=list' in html
    assert 'href="/knowledge?view=graph' in html
    assert 'id="knowledge-filter-form"' in html
    assert 'name="stage"' in html
    assert 'name="category"' in html
    assert 'name="domain"' in html
    assert 'name="q"' in html

    module = html.split('<main class="engram-knowledge"', 1)[1].split("</main>", 1)[0]

    # Adjacent stages remain separate atomic migrations; compatibility shell is out of scope.
    for forbidden in (
        'href="/proposals"',
        'href="/gallery"',
        'href="/hub"',
        "/api/review/",
        "/api/knowledge/integrate",
        "/api/knowledge/export",
        "/api/knowledge/retrospect",
        "/api/knowledge/trash/empty",
    ):
        assert forbidden not in module


def test_knowledge_renderer_escapes_dynamic_fields_and_quotes_paths() -> None:
    payload = '<img src=x onerror="alert(1)">'
    node_id = '../节点/α" onclick="alert(2)'
    rendered = knowledge_tree_page(
        nodes=[_node(id=node_id, summary=payload, content=payload, domain=payload, category=payload)],
        counts=COUNTS,
        active_category=payload,
        active_domain=payload,
        domains=[payload],
        query=payload,
        view="graph",
    )

    assert payload not in rendered
    assert f'href="/knowledge/{quote(node_id, safe="")}"' in rendered
    module = rendered.split('<main class="engram-knowledge"', 1)[1].split("</main>", 1)[0]
    assert _unsafe_event_attributes(module) == []


def test_knowledge_filter_links_preserve_values_with_query_encoding() -> None:
    rendered = knowledge_tree_page(
        nodes=[_node()],
        counts=COUNTS,
        active_stage="draft",
        active_category="workflow hint",
        active_domain="science/APA",
        domains=["science/APA"],
        query="brain development",
        view="graph",
    )
    marker = 'aria-label="Knowledge views"'
    nav = rendered.split(marker, 1)[1].split("</nav>", 1)[0]
    hrefs = _hrefs(nav)
    graph = unescape(next(href for href in hrefs if "view=graph" in href))
    parsed = parse_qs(urlsplit(graph).query)
    assert parsed == {
        "view": ["graph"],
        "stage": ["draft"],
        "category": ["workflow hint"],
        "domain": ["science/APA"],
        "q": ["brain development"],
    }


def test_knowledge_route_preserves_query_and_switches_graph_view(tmp_path: Path) -> None:
    sync_root = tmp_path / "sync"
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    app = create_app(
        repo=repo,
        sync_root=sync_root,
        config=HermesConfig(sync_root=sync_root, db_path=tmp_path / "hermes.sqlite3"),
    )
    client = TestClient(app)

    response = client.get("/knowledge", params={"view": "graph", "q": "not-present"})

    assert response.status_code == 200
    assert 'class="engram-knowledge" data-view="graph"' in response.text
    assert 'name="q" value="not-present"' in response.text
    assert "No graph to draw." in response.text


def test_brain_map_compatibility_route_targets_knowledge_graph(tmp_path: Path) -> None:
    sync_root = tmp_path / "sync"
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    app = create_app(
        repo=repo,
        sync_root=sync_root,
        config=HermesConfig(sync_root=sync_root, db_path=tmp_path / "hermes.sqlite3"),
    )
    response = TestClient(app).get("/brain-map", follow_redirects=False)

    assert response.status_code == 301
    assert response.headers["location"] == "/knowledge?view=graph"


def test_knowledge_api_pagination_rejects_non_positive_limits(tmp_path: Path) -> None:
    sync_root = tmp_path / "sync"
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    app = create_app(
        repo=repo,
        sync_root=sync_root,
        config=HermesConfig(sync_root=sync_root, db_path=tmp_path / "hermes.sqlite3"),
    )
    client = TestClient(app)

    assert client.get("/api/knowledge/graph", params={"limit": 0}).status_code == 422
    assert client.get("/api/knowledge/graph", params={"limit": 501}).status_code == 422
    assert client.get("/api/knowledge/list", params={"limit": 0}).status_code == 422


def _hrefs(fragment: str) -> list[str]:
    import re

    return re.findall(r'href="([^"]+)"', fragment)


def _unsafe_event_attributes(rendered: str) -> list[str]:
    from html.parser import HTMLParser

    unsafe: list[str] = []

    class Parser(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            unsafe.extend(name for name, _ in attrs if name.lower().startswith("on"))

    Parser().feed(rendered)
    return unsafe
