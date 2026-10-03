"""Regression contract for the recovered Grok Engram visual package.

The source package is archived at reference-packages/grok-engram and is used as
visual provenance only; backend behavior and safe renderer code stay local.
"""

from hermes.templates import _DARK_CSS, _page


def test_grok_engram_tokens_are_default_and_shared():
    assert "/* Engram light (DEFAULT)" in _DARK_CSS
    assert "--bg:#ffffff" in _DARK_CSS
    assert "--primary:#000000" in _DARK_CSS
    assert "--sidebar-w:220px" in _DARK_CSS
    assert "html:not([data-theme])" in _DARK_CSS


def test_page_renderer_keeps_avatar_dom_construction_safe():
    rendered = _page("Contract", "<main>ok</main>")
    assert "renderStoredAvatar" in rendered
    assert "document.createElement('img')" in rendered
    assert "innerHTML='<img" not in rendered
    assert "onerror=\\\"this.outerHTML" not in rendered


def test_grok_visual_contract_does_not_add_render_endpoint():
    assert "/api/render" not in _DARK_CSS
