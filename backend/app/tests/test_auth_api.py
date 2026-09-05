import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_openapi_documents_all_authentication_endpoints() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/refresh" in paths
    assert "/api/v1/auth/reset-password" in paths
    assert "/api/v1/auth/sessions/{session_id}" in paths
