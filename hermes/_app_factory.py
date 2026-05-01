"""App factory for uvicorn --reload --factory mode."""
from hermes.app import create_app as _create_app
from hermes.repository import HermesRepository
from pathlib import Path
import os


def create_app():
    """Factory function called by uvicorn in reload mode."""
    sync_root = os.environ.get("HERMES_SYNC_ROOT", os.environ.get("BRAIN_SYNC_ROOT", str(Path.home() / "hermes-sync")))
    db_path = str(Path(sync_root) / "hermes.sqlite3")
    repo = HermesRepository(db_path)
    return _create_app(repo=repo, sync_root=sync_root)