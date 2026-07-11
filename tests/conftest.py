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
