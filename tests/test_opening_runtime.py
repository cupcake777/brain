from pathlib import Path


def test_opening_asset_loaders_have_timeout_guard() -> None:
    source = Path("hermes/opening/app.js").read_text()
    assert "Promise.race" in source
    assert "ASSET_LOAD_TIMEOUT_MS" in source


def test_opening_sunset_ad_assets_exist() -> None:
    source = Path("hermes/opening/app.js").read_text()
    for line in source.splitlines():
        if '"./assets/ads/' in line:
            asset = line.strip().strip(",").strip('"')
            assert Path("hermes/opening", asset[2:]).is_file(), asset
