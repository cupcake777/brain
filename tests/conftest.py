from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_embedding_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests from calling a production embedding endpoint."""
    monkeypatch.setenv("BRAIN_DISABLE_EMBEDDINGS", "1")


@pytest.fixture(autouse=True)
def _isolate_agent_context(monkeypatch, tmp_path):
    """Runtime/API tests must never write the operator's real agent memory."""
    monkeypatch.setenv('HERMES_CONTEXT_PATH',str(tmp_path/'agent'/'brain-context.md'))


@pytest.fixture(autouse=True)
def _isolate_workspace_settings(monkeypatch, tmp_path):
    """Settings tests must not overwrite the running workspace or its credentials."""
    monkeypatch.setenv('BRAIN_PROFILE_PATH', str(tmp_path/'settings'/'profile.json'))
    monkeypatch.setenv('HERMES_ENV_FILE', str(tmp_path/'settings'/'private.env'))


@pytest.fixture(autouse=True)
def _isolate_web_background_worker(monkeypatch):
    """UI tests drive ingestion explicitly; a live scanner races those fixtures."""
    monkeypatch.setattr("hermes.app._start_bg_runtime_if_needed", lambda *args: None)
