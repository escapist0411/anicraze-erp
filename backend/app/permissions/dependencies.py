import logging
from collections.abc import Callable
from fastapi import Request

from app.dependencies.auth import CurrentUser
from app.exceptions.domain import AuthorizationError
from app.models.auth import RoleName, User

logger = logging.getLogger(__name__)

# SALES is a shop POS role, not a legacy CRM/warehouse/finance role. Keep this
# allowlist at the permission dependency so a newly added route fails closed.
SALES_ROUTES = {
    ("GET", "/api/v1/stores"),
    ("GET", "/api/v1/inventory"),
    ("GET", "/api/v1/inventory/{id}"),
    ("GET", "/api/v1/inventory/transactions"),
    ("GET", "/api/v1/inventory/ledger"),
    ("GET", "/api/v1/stock-transfers"),
    ("GET", "/api/v1/stock-transfers/{id}"),
    ("GET", "/api/v1/stock-transfers/{id}/receipt"),
    ("GET", "/api/v1/billing/search"),
    ("GET", "/api/v1/billing/barcode/{barcode}"),
    ("GET", "/api/v1/billing/products"),
    ("POST", "/api/v1/billing"),
    ("GET", "/api/v1/invoices"),
    ("GET", "/api/v1/invoices/{id}"),
    ("GET", "/api/v1/invoices/{id}/pdf"),
    ("GET", "/api/v1/invoices/{id}/history"),
    ("POST", "/api/v1/invoices/{id}/cancel"),
    ("GET", "/api/v1/returns"),
    ("POST", "/api/v1/returns"),
    ("GET", "/api/v1/billing/analytics"),
    ("GET", "/api/v1/billing/reports/sales"),
    ("GET", "/api/v1/billing/reports/returns"),
    ("GET", "/api/v1/cash-register"),
    ("GET", "/api/v1/reports/{domain}/{report}"),
}


def _sales_route_allowed(user: User, request: Request) -> bool:
    if "SALES" not in _role_names(user):
        return True
    route = request.scope.get("route")
    path = getattr(route, "path", "")
    if (request.method, path) not in SALES_ROUTES:
        return False
    if path == "/api/v1/reports/{domain}/{report}":
        return request.path_params.get("domain") == "sales"
    return True


def _normalize_roles(roles: tuple[str | RoleName, ...]) -> set[str]:
    return {str(role).upper() for role in roles}


def _role_names(user: User) -> set[str]:
    return {str(role.code or role.name).upper() for role in user.roles}


def _permission_codes(user: User) -> set[str]:
    return {permission.code for role in user.roles for permission in role.permissions} | {permission.code for permission in user.direct_permissions}


def require_roles(*roles: str | RoleName, owner_bypass: bool = True) -> Callable[..., object]:
    expected = _normalize_roles(roles)
    if not expected:
        raise ValueError("At least one role is required")

    async def validator(user: CurrentUser) -> User:
        granted = _role_names(user)
        if not expected.intersection(granted) and not (owner_bypass and RoleName.OWNER.value in granted):
            logger.warning("Role access denied for user_id=%s required_roles=%s", user.id, sorted(expected))
            raise AuthorizationError("A required role is missing", "AUTH_ROLE_REQUIRED")
        return user

    return validator


def require_permission(permission_code: str) -> Callable[..., object]:
    return require_all_permissions(permission_code)


def require_any_permission(*permission_codes: str) -> Callable[..., object]:
    expected = {code.strip().lower() for code in permission_codes if code.strip()}
    if not expected:
        raise ValueError("At least one permission is required")

    async def validator(user: CurrentUser, request: Request) -> User:
        granted = _permission_codes(user)
        if not _sales_route_allowed(user, request) or ("*" not in granted and RoleName.OWNER.value not in _role_names(user) and not expected.intersection(granted)):
            logger.warning("Permission access denied for user_id=%s required_any=%s", user.id, sorted(expected))
            raise AuthorizationError("A required permission is missing", "AUTH_PERMISSION_DENIED")
        return user

    return validator


def require_all_permissions(*permission_codes: str) -> Callable[..., object]:
    expected = {code.strip().lower() for code in permission_codes if code.strip()}
    if not expected:
        raise ValueError("At least one permission is required")

    async def validator(user: CurrentUser, request: Request) -> User:
        granted = _permission_codes(user)
        if not _sales_route_allowed(user, request) or ("*" not in granted and RoleName.OWNER.value not in _role_names(user) and not expected.issubset(granted)):
            logger.warning("Permission access denied for user_id=%s required_all=%s", user.id, sorted(expected))
            raise AuthorizationError("A required permission is missing", "AUTH_PERMISSION_DENIED")
        return user

    return validator


def require_permissions(*permission_codes: str) -> Callable[..., object]:
    return require_all_permissions(*permission_codes)


async def require_owner(user: CurrentUser) -> User:
    return await require_roles(RoleName.OWNER, owner_bypass=False)(user)


async def require_admin(user: CurrentUser) -> User:
    return await require_roles(RoleName.ADMIN, owner_bypass=True)(user)
