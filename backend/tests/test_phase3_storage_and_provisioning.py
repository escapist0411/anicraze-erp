from pathlib import Path
from types import SimpleNamespace as Obj

import pytest

from app.config.settings import Settings
from app.scripts.seed_demo import require_demo_database
from app.storage import DocumentStorage, PublicAssetFiles
from scripts.bootstrap_production_users import expected_database


def test_private_document_storage_rejects_traversal_and_other_roots(tmp_path):
    storage = DocumentStorage(tmp_path / "private")
    invoice = storage.save("invoices", "ANI-INV-000001.pdf", b"%PDF-1.4\n")
    assert storage.read_path(str(invoice), "invoices").read_bytes().startswith(b"%PDF")
    for kind, name in (("invoices", "../secret.pdf"), ("reports", "/etc/passwd"),
                       ("invoices", ".env"), ("unknown", "test.pdf")):
        with pytest.raises(ValueError):
            storage.save(kind, name, b"unsafe")
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"private")
    with pytest.raises(FileNotFoundError):
        storage.read_path(str(outside), "invoices")
    with pytest.raises(FileNotFoundError):
        storage.read_path(str(invoice), "reports")


@pytest.mark.asyncio
async def test_public_asset_mount_rejects_private_or_dotfile_paths(tmp_path):
    assets = PublicAssetFiles(directory=tmp_path)
    for path in (".env", "private/invoices/one.pdf", "products/a/secret.txt", "barcodes/../../.env"):
        with pytest.raises(Exception) as exc:
            await assets.get_response(path, {"type": "http", "method": "GET"})
        assert getattr(exc.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_reset_guard_refuses_connected_production_like_name(monkeypatch):
    import app.scripts.seed_demo as module
    monkeypatch.setattr(module, "require_demo", lambda: None)
    class FakeSession:
        async def scalar(self, _query):
            return "anicraze_production"
    with pytest.raises(RuntimeError, match="connected database"):
        await require_demo_database(FakeSession())


def test_production_bootstrap_refuses_demo_or_unconfirmed_target(monkeypatch):
    import scripts.bootstrap_production_users as module
    monkeypatch.setattr(module, "get_settings", lambda: Obj(environment="production", database_url="postgresql+asyncpg://user:pass@localhost/anicraze_demo"))
    monkeypatch.setenv("ANICRAZE_PRODUCTION_DATABASE", "anicraze_demo")
    monkeypatch.setenv("ANICRAZE_CONFIRM_DATABASE", "anicraze_demo")
    with pytest.raises(RuntimeError, match="identity"):
        expected_database()
    monkeypatch.setattr(module, "get_settings", lambda: Obj(environment="production", database_url="postgresql+asyncpg://user:pass@localhost/anicraze_production"))
    monkeypatch.setenv("ANICRAZE_PRODUCTION_DATABASE", "anicraze_production")
    monkeypatch.delenv("ANICRAZE_CONFIRM_DATABASE", raising=False)
    with pytest.raises(RuntimeError, match="identity"):
        expected_database()


def test_production_settings_have_explicit_storage_mode():
    settings = Settings(APP_ENV="production", DATABASE_URL="postgresql+asyncpg://user:pass@localhost/anicraze_production", SECRET_KEY="x" * 32,
                        STORAGE_BACKEND="volume", STORAGE_ROOT="/mnt/anicraze")
    assert settings.storage_backend == "volume" and settings.storage_root == Path("/mnt/anicraze")
