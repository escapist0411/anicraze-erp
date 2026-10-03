"""Filesystem locations owned by the backend runtime."""

from pathlib import Path
from app.config.settings import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]
settings = get_settings()
if settings.storage_backend == "volume":
    if settings.storage_root is None or not settings.storage_root.is_absolute():
        raise RuntimeError("STORAGE_ROOT must be an absolute mounted-volume path")
    STORAGE_ROOT = settings.storage_root.resolve()
    UPLOAD_DIR = STORAGE_ROOT / "public" / "uploads"
    PRIVATE_DOCUMENT_DIR = STORAGE_ROOT / "private" / "documents"
else:
    if settings.environment == "production":
        raise RuntimeError("Production requires durable STORAGE_BACKEND=volume")
    STORAGE_ROOT = BACKEND_ROOT
    UPLOAD_DIR = BACKEND_ROOT / "uploads"
    PRIVATE_DOCUMENT_DIR = BACKEND_ROOT / "generated"


def ensure_runtime_directories() -> None:
    """Create directories required during application import/startup."""

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PRIVATE_DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
