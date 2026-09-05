import httpx
import pytest
from pydantic import ValidationError

from app.main import app
from app.schemas.management import UserCreateRequest, UserUpdateRequest


@pytest.mark.asyncio
async def test_openapi_documents_management_endpoints() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        paths = (await client.get("/api/v1/openapi.json")).json()["paths"]
    expected = {"/api/v1/users", "/api/v1/users/{user_id}/status", "/api/v1/users/{user_id}/roles", "/api/v1/users/{user_id}/permissions", "/api/v1/users/{user_id}/reset-password", "/api/v1/users/{user_id}/sessions", "/api/v1/roles", "/api/v1/permissions", "/api/v1/permissions/grouped"}
    assert expected.issubset(paths)


def test_create_user_normalizes_email_and_requires_matching_passwords() -> None:
    payload = UserCreateRequest(name="Test User", email="TEST@ANICRAZE.COM", password="Strong@1234", confirm_password="Strong@1234")
    assert payload.email == "test@anicraze.com"
    with pytest.raises(ValidationError):
        UserCreateRequest(name="Test User", email="test@anicraze.com", password="Strong@1234", confirm_password="Different@123")


def test_user_update_rejects_security_fields() -> None:
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"password_hash": "secret"})
