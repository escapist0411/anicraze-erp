from app.config.paths import BACKEND_ROOT, UPLOAD_DIR, ensure_runtime_directories


def test_upload_directory_is_scoped_to_backend_root() -> None:
    ensure_runtime_directories()

    assert UPLOAD_DIR == BACKEND_ROOT / "uploads"
    assert UPLOAD_DIR.is_dir()
    assert UPLOAD_DIR.parent == BACKEND_ROOT
