"""HTTP-level multi-shop checks, opt-in only for a verified throwaway database."""

import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from fastapi import Request
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import selectinload

from app.config.settings import get_settings
from app.database.session import AsyncSessionFactory
from app.dependencies.auth import get_current_user
from app.main import app
from app.models.auth import AuditLog, Role, User
from app.models.billing import CashRegister, Invoice, InvoiceStatus, PaymentStatus, RegisterStatus, Return, ReturnStatus
from app.models.catalog import Product
from app.models.inventory import Inventory, Store, Warehouse
from app.scripts.import_final_catalog import import_catalog
from app.storage import DocumentStorage


@pytest.mark.asyncio
async def test_two_shop_http_authorization_on_isolated_database():
    configured = make_url(get_settings().database_url).database
    if os.environ.get("ANICRAZE_PHASE3_ISOLATED") != "yes" or configured != "anicraze_phase3_test":
        pytest.skip("Isolated local PostgreSQL opt-in is required")
    async with AsyncSessionFactory() as session:
        if await session.scalar(text("SELECT current_database()")) != "anicraze_phase3_test":
            pytest.fail("Refusing to write test fixtures to an unverified database")

    await import_catalog()
    async with AsyncSessionFactory() as session:
        stores = {s.code: s for s in (await session.scalars(select(Store))).all()}
        users = {u.email: u for u in (await session.scalars(select(User).options(
            selectinload(User.roles).selectinload(Role.permissions), selectinload(User.direct_permissions)
        ))).all()}
        product = await session.scalar(select(Product).where(
            ~select(Inventory.id).where(Inventory.product_id == Product.id).exists()
        ).order_by(Product.name).limit(1))
        if product is None:
            pytest.fail("No unused isolated product remains for this rehearsal")
        warehouse = await session.scalar(select(Warehouse).limit(1))
        fixtures = {}
        for code, email in (("ELPRO", "elpro@anicraze.in"), ("WESTEND", "westend@anicraze.in")):
            inv = Inventory(product_id=product.id, store_id=stores[code].id,
                            available_quantity=10, reserved_quantity=0, damaged_quantity=0,
                            minimum_stock=0, reorder_level=0, average_cost=Decimal("100"),
                            inventory_value=Decimal("1000"))
            session.add(inv)
            invoice = Invoice(invoice_number=f"TEST-{code}-{uuid4().hex[:8]}", idempotency_key=uuid4().hex,
                              store_id=stores[code].id, employee_id=users[email].id,
                              customer_name_snapshot="Isolated Test", subtotal=Decimal("100"),
                              discount=Decimal("0"), taxable_amount=Decimal("100"),
                              grand_total=Decimal("100"), payment_status=PaymentStatus.PAID,
                              invoice_status=InvoiceStatus.COMPLETED)
            session.add(invoice)
            await session.flush()
            invoice.pdf_path = str(DocumentStorage().save("invoices", f"{invoice.invoice_number}.pdf", b"%PDF-1.4\n%%EOF\n"))
            session.add(Return(return_number=f"RET-{code}-{uuid4().hex[:8]}", invoice_id=invoice.id,
                               reason="Isolated test", total_amount=Decimal("20"), status=ReturnStatus.COMPLETED))
            session.add(CashRegister(store_id=stores[code].id, employee_id=users[email].id,
                                     opening_balance=Decimal("0"), cash_sales=Decimal("100"),
                                     cash_refunds=Decimal("0"), status=RegisterStatus.OPEN))
            session.add(AuditLog(actor_user_id=users[email].id, action="TEST_INVOICE", entity_type="invoice",
                                 entity_id=invoice.id, metadata_json={"isolated": True},
                                 created_at=datetime.now(timezone.utc)))
            fixtures[code] = (inv.id, invoice.id)
        warehouse_inv = Inventory(product_id=product.id, warehouse_id=warehouse.id,
                                  available_quantity=10, reserved_quantity=0, damaged_quantity=0,
                                  minimum_stock=0, reorder_level=0, average_cost=Decimal("100"),
                                  inventory_value=Decimal("1000"))
        session.add(warehouse_inv)
        await session.commit()
        warehouse_id = warehouse_inv.id

    async def test_actor(request: Request):
        return users[request.headers.get("x-test-actor", "elpro@anicraze.in")]

    app.dependency_overrides[get_current_user] = test_actor
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://isolated.test") as client:
            async def get(path, email="elpro@anicraze.in"):
                return await client.get(path, headers={"x-test-actor": email})

            a_inv, a_invoice = fixtures["ELPRO"]
            b_inv, b_invoice = fixtures["WESTEND"]
            for own_inv, foreign_inv, own_invoice, foreign_invoice, email in (
                (a_inv, b_inv, a_invoice, b_invoice, "elpro@anicraze.in"),
                (b_inv, a_inv, b_invoice, a_invoice, "westend@anicraze.in"),
            ):
                assert (await get(f"/api/v1/inventory/{own_inv}", email)).status_code == 200
                assert (await get(f"/api/v1/inventory/{foreign_inv}", email)).status_code in (403, 404)
                assert (await get(f"/api/v1/inventory/{warehouse_id}", email)).status_code in (403, 404)
                for base in ("inventory/transactions", "inventory/ledger"):
                    own = await get(f"/api/v1/{base}?inventory_id={own_inv}", email)
                    foreign = await get(f"/api/v1/{base}?inventory_id={foreign_inv}", email)
                    assert own.status_code == 200 and foreign.status_code in (403, 404)
                assert (await get(f"/api/v1/invoices/{own_invoice}/history", email)).status_code == 200
                assert (await get(f"/api/v1/invoices/{foreign_invoice}/history", email)).status_code in (403, 404)
                assert (await get(f"/api/v1/invoices/{foreign_invoice}/pdf", email)).status_code in (403, 404)
                assert (await get(f"/api/v1/invoices/{own_invoice}/pdf", email)).status_code == 200
                assert (await get(f"/api/v1/invoices/{own_invoice}", email)).status_code == 200
                assert (await get(f"/api/v1/invoices/{foreign_invoice}", email)).status_code in (403, 404)
                assert (await get(f"/api/v1/billing/products?store_id={stores['WESTEND' if email.startswith('elpro') else 'ELPRO'].id}", email)).status_code in (403, 404)
                foreign_store = stores["WESTEND" if email.startswith("elpro") else "ELPRO"].id
                manipulated_bill = await client.post("/api/v1/billing", headers={"x-test-actor": email}, json={
                    "idempotency_key": uuid4().hex,
                    "store_id": str(foreign_store),
                    "items": [{"inventory_id": str(own_inv), "quantity": 1}],
                    "payments": [{"method": "CASH", "amount": "100"}],
                })
                assert manipulated_bill.status_code == 403
                assert (await client.post("/api/v1/stock-transfers/direct", headers={"x-test-actor": email}, json={
                    "destination_store_id": str(foreign_store), "items": []
                })).status_code == 403
                assert (await get("/api/v1/warehouses", email)).status_code == 403
                assert (await get("/api/v1/products", email)).status_code == 403
                for path in ("billing/reports/sales", "billing/reports/returns", "returns", "cash-register", "billing/analytics"):
                    response = await get(f"/api/v1/{path}", email)
                    assert response.status_code == 200, (path, response.status_code, response.text[:200])
                    if path == "billing/reports/sales":
                        assert response.json()["data"] and all(row["store_id"] == str(stores["ELPRO" if email.startswith("elpro") else "WESTEND"].id) for row in response.json()["data"])
                    if path == "cash-register":
                        assert response.json()["data"] and all(row["store_id"] == str(stores["ELPRO" if email.startswith("elpro") else "WESTEND"].id) for row in response.json()["data"])
                assert (await get(f"/api/v1/reports/sales/summary?store_id={stores['WESTEND' if email.startswith('elpro') else 'ELPRO'].id}", email)).status_code == 403

            assert (await get(f"/api/v1/inventory/{b_inv}", "owner@anicraze.in")).status_code == 200
            assert (await get(f"/api/v1/inventory/{b_inv}", "manager@anicraze.in")).status_code == 200
            for financial_path in ("payments", "billing/reports/payments", "cash-register",
                                   "dashboard/owner", "reports/finance/summary", "purchase-payables"):
                assert (await get(f"/api/v1/{financial_path}", "manager@anicraze.in")).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
