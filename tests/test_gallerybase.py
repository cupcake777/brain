from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

from hermes.config import HermesConfig
from hermes.gallerybase import gallery_detail_page, gallery_page
from hermes.repository import HermesRepository
from hermes.app import create_app


def _chart(**overrides: object) -> dict[str, object]:
    chart: dict[str, object] = {
        "name": "volcano",
        "title": "Volcano plot",
        "description": "Differential expression overview",
        "tier": "P1",
        "status": "done",
        "data_type": "point_table",
        "tags": ["RNA", "DE"],
        "demo": "demos/volcano.png",
        "interactive": "interactive/volcano.html",
        "template": "templates/volcano.py",
        "required_fields": ["log2fc", "pvalue"],
        "optional_fields": ["label"],
        "visual_encodings": {"x": "log2fc", "y": "-log10(p)"},
        "reusable_for": ["RNA-seq"],
    }
    chart.update(overrides)
    return chart


def _client_for_catalog(tmp_path: Path, monkeypatch, catalog: Any) -> tuple[TestClient, Path]:
    plotting = tmp_path / "plotting"
    plotting.mkdir()
    (plotting / "catalog.yaml").write_text(yaml.safe_dump(catalog), encoding="utf-8")
    monkeypatch.setenv("BRAIN_PLOTTING_DIR", str(plotting))
    config = HermesConfig(sync_root=tmp_path / "sync", db_path=tmp_path / "sync" / "hermes.sqlite3")
    repo = HermesRepository(config.db_path)
    return TestClient(create_app(repo=repo, sync_root=config.sync_root, config=config)), plotting


def test_gallery_list_is_static_local_and_escapes_catalog_content() -> None:
    payload = '<img src=x onerror=alert(1)><script>alert(2)</script>'
    html = gallery_page(charts=[_chart(name="chart/id", title=payload, description=payload)])

    assert 'id="gallery-main"' in html
    assert "/gallery/chart%2Fid" in html
    assert payload not in html
    assert "&lt;script&gt;alert(2)&lt;/script&gt;" in html
    assert 'src="http://' not in html and 'src="https://' not in html
    assert 'href="http://' not in html and 'href="https://' not in html
    assert "poster" not in html.lower()
    assert 'id="gallery-no-results"' in html
    assert 'aria-live="polite"' in html
    assert 'id="gallery-clear-filters"' in html
    assert 'id="welcomeOverlay"' not in html
    gallery_script = html.split('id="gallery-main"', 1)[1]
    assert "/api/gallery/feedback" not in gallery_script
    assert "/api/render" not in gallery_script
    gallery_main = html.split('<main id="gallery-main"', 1)[1].split("</main>", 1)[0]
    assert "onclick=" not in gallery_main


def test_gallery_detail_allows_only_catalog_local_assets() -> None:
    html = gallery_detail_page(chart=_chart())

    assert 'src="/gallery/static/demos/volcano.png"' in html
    assert 'src="/gallery/static/interactive/volcano.html"' in html
    assert 'sandbox="allow-scripts"' in html
    assert "allow-same-origin" not in html
    assert "/api/gallery/template/templates/volcano.py" in html
    assert 'id="welcomeOverlay"' not in html

    unsafe = gallery_detail_page(
        chart=_chart(
            demo="https://attacker.invalid/a.png",
            interactive="../secret.html",
            template="/etc/passwd",
        )
    )
    assert "attacker.invalid" not in unsafe
    assert "../secret.html" not in unsafe
    assert "/etc/passwd" not in unsafe
    assert "<iframe" not in unsafe


def test_gallery_empty_and_missing_states_are_explicit() -> None:
    assert "No figure templates yet" in gallery_page(charts=[])
    missing = gallery_detail_page(chart=None, chart_name="missing/chart")
    assert "Figure not found" in missing
    assert "/gallery" in missing
    assert "missing/chart" not in missing


def test_gallery_rendered_scripts_are_syntax_valid(tmp_path: Path) -> None:
    html = gallery_page(charts=[_chart()]) + gallery_detail_page(chart=_chart())
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.I | re.S)
    assert scripts
    for index, script in enumerate(scripts, 1):
        script_path = tmp_path / f"gallery-{index}.js"
        script_path.write_text(script, encoding="utf-8")
        import subprocess

        result = subprocess.run(["node", "--check", str(script_path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_gallery_routes_use_isolated_renderer_and_normalized_catalog(tmp_path: Path, monkeypatch) -> None:
    client, plotting = _client_for_catalog(
        tmp_path,
        monkeypatch,
        {
            "templates": [
                {
                    "id": "volcano",
                    "title": "Volcano plot",
                    "input_shape": "point_table",
                    "tier": "P1",
                    "status": "done",
                    "demo_png": "demos/volcano.png",
                    "interactive": "interactive/volcano.html",
                }
            ]
        },
    )
    (plotting / "interactive").mkdir()
    (plotting / "interactive" / "volcano.html").write_text("<script>fetch('https://attacker.invalid')</script>", encoding="utf-8")

    listing = client.get("/gallery")
    detail = client.get("/gallery/volcano")
    assert listing.status_code == 200
    assert 'id="gallery-main"' in listing.text
    assert "Volcano plot" in listing.text
    assert detail.status_code == 200
    assert 'id="gallery-detail-main"' in detail.text
    assert "Volcano plot" in detail.text
    assert 'sandbox="allow-scripts"' in detail.text
    interactive = client.get("/gallery/static/interactive/volcano.html")
    assert interactive.status_code == 200
    csp = interactive.headers["content-security-policy"]
    assert "connect-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "frame-ancestors 'none'" not in csp


def test_gallery_catalog_rejects_malformed_shapes_instead_of_500(tmp_path: Path, monkeypatch) -> None:
    for index, catalog in enumerate(
        (
            {"templates": None},
            {"templates": [None, "bad", {"id": "ok"}]},
            {"charts": None},
            {"charts": "oops"},
            {"charts": [None, "bad", {"name": "ok"}]},
        )
    ):
        case = tmp_path / str(index)
        case.mkdir()
        client, _ = _client_for_catalog(case, monkeypatch, catalog)
        assert client.get("/gallery").status_code == 200
        response = client.get("/api/gallery/catalog")
        assert response.status_code == 200
        assert all(isinstance(chart, dict) for chart in response.json()["charts"])


def test_gallery_static_allowlist_is_typed_and_template_paths_round_trip(tmp_path: Path, monkeypatch) -> None:
    client, plotting = _client_for_catalog(
        tmp_path,
        monkeypatch,
        {
            "charts": [
                {
                    "name": "nested",
                    "title": "Nested template",
                    "demo": "demos/secret.txt",
                    "interactive": "interactive/chart.html",
                    "template": "templates/sub/nested.py",
                }
            ]
        },
    )
    for relative, content in {
        "demos/secret.txt": "SECRET",
        "interactive/chart.html": "<p>interactive</p>",
        "templates/sub/nested.py": "print('ok')",
    }.items():
        target = plotting / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    assert client.get("/gallery/static/demos/secret.txt").status_code == 404
    detail = client.get("/gallery/nested")
    assert detail.status_code == 200
    assert "/api/gallery/template/templates/sub/nested.py" in detail.text
    source = client.get("/api/gallery/template/templates/sub/nested.py")
    assert source.status_code == 200
    assert source.json()["content"] == "print('ok')"
    assert client.get("/gallery/static").status_code == 404


def test_gallery_does_not_render_missing_or_unsafe_preview_assets(tmp_path: Path, monkeypatch) -> None:
    client, _ = _client_for_catalog(
        tmp_path,
        monkeypatch,
        {
            "charts": [
                {"name": "missing", "title": "Missing", "demo": "demos/missing.png"},
                {"name": "svg", "title": "SVG", "demo": "demos/active.svg"},
            ]
        },
    )
    listing = client.get("/gallery")
    assert listing.status_code == 200
    assert "/gallery/static/demos/missing.png" not in listing.text
    assert "/gallery/static/demos/active.svg" not in listing.text
    assert "Local figure unavailable" in client.get("/gallery/missing").text
