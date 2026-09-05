from pathlib import Path

import pytest

from app.config.settings import Settings
from app.main import health
from app.scripts.seed_demo import SELECTED_PRODUCTS, require_demo


def test_demo_environment_and_small_neon_pool_are_supported():
    settings = Settings(APP_ENV="demo", DATABASE_URL="postgresql+asyncpg://user:pass@db.example/demo", SECRET_KEY="x" * 32)
    assert settings.environment == "demo"
    assert settings.database_pool_size == 5
    assert settings.database_max_overflow == 5


def test_demo_seed_selects_only_nine_final_products():
    assert len(SELECTED_PRODUCTS) == 9
    assert "Naruto Rasengan" in SELECTED_PRODUCTS
    assert "Luffy Sitting — Variant 1" in SELECTED_PRODUCTS


def test_demo_seed_refuses_current_non_demo_environment():
    with pytest.raises(RuntimeError, match="must be 'demo'"):
        require_demo()


@pytest.mark.asyncio
async def test_health_payload_contains_no_environment_details():
    assert await health() == {"status": "ok"}


def test_deployment_manifests_exist():
    root = Path(__file__).resolve().parents[2]
    assert (root / "netlify.toml").is_file()
    assert (root / "render.yaml").is_file()
