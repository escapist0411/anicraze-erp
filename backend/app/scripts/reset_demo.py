"""Reset only the isolated demo's operational state; refuses every other environment."""

import asyncio
import json

from sqlalchemy import text

from app.config.settings import get_settings
from app.database.session import AsyncSessionFactory
from app.scripts.seed_demo import seed_demo

TRANSACTION_TABLES = (
    "report_delivery_attempts", "report_export_history", "notifications", "audit_logs",
    "customer_communications", "store_credit_ledger", "customer_memberships", "loyalty_transactions",
    "loyalty_accounts", "customer_notes", "customer_addresses", "customer_profiles", "customers",
    "refunds", "return_items", "returns", "invoice_taxes", "invoice_discounts", "payments", "invoice_items", "invoices", "cash_register",
    "purchase_return_items", "purchase_returns", "supplier_payments", "supplier_invoice_items", "supplier_invoices",
    "landed_cost_allocations", "landed_cost_components", "landed_cost_documents", "grn_items", "goods_received_notes",
    "purchase_order_items", "purchase_orders", "purchase_request_items", "purchase_requests", "supplier_addresses", "supplier_contacts", "suppliers",
    "stock_receipt_items", "stock_receipts", "stock_reservations", "stock_transfer_items", "stock_transfers", "stock_adjustment_items", "stock_adjustments",
    "inventory_alerts", "inventory_ledger", "inventory_transactions", "refresh_tokens", "password_reset_tokens",
)


async def reset_demo() -> dict[str, object]:
    if get_settings().environment != "demo":
        raise RuntimeError("Demo reset refused: APP_ENV/ENVIRONMENT must be 'demo'")
    async with AsyncSessionFactory() as session:
        await session.execute(text("SELECT pg_advisory_xact_lock(1602028)"))
        quoted = ", ".join(f'"{table}"' for table in TRANSACTION_TABLES)
        await session.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
        await session.execute(text("UPDATE inventory SET available_quantity=0, reserved_quantity=0, damaged_quantity=0, average_cost=0, last_purchase_cost=NULL, inventory_value=0, last_movement_at=NULL"))
        await session.execute(text("UPDATE invoice_sequence SET current_value=0"))
        await session.execute(text("UPDATE procurement_sequences SET current_value=0"))
        await session.commit()
    seeded = await seed_demo()
    return {"reset": True, "inventory": "zero", "seed": seeded}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(reset_demo()), indent=2))
