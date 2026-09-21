"""Create the clean ANICRAZE pre-production baseline in the isolated demo DB.

This utility deliberately works only against the database named
``anicraze_demo`` while the application environment is ``demo``. It uses
ordinary DELETE statements inside one transaction, never drops schema objects,
never resets Alembic, and never changes users or passwords.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Iterable

from sqlalchemy import text

from app.config.settings import get_settings
from app.database.session import AsyncSessionFactory

EXPECTED_DATABASE = "anicraze_demo"
CONFIRMATION = "REMOVE-DEMO-OPERATIONAL-DATA"
FINAL_STORE_CODES = ("ELPRO", "WESTEND", "CIVIL", "SWARGATE", "KALYANI", "SHIVAJI", "EVENT1", "EVENT2")

# Child-first order. Configuration/master tables are intentionally absent.
OPERATIONAL_TABLES = (
    "report_delivery_attempts", "report_export_history", "business_targets",
    "notifications", "customer_communications", "store_credit_ledger",
    "customer_memberships", "loyalty_transactions", "loyalty_accounts",
    "customer_notes", "customer_addresses", "customer_profiles",
    "refunds", "return_items", "returns", "invoice_taxes", "invoice_discounts",
    "payments", "invoice_items", "invoices", "cash_register", "customers",
    "purchase_return_items", "purchase_returns", "supplier_payments",
    "supplier_invoice_items", "supplier_invoices", "landed_cost_allocations",
    "landed_cost_components", "landed_cost_documents", "grn_items",
    "goods_received_notes", "purchase_order_items", "purchase_orders",
    "purchase_request_items", "purchase_requests", "payment_reminders",
    "purchase_payment_transactions", "purchase_payables",
    "stock_receipt_items", "stock_receipts", "stock_reservations",
    "stock_transfer_items", "stock_transfers", "stock_adjustment_items",
    "stock_adjustments", "inventory_alerts", "inventory_ledger",
    "inventory_transactions", "purchase_return_items", "store_inventory",
    "warehouse_inventory", "inventory", "expenses",
    "refresh_tokens", "password_reset_tokens",
)

TEST_PRODUCT_NAMES = ("Test Product", "Workflow Test Product", "Demo Product")
TEST_SUPPLIER_PATTERNS = ("%test supplier%", "%demo supplier%", "%workflow supplier%")
OPERATIONAL_AUDIT_PREFIXES = (
    "INVENTORY_", "STOCK_RECEIPT_", "TRANSFER_", "INVOICE_", "SALE_",
    "RETURN_", "REFUND_", "PAYMENT_", "PURCHASE_", "REPORT_",
    "PRODUCT_BARCODE_",
)


async def existing_tables(session) -> set[str]:
    result = await session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
    return {row[0] for row in result}


async def scalar(session, sql: str, values: dict | None = None) -> int | str:
    return (await session.execute(text(sql), values or {})).scalar_one()


async def counts(session, tables: Iterable[str]) -> dict[str, int]:
    present = await existing_tables(session)
    output: dict[str, int] = {}
    for table in tables:
        if table in present:
            output[table] = int(await scalar(session, f'SELECT count(*) FROM "{table}"'))
    return output


async def snapshot(session) -> dict[str, object]:
    present = await existing_tables(session)
    inventory = {"rows": 0, "available": 0, "reserved": 0, "damaged": 0}
    if "inventory" in present:
        row = (await session.execute(text("""
            SELECT count(*), coalesce(sum(available_quantity),0),
                   coalesce(sum(reserved_quantity),0), coalesce(sum(damaged_quantity),0)
            FROM inventory WHERE deleted_at IS NULL
        """))).one()
        inventory = dict(zip(inventory, map(int, row), strict=True))
    return {
        "database": await scalar(session, "SELECT current_database()"),
        "alembic": await scalar(session, "SELECT version_num FROM alembic_version"),
        "users": int(await scalar(session, "SELECT count(*) FROM users WHERE deleted_at IS NULL")),
        "roles": int(await scalar(session, "SELECT count(*) FROM roles")),
        "permissions": int(await scalar(session, "SELECT count(*) FROM permissions")),
        "active_final_stores": int(await scalar(session, "SELECT count(*) FROM stores WHERE deleted_at IS NULL AND status='ACTIVE' AND code = ANY(:codes)", {"codes": list(FINAL_STORE_CODES)})),
        "warehouses": int(await scalar(session, "SELECT count(*) FROM warehouses WHERE deleted_at IS NULL")),
        "products": int(await scalar(session, "SELECT count(*) FROM products WHERE deleted_at IS NULL")),
        "client_catalog_products": int(await scalar(session, "SELECT count(*) FROM products WHERE deleted_at IS NULL AND import_reference IS NOT NULL")),
        "test_products": int(await scalar(session, "SELECT count(*) FROM products WHERE deleted_at IS NULL AND name = ANY(:names)", {"names": list(TEST_PRODUCT_NAMES)})),
        "suppliers": int(await scalar(session, "SELECT count(*) FROM suppliers WHERE deleted_at IS NULL")) if "suppliers" in present else 0,
        "customers": int(await scalar(session, "SELECT count(*) FROM customers WHERE deleted_at IS NULL")) if "customers" in present else 0,
        "inventory": inventory,
        "operational": await counts(session, OPERATIONAL_TABLES),
    }


async def delete_rows(session, table: str) -> int:
    result = await session.execute(text(f'DELETE FROM "{table}"'))
    return int(result.rowcount or 0)


async def cleanup(execute: bool, confirmation: str | None) -> dict[str, object]:
    settings = get_settings()
    if settings.environment != "demo":
        raise RuntimeError("Cleanup refused: application environment must be demo")
    if execute and confirmation != CONFIRMATION:
        raise RuntimeError(f"Cleanup refused: pass --confirm {CONFIRMATION}")

    async with AsyncSessionFactory() as session:
        await session.execute(text("SELECT pg_advisory_xact_lock(1602029)"))
        database = str(await scalar(session, "SELECT current_database()"))
        if database != EXPECTED_DATABASE:
            raise RuntimeError(f"Cleanup refused: expected database {EXPECTED_DATABASE}, connected to {database}")
        before = await snapshot(session)
        if not execute:
            await session.rollback()
            return {"mode": "dry-run", "before": before, "confirmation_required": CONFIRMATION}

        present = await existing_tables(session)
        removed: dict[str, int] = {}
        for table in dict.fromkeys(OPERATIONAL_TABLES):
            if table in present:
                removed[table] = await delete_rows(session, table)

        # Delete only unmistakable test suppliers; genuine supplier masters remain.
        if "suppliers" in present:
            supplier_filter = " OR ".join("lower(company_name || ' ' || display_name) LIKE :supplier_%d" % index for index, _ in enumerate(TEST_SUPPLIER_PATTERNS))
            values = {"supplier_%d" % index: value for index, value in enumerate(TEST_SUPPLIER_PATTERNS)}
            result = await session.execute(text(f"DELETE FROM suppliers WHERE {supplier_filter}"), values)
            removed["test_suppliers"] = int(result.rowcount or 0)

        # Product rows imported from the approved final catalogue are retained.
        test_ids = [row[0] for row in (await session.execute(text("SELECT id FROM products WHERE import_reference IS NULL AND name = ANY(:names)"), {"names": list(TEST_PRODUCT_NAMES)})).all()]
        if test_ids:
            for table in ("product_images", "product_variants"):
                if table in present:
                    result = await session.execute(text(f"DELETE FROM {table} WHERE product_id = ANY(:ids)"), {"ids": test_ids})
                    removed[f"test_{table}"] = int(result.rowcount or 0)
            result = await session.execute(text("DELETE FROM products WHERE id = ANY(:ids)"), {"ids": test_ids})
            removed["test_products"] = int(result.rowcount or 0)
        else:
            removed["test_products"] = 0

        # Remove the already-retired demo location, retaining the eight final IDs.
        result = await session.execute(text("DELETE FROM stores WHERE code='DEMO_SHOP' AND deleted_at IS NOT NULL"))
        removed["retired_demo_store"] = int(result.rowcount or 0)

        # Preserve security/account/RBAC audits; remove operational demo history.
        conditions = " OR ".join("action LIKE :audit_%d" % index for index, _ in enumerate(OPERATIONAL_AUDIT_PREFIXES))
        values = {"audit_%d" % index: value + "%" for index, value in enumerate(OPERATIONAL_AUDIT_PREFIXES)}
        result = await session.execute(text(f"DELETE FROM audit_logs WHERE {conditions} OR action='PRODUCT_CREATED'"), values)
        removed["operational_audit_logs"] = int(result.rowcount or 0)

        after = await snapshot(session)
        expected_zero = after["inventory"] == {"rows": 0, "available": 0, "reserved": 0, "damaged": 0}
        operational_zero = all(value == 0 for key, value in after["operational"].items() if key not in {"refresh_tokens", "password_reset_tokens"})
        verified = (
            after["database"] == EXPECTED_DATABASE
            and after["users"] == before["users"] == 3
            and after["active_final_stores"] == 8
            and after["warehouses"] == 1
            and after["client_catalog_products"] == 160
            and after["products"] == 160
            and expected_zero and operational_zero
        )
        if not verified:
            await session.rollback()
            raise RuntimeError("Post-cleanup verification failed; transaction rolled back")
        await session.commit()
        return {"mode": "execute", "before": before, "removed": removed, "after": after, "verified": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    if args.dry_run == args.execute:
        parser.error("choose exactly one of --dry-run or --execute")
    print(json.dumps(asyncio.run(cleanup(args.execute, args.confirm)), indent=2, default=str))


if __name__ == "__main__":
    main()
