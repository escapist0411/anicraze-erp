"""Seed the isolated online demo without creating transaction history or stock."""

import asyncio
import json
import os

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.auth.passwords import hash_password
from app.config.settings import get_settings
from app.database.session import AsyncSessionFactory
from app.models.auth import User, UserStatus, user_roles
from app.models.catalog import Product, ProductStatus
from app.models.inventory import Inventory, LocationStatus, LocationType, Store, StoreInventory, Warehouse, WarehouseInventory
from app.scripts.import_final_catalog import import_catalog
from app.scripts.seed_owner import seed_rbac

DEMO_STORES = (
    ("ELPRO", "ANICRAZE Elpro City Square Mall", "Elpro Chinchwad", "Elpro City Square Mall,\nChinchwad Gaon,\nChinchwad,\nPune,\nPimpri-Chinchwad,\nMaharashtra 411033", LocationType.PERMANENT_STORE),
    ("WESTEND", "ANICRAZE Westend Mall", "Westend Mall", "Ground Floor,\nWESTEND MALL,\nWard No. 8,\nWireless Colony,\nAundh,\nPune,\nMaharashtra 411067", LocationType.PERMANENT_STORE),
    ("CIVIL", "ANICRAZE Civil Court Metro Station", "Civil Court Metro", "Civil Court Metro Station,\nPune,\nMaharashtra", LocationType.PERMANENT_STORE),
    ("SWARGATE", "ANICRAZE Swargate Metro Station", "Swargate Metro", "Swargate Metro Station,\nPune,\nMaharashtra", LocationType.PERMANENT_STORE),
    ("KALYANI", "ANICRAZE Kalyani Nagar Metro Station", "Kalyani Nagar Metro", "Kalyani Nagar Metro Station,\nPune,\nMaharashtra", LocationType.PERMANENT_STORE),
    ("SHIVAJI", "ANICRAZE Shivaji Nagar Metro Station", "Shivaji Nagar Metro", "Shivaji Nagar Metro Station,\nPune,\nMaharashtra", LocationType.PERMANENT_STORE),
    ("EVENT1", "ANICRAZE Event 1", "Event 1", None, LocationType.EVENT_LOCATION),
    ("EVENT2", "ANICRAZE Event 2", "Event 2", None, LocationType.EVENT_LOCATION),
)
DEMO_WAREHOUSE_CODE = "ANICRAZE_CWH"
SELECTED_PRODUCTS = (
    "Naruto Rasengan", "Kakashi Chidori", "Tanjiro Standing", "Luffy Sitting — Variant 1",
    "Gojo Standing — Variant 1", "Qposket Elsa", "Rubber Keychain", "UNO No Mercy", "Katana",
)
USERS = (
    ("owner.demo@anicraze.in", "ANICRAZE Demo Owner", "OWNER", "DEMO_OWNER_PASSWORD", None),
    ("employee.demo@anicraze.in", "ANICRAZE Demo Employee", "SALES", "DEMO_EMPLOYEE_PASSWORD", "DEMO-EMP-001"),
    ("manager.demo@anicraze.in", "ANICRAZE Demo Store Manager", "MANAGER", "DEMO_MANAGER_PASSWORD", "DEMO-MGR-001"),
)


def require_demo() -> None:
    if get_settings().environment != "demo":
        raise RuntimeError("Demo seed refused: APP_ENV/ENVIRONMENT must be 'demo'")


def password(name: str) -> str:
    value = os.environ.get(name, "")
    if len(value) < 12:
        raise RuntimeError(f"{name} must be configured with at least 12 characters")
    return value


async def seed_demo() -> dict[str, object]:
    require_demo()
    credentials = {name: password(name) for _, _, _, name, _ in USERS}
    # Uses the same final CSV and idempotent catalog importer as every environment.
    await import_catalog()
    async with AsyncSessionFactory() as session:
        await session.execute(text("SELECT pg_advisory_xact_lock(1602027)"))
        roles = await seed_rbac(session)
        stores=[]
        for code,name,short_name,address,kind in DEMO_STORES:
            store=await session.scalar(select(Store).where(Store.code==code))
            if store is None:store=Store(code=code,name=name,short_name=short_name,location_type=kind,address=address,status=LocationStatus.ACTIVE);session.add(store);await session.flush()
            else:store.name,store.short_name,store.address,store.location_type,store.status,store.deleted_at=name,short_name,address,kind,LocationStatus.ACTIVE,None
            stores.append(store)
        store=stores[0]
        warehouse = await session.scalar(select(Warehouse).where(Warehouse.code == DEMO_WAREHOUSE_CODE))
        if warehouse is None:
            warehouse = Warehouse(code=DEMO_WAREHOUSE_CODE, name="ANICRAZE Central Warehouse", address="Demo environment only", status=LocationStatus.ACTIVE)
            session.add(warehouse); await session.flush()
        else:
            warehouse.name, warehouse.status, warehouse.deleted_at = "ANICRAZE Central Warehouse", LocationStatus.ACTIVE, None

        seeded_users = []
        for email, full_name, role_code, variable, employee_code in USERS:
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, full_name=full_name, password_hash=hash_password(credentials[variable]))
                session.add(user); await session.flush()
            else:
                user.full_name, user.password_hash = full_name, hash_password(credentials[variable])
            user.status, user.is_active, user.deleted_at = UserStatus.ACTIVE, True, None
            user.assigned_store_id = store.id if role_code != "OWNER" else None
            user.employee_code = "EMP-ELPRO-001" if role_code == "SALES" else employee_code
            user.must_change_password = False
            await session.execute(insert(user_roles).values(user_id=user.id, role_id=roles[role_code].id).on_conflict_do_nothing())
            seeded_users.append(email)

        products = list((await session.scalars(select(Product).where(Product.name.in_(SELECTED_PRODUCTS), Product.deleted_at.is_(None), Product.status == ProductStatus.ACTIVE))).all())
        if {product.name for product in products} != set(SELECTED_PRODUCTS):
            missing = sorted(set(SELECTED_PRODUCTS) - {product.name for product in products})
            raise RuntimeError(f"Final catalog is missing selected demo products: {missing}")
        inventory_rows = 0
        for product in products:
            for location_type, location_id in (("store", store.id), ("warehouse", warehouse.id)):
                query = select(Inventory).where(Inventory.product_id == product.id, Inventory.variant_id.is_(None))
                query = query.where(Inventory.store_id == location_id) if location_type == "store" else query.where(Inventory.warehouse_id == location_id)
                inventory = await session.scalar(query)
                if inventory is None:
                    inventory = Inventory(product_id=product.id, store_id=location_id if location_type == "store" else None, warehouse_id=location_id if location_type == "warehouse" else None, available_quantity=0, reserved_quantity=0, damaged_quantity=0, minimum_stock=0, maximum_stock=None, reorder_level=0, average_cost=0, last_purchase_cost=None, inventory_value=0)
                    session.add(inventory); await session.flush()
                    session.add(StoreInventory(inventory_id=inventory.id, store_id=store.id) if location_type == "store" else WarehouseInventory(inventory_id=inventory.id, warehouse_id=warehouse.id))
                inventory_rows += 1
        await session.commit()
        return {"users": seeded_users, "stores": [x.name for x in stores], "warehouse": warehouse.name, "selected_products": len(products), "zero_stock_inventory_rows": inventory_rows}


if __name__ == "__main__":
    require_demo()
    print(json.dumps(asyncio.run(seed_demo()), indent=2))
