"""Filesystem locations owned by the backend runtime."""

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_ROOT / "uploads"


def ensure_runtime_directories() -> None:
    """Create directories required during application import/startup."""

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
