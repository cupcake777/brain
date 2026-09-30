from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.knowledge_detail import knowledge_detail_page
from hermes.repository import HermesRepository, KnowledgeNode


class _DetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.event_attributes: list[tuple[str, str]] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name.lower().startswith("on"):
                self.event_attributes.append((name, value or ""))
            if tag == "a" and name == "href" and value is not None:
                self.links.append(value)


def _node(**overrides: object) -> dict[str, object]:
    node: dict[str, object] = {
        "id": "node/α?x=1#frag",
        "parent_id": None,
        "summary": "A durable knowledge claim",
        "content": "Preserve evidence and explicit lifecycle transitions.",
        "category": "rule",
        "domain": "brain",
        "stage": "refined",
        "operation": "refine",
        "confidence": 0.82,
        "source": "conversation:session-1",
        "evidence": '[{"source_type":"conversation","source_uri":"session-1","quoted_excerpt":"source text"}]',
        "supersedes": None,
        "merged_from": "[]",
        "contradicts": "[]",
        "verified_by": "[]",
        "created_at": "2026-09-30T00:00:00+00:00",
        "refined_at": "2026-09-30T01:00:00+00:00",
        "verified_at": None,
        "deprecated_at": None,
        "retrieval_count": 3,
        "correction_count": 0,
        "last_used_at": None,
        "outcome_count": 2,
        "last_outcome_at": None,
        "outcome_distribution": {"success": 2},
        "last_retrieved_at": None,
        "is_stale": False,
        "stale_days": 0,
    }
    node.update(overrides)
    return node


def _stored_node(node_id: str, **overrides: object) -> KnowledgeNode:
    values: dict[str, object] = {
        **_node(id=node_id),
        "kind": "rule",
        "trigger_terms": "[]",
        "use_when": "Use during tests.",
        "avoid_when": "",
        "success_signal": "Rendered detail.",
        "failure_signal": "Missing detail.",
    }
    values.pop("outcome_distribution", None)
    values.pop("last_retrieved_at", None)
    values.pop("is_stale", None)
    values.pop("stale_days", None)
    values.update(overrides)
    return KnowledgeNode(**values)  # type: ignore[arg-type]


def test_detail_is_an_isolated_engram_view_without_inline_event_handlers() -> None:
    html = knowledge_detail_page(
        node=_node(),
        thought_chains=[],
        parent_node=None,
        child_nodes=[],
        supersedes_node=None,
        superseded_by=[],
        contradicts_nodes=[],
    )

    main = html.split('<main class="engram-detail"', 1)[1].split("</main>", 1)[0]
    parser = _DetailParser()
    parser.feed('<main class="engram-detail"' + main + "</main>")

    assert '<main class="engram-detail" id="knowledge-detail-main"' in html
    assert 'href="#knowledge-detail-main"' in html
    assert "Provenance" in main
    assert "History" in main
    assert "Relationships" in main
    assert parser.event_attributes == []
    assert f"/knowledge/{quote(str(_node()['id']), safe='')}" in parser.links
    assert "/proposals" not in main
    assert "/gallery" not in main


def test_detail_escapes_payloads_and_quotes_every_relationship_path() -> None:
    payload = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
    hostile_id = "x&apos;);alert(3);//?#/α"
    html = knowledge_detail_page(
        node=_node(id=hostile_id, summary=payload, content=payload, source=payload),
        thought_chains=[
            {
                "action": payload,
                "reasoning": payload,
                "decision": payload,
                "created_at": payload,
            }
        ],
        parent_node={"id": hostile_id, "summary": payload, "stage": payload},
        child_nodes=[{"id": hostile_id, "summary": payload, "stage": payload}],
        supersedes_node={"id": hostile_id, "summary": payload, "stage": payload},
        superseded_by=[{"id": hostile_id, "summary": payload, "stage": payload}],
        contradicts_nodes=[{"id": hostile_id, "summary": payload, "stage": payload}],
    )

    main = html.split('<main class="engram-detail"', 1)[1].split("</main>", 1)[0]
    parser = _DetailParser()
    parser.feed('<main class="engram-detail"' + main + "</main>")
    expected = "/knowledge/" + quote(hostile_id, safe="")

    assert payload not in main
    assert "<img" not in main
    assert "<script" not in main
    assert parser.event_attributes == []
    assert parser.links.count(expected) == 6


def test_detail_degrades_safely_for_empty_and_malformed_optional_data() -> None:
    html = knowledge_detail_page(
        node=_node(
            summary="",
            content="",
            confidence=None,
            source=None,
            evidence="not-json",
            merged_from="{}",
            verified_by=None,
            retrieval_count=None,
            outcome_count=None,
        ),
        thought_chains=[],
        parent_node=None,
        child_nodes=[],
        supersedes_node=None,
        superseded_by=[],
        contradicts_nodes=[],
    )

    assert "Untitled knowledge" in html
    assert "No claim content recorded." in html
    assert "No evidence recorded." in html
    assert "No reasoning history recorded." in html
    assert "Not available" in html
    assert ">None<" not in html


def test_detail_route_uses_isolated_renderer_and_resolves_contradictions(tmp_path: Path) -> None:
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "brain.sqlite3")
    repo = HermesRepository(config.db_path)
    repo.insert_knowledge_node(_stored_node("node-main", contradicts='["node/other"]'))
    repo.insert_knowledge_node(_stored_node("node/other", summary="Conflicting claim"))
    client = TestClient(create_app(repo=repo, sync_root=config.sync_root, config=config))

    response = client.get("/knowledge/node-main")

    assert response.status_code == 200
    assert '<main class="engram-detail" id="knowledge-detail-main"' in response.text
    assert "Conflicting claim" in response.text
    assert "/knowledge/node%2Fother" in response.text
    assert "onclick=\"knPromote" not in response.text


def test_detail_exposes_explicit_lifecycle_actions_without_dynamic_javascript() -> None:
    html = knowledge_detail_page(
        node=_node(id="node/action", stage="refined"),
        thought_chains=[],
        parent_node=None,
        child_nodes=[],
        supersedes_node=None,
        superseded_by=[],
        contradicts_nodes=[{"id": "source/one", "summary": "Conflict", "stage": "verified"}],
    )
    main = html.split('<main class="engram-detail"', 1)[1].split("</main>", 1)[0]
    parser = _DetailParser()
    parser.feed('<main class="engram-detail"' + main + "</main>")

    assert 'data-detail-action="edit"' in main
    assert 'data-detail-action="stage"' in main
    assert 'data-next-stage="verified"' in main
    assert 'data-detail-action="deprecate"' in main
    assert 'data-detail-action="merge"' in main
    assert "/api/knowledge/node%2Faction/stage" in main
    assert "/api/knowledge/node%2Faction/merge/source%2Fone" in main
    assert 'role="dialog"' in html
    assert 'aria-live="polite"' in html
    assert parser.event_attributes == []


def test_detail_dialog_traps_focus_and_mutations_keep_same_origin_credentials() -> None:
    html = knowledge_detail_page(
        node=_node(id="node-focus", stage="refined"),
        thought_chains=[],
        parent_node=None,
        child_nodes=[],
        supersedes_node=None,
        superseded_by=[],
        contradicts_nodes=[],
    )

    assert "credentials:'same-origin'" in html
    assert "event.key==='Tab'" in html
    assert "focusableElements" in html
    assert "first.focus()" in html
    assert "last.focus()" in html
    assert "closeDialog();showStatus('Knowledge updated.'" in html
