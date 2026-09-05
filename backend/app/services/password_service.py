import re

from app.auth.passwords import hash_password, verify_password
from app.config.settings import get_settings
from app.exceptions.domain import PasswordValidationError
from app.models.auth import User

COMMON_WEAK_PASSWORDS = {
    "admin@123",
    "password",
    "password123",
    "qwerty123",
    "welcome123",
    "12345678",
}


class PasswordService:
    @staticmethod
    def hash(password: str) -> str:
        return hash_password(password)

    @staticmethod
    def verify(password: str, password_hash: str) -> bool:
        return verify_password(password, password_hash)

    @staticmethod
    def validate_new_password(password: str, user: User) -> None:
        settings = get_settings()
        lowered = password.casefold()
        if password != password.strip():
            raise PasswordValidationError("Password must not have leading or trailing whitespace")
        if not settings.password_min_length <= len(password) <= settings.password_max_length:
            raise PasswordValidationError(
                f"Password must be between {settings.password_min_length} and {settings.password_max_length} characters"
            )
        if not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password):
            raise PasswordValidationError("Password must include uppercase and lowercase characters")
        if not re.search(r"\d", password):
            raise PasswordValidationError("Password must include a number")
        if not re.search(r"[^A-Za-z0-9]", password):
            raise PasswordValidationError("Password must include a special character")
        if lowered in {user.email.casefold(), user.full_name.casefold()} or lowered in COMMON_WEAK_PASSWORDS:
            raise PasswordValidationError("Password is too common or closely matches your account details")
