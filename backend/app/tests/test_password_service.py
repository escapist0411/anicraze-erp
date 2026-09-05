from uuid import uuid4

import pytest

from app.exceptions.domain import PasswordValidationError
from app.models.auth import User
from app.services.password_service import PasswordService


def make_user() -> User:
    return User(
        id=uuid4(),
        email="owner@anicraze.com",
        full_name="ANICRAZE Owner",
        password_hash="unused",
    )


def test_password_policy_accepts_strong_password() -> None:
    PasswordService.validate_new_password("Enterprise@2026", make_user())


def test_password_policy_rejects_weak_password() -> None:
    with pytest.raises(PasswordValidationError):
        PasswordService.validate_new_password("password123", make_user())
