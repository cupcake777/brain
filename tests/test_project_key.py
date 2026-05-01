from pathlib import Path

from hermes.project_key import resolve_project_key


def test_resolve_project_key_prefers_explicit_hermes_project(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    nested = root / "src" / "module"
    nested.mkdir(parents=True)
    (root / ".hermes-project").write_text(
        "project_key: eqtl_flip_2026\n"
        "display_name: Flip eQTL Analysis\n",
        encoding="utf-8",
    )

    result = resolve_project_key(nested)

    assert result.project_key == "eqtl_flip_2026"
    assert result.source == "hermes-project"
    assert result.warning is None


def test_resolve_project_key_uses_git_remote_hash(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text(
        '[remote "origin"]\n'
        "\turl = git@github.com:ExampleOrg/Brain.git\n",
        encoding="utf-8",
    )

    result = resolve_project_key(root)

    assert result.project_key == "5e4063a02a02"
    assert result.source == "git-remote"
    assert result.warning is None


def test_resolve_project_key_falls_back_to_project_root_name(tmp_path: Path) -> None:
    root = tmp_path / "brain-app"
    nested = root / "service"
    nested.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='brain-app'\n", encoding="utf-8")

    result = resolve_project_key(nested)

    assert result.project_key == "brain-app"
    assert result.source == "cwd-fallback"
    assert "not portable" in result.warning


def test_resolve_project_key_returns_global_when_no_project_root_exists(tmp_path: Path) -> None:
    folder = tmp_path / "scratch" / "notes"
    folder.mkdir(parents=True)

    result = resolve_project_key(folder)

    assert result.project_key == "global"
    assert result.source == "global"
    assert result.warning is None
