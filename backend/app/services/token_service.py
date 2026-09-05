import secrets

from app.auth.tokens import TokenService, decode_token
from app.utils.security import sha256


class SecurityTokenService:
    """Security-oriented token helpers used by account services."""

    @staticmethod
    def hash_token(token: str) -> str:
        return sha256(token)

    @staticmethod
    def generate_password_reset_token() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def decode_access_token(token: str) -> dict[str, object]:
        return decode_token(token, "access")

    @staticmethod
    def decode_refresh_token(token: str) -> dict[str, object]:
        return decode_token(token, "refresh")


__all__ = ["SecurityTokenService", "TokenService"]
