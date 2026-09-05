from app.config.settings import get_settings


def test_settings_loads_required_configuration() -> None:
    settings = get_settings()
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.access_token_expire_minutes > 0
