from hermes.cli import build_app, build_runtime, main


def test_build_runtime_uses_paths_under_sync_root(tmp_path) -> None:
    runtime = build_runtime(sync_root=tmp_path / "shared")

    assert runtime.config.db_path == tmp_path / "shared" / "hermes.sqlite3"
    assert runtime.config.proposals_dir == tmp_path / "shared" / "inbox" / "proposals"


def test_build_app_exposes_health_endpoint(tmp_path) -> None:
    app = build_app(sync_root=tmp_path / "shared")

    routes = {route.path for route in app.routes}
    assert "/health" in routes


def test_main_scan_command_returns_zero(tmp_path) -> None:
    exit_code = main(["--sync-root", str(tmp_path / "shared"), "scan"])

    assert exit_code == 0
