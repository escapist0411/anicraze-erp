from uuid import uuid4

from app.auth.passwords import hash_password, verify_password
from app.auth.tokens import create_access_token, create_refresh_token, decode_token
from app.models.auth import Role, RoleName, User


def test_password_and_jwt_round_trip() -> None:
    password_hash = hash_password("UnitTestPassword!234")
    assert verify_password("UnitTestPassword!234", password_hash)
    role = Role(name=RoleName.OWNER, description="Full enterprise authority")
    user = User(id=uuid4(), email="owner@anicraze.com", full_name="ANICRAZE Owner", password_hash=password_hash, roles=[role])
    access_token, _ = create_access_token(user)
    refresh_token, refresh_jti, _ = create_refresh_token(user)
    access_payload = decode_token(access_token, "access")
    assert access_payload["roles"] == ["OWNER"]
    assert access_payload["permissions"] == ["*"]
    assert access_payload["token_type"] == "access"
    assert decode_token(refresh_token, "refresh")["jti"] == refresh_jti
