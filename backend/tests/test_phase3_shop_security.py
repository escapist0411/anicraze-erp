"""Two-shop negative regressions without touching a live database."""

from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.exceptions.domain import AuthorizationError
from app.permissions.dependencies import SALES_ROUTES, _sales_route_allowed, require_permission
from app.main import app
from fastapi.routing import APIRoute
from app.permissions.store_scope import require_shop_access, scoped_shop
from app.repositories.billing import InvoiceRepository, ReturnRepository
from app.repositories.inventory import InventoryRepository
from app.services.inventory import InventoryService


SHOP_A, SHOP_B, WAREHOUSE = uuid4(), uuid4(), uuid4()


def actor(role, shop=None):
    return Obj(id=uuid4(), assigned_store_id=shop, roles=[Obj(code=role, permissions=[Obj(code="inventory.read"), Obj(code="billing.read")])], direct_permissions=[])


def request(method, route, **params):
    return Request({"type": "http", "method": method, "path": route,
                    "headers": [], "route": Obj(path=route), "path_params": params})


@pytest.mark.parametrize("home,foreign", [(SHOP_A, SHOP_B), (SHOP_B, SHOP_A)])
def test_sales_store_and_warehouse_boundary(home, foreign):
    sales = actor("SALES", home)
    assert scoped_shop(sales) == home
    assert require_shop_access(sales, home) == home
    for target in (foreign, None):
        with pytest.raises(AuthorizationError):
            scoped_shop(sales, target) if target is foreign else require_shop_access(sales, target)
        with pytest.raises(AuthorizationError):
            require_shop_access(sales, target)
    assert scoped_shop(actor("OWNER"), foreign) == foreign
    assert scoped_shop(actor("MANAGER"), foreign) == foreign


@pytest.mark.asyncio
@pytest.mark.parametrize("home,foreign", [(SHOP_A, SHOP_B), (SHOP_B, SHOP_A)])
async def test_known_foreign_or_warehouse_inventory_id_is_rejected(home, foreign):
    service = InventoryService.__new__(InventoryService)
    service.actor = actor("SALES", home)
    service.repo = Obj(get=AsyncMock(side_effect=[Obj(store_id=home), Obj(store_id=foreign), Obj(store_id=None)]))
    assert (await service.get(uuid4())).store_id == home
    with pytest.raises(AuthorizationError):
        await service.get(uuid4())
    with pytest.raises(AuthorizationError):
        await service.get(uuid4())


class FakeScalars:
    def all(self):
        return []
    def unique(self):
        return self


class QuerySession:
    def __init__(self):
        self.queries = []
    async def scalars(self, query):
        self.queries.append(str(query))
        return FakeScalars()


@pytest.mark.asyncio
async def test_inventory_ledger_and_transactions_apply_shop_filter_to_list_and_id():
    session = QuerySession()
    repo = InventoryRepository(session)
    for resource_id in (None, uuid4()):
        await repo.transactions(resource_id, store_id=SHOP_A)
        await repo.ledger(resource_id, store_id=SHOP_A)
    assert all("store_id =" in sql for sql in session.queries)
    assert all("inventory_id =" in sql for sql in session.queries[2:])


@pytest.mark.asyncio
async def test_invoice_and_return_lists_apply_shop_filter():
    session = QuerySession()
    await InvoiceRepository(session).list(store_id=SHOP_A)
    await ReturnRepository(session).list(store_id=SHOP_A)
    assert all("invoices.store_id =" in sql for sql in session.queries)


@pytest.mark.asyncio
@pytest.mark.parametrize("route", [
    "/api/v1/products", "/api/v1/warehouses", "/api/v1/inventory/alerts",
    "/api/v1/payments", "/api/v1/refunds", "/api/v1/billing/reports/payments",
    "/api/v1/dashboard/{section}", "/api/v1/customers", "/api/v1/communications/whatsapp/settings",
    "/api/v1/sales-returns", "/api/v1/stock-adjustments", "/api/v1/inventory/export",
])
async def test_sales_legacy_or_global_routes_fail_closed(route):
    with pytest.raises(AuthorizationError):
        await require_permission("inventory.read")(actor("SALES", SHOP_A), request("GET", route))


@pytest.mark.asyncio
@pytest.mark.parametrize("route", [
    "/api/v1/inventory", "/api/v1/inventory/{id}", "/api/v1/inventory/transactions",
    "/api/v1/inventory/ledger", "/api/v1/billing/products", "/api/v1/invoices",
    "/api/v1/invoices/{id}/pdf", "/api/v1/invoices/{id}/history",
    "/api/v1/billing/reports/sales", "/api/v1/billing/reports/returns", "/api/v1/cash-register",
])
async def test_sales_shop_workflow_routes_remain_permitted(route):
    await require_permission("inventory.read")(actor("SALES", SHOP_A), request("GET", route))
    await require_permission("inventory.read")(actor("SALES", SHOP_B), request("GET", route))


@pytest.mark.asyncio
async def test_owner_manager_not_accidentally_restricted_by_sales_route_policy():
    for role in ("OWNER", "MANAGER"):
        await require_permission("inventory.read")(actor(role), request("GET", "/api/v1/warehouses"))
        await require_permission("inventory.read")(actor(role), request("GET", "/api/v1/products"))


@pytest.mark.asyncio
async def test_sales_generic_report_rejects_finance_query_manipulation():
    validator = require_permission("billing.read")
    await validator(actor("SALES", SHOP_A), request("GET", "/api/v1/reports/{domain}/{report}", domain="sales"))
    with pytest.raises(AuthorizationError):
        await validator(actor("SALES", SHOP_A), request("GET", "/api/v1/reports/{domain}/{report}", domain="finance"))


def test_every_registered_permission_route_defaults_to_sales_denied():
    registered = {(method, route.path) for route in app.routes if isinstance(route, APIRoute)
                  for method in route.methods}
    assert SALES_ROUTES <= registered
    sales = actor("SALES", SHOP_A)
    for method, path in registered:
        if path.startswith("/api/v1/auth/") or path.startswith("/api/v1/communications/whatsapp/webhook") or path.endswith("/health"):
            continue  # public/self routes have separate authentication rules
        assert _sales_route_allowed(sales, request(method, path, domain="sales")) == ((method, path) in SALES_ROUTES)
