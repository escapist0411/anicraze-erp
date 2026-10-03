"""Private document storage on a local filesystem or mounted durable volume.

The provider is configured in app.config.paths. Database paths are never
trusted for retrieval without containment validation.
"""

import re
from pathlib import Path
from pathlib import PurePosixPath
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from app.config.paths import PRIVATE_DOCUMENT_DIR

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$")
_KINDS = {"invoices", "reports", "payslips", "procurement"}


class DocumentStorage:
    def __init__(self, root: Path = PRIVATE_DOCUMENT_DIR):
        self.root = root.resolve()

    def _target(self, kind: str, filename: str) -> Path:
        if kind not in _KINDS or not _SAFE.fullmatch(filename) or filename in {".", ".."}:
            raise ValueError("Unsafe document storage key")
        return self.root / kind / filename

    def save(self, kind: str, filename: str, content: bytes) -> Path:
        path = self._target(kind, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def read_path(self, stored_path: str, kind: str) -> Path:
        if kind not in _KINDS:
            raise ValueError("Unsafe document kind")
        path = Path(stored_path).resolve()
        if path.parent != (self.root / kind).resolve() or not path.is_file():
            raise FileNotFoundError("Private document is unavailable")
        return path


class PublicAssetFiles(StaticFiles):
    """Expose only catalog artwork and regeneratable barcode images."""

    async def get_response(self, path: str, scope):
        parts = PurePosixPath(path.replace("\\", "/")).parts
        allowed = ((len(parts) == 3 and parts[0] == "products" and
                    parts[2].lower().endswith((".jpg", ".png", ".webp"))) or
                   (len(parts) == 2 and parts[0] == "barcodes" and
                    parts[1].lower().endswith(".svg")))
        if not allowed or any(part.startswith(".") or part in {"..", ""} for part in parts):
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)
