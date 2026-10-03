"""Location boundary for shop-assigned accounts.

An assigned store is an authorization constraint, never merely a default filter.
"""

from uuid import UUID

from app.exceptions.domain import AuthorizationError
from app.models.auth import User


def assigned_shop(actor: User) -> UUID | None:
    roles = {role.code for role in actor.roles}
    if not roles.intersection({"SALES", "EMPLOYEE"}):
        return None
    if actor.assigned_store_id is None:
        raise AuthorizationError("No shop is assigned to this account", "SHOP_SCOPE_REQUIRED")
    return actor.assigned_store_id


def require_shop_access(actor: User, store_id: UUID | None) -> UUID | None:
    shop_id = assigned_shop(actor)
    if shop_id is not None and store_id != shop_id:
        raise AuthorizationError("Resource is outside your assigned shop", "SHOP_SCOPE_DENIED")
    return store_id


def scoped_shop(actor: User, requested_store_id: UUID | None = None) -> UUID | None:
    shop_id = assigned_shop(actor)
    if shop_id is not None:
        if requested_store_id is not None and requested_store_id != shop_id:
            raise AuthorizationError("Resource is outside your assigned shop", "SHOP_SCOPE_DENIED")
        return shop_id
    return requested_store_id
