class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        if code is not None:
            self.code = code
        super().__init__(message)


class AuthenticationError(DomainError):
    status_code = 401
    code = "AUTH_TOKEN_INVALID"


class AuthorizationError(DomainError):
    status_code = 403
    code = "AUTH_PERMISSION_DENIED"


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class PasswordValidationError(DomainError):
    status_code = 422
    code = "AUTH_PASSWORD_TOO_WEAK"
