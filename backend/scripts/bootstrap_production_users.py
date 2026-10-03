"""Provision only missing ANICRAZE production locations and accounts.

Run only after an explicit migration against an isolated, identity-verified
production database. Existing account credentials, roles and token versions
are never changed by this command.
"""

import asyncio
import os

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.auth.passwords import hash_password
from app.config.settings import get_settings
from app.database.session import AsyncSessionFactory
from app.models.auth import Role, User, UserStatus, user_roles
from app.models.inventory import LocationStatus, Store, Warehouse
from app.scripts.seed_demo import DEMO_STORES, DEMO_WAREHOUSE_CODE
from app.scripts.seed_owner import seed_rbac
from app.services.password_service import PasswordService

EXPECTED_REVISION = "20260921_0020"
ACCOUNTS = (
    ("owner@anicraze.in", "ANICRAZE Owner", "OWNER", None, "ANICRAZE_OWNER_PASSWORD"),
    ("manager@anicraze.in", "ANICRAZE Manager", "MANAGER", None, "ANICRAZE_MANAGER_PASSWORD"),
    ("elpro@anicraze.in", "ANICRAZE ELPRO", "SALES", "ELPRO", "ANICRAZE_ELPRO_PASSWORD"),
    ("westend@anicraze.in", "ANICRAZE WESTEND", "SALES", "WESTEND", "ANICRAZE_WESTEND_PASSWORD"),
    ("civil@anicraze.in", "ANICRAZE CIVIL", "SALES", "CIVIL", "ANICRAZE_CIVIL_PASSWORD"),
    ("swargate@anicraze.in", "ANICRAZE SWARGATE", "SALES", "SWARGATE", "ANICRAZE_SWARGATE_PASSWORD"),
    ("kalyani@anicraze.in", "ANICRAZE KALYANI", "SALES", "KALYANI", "ANICRAZE_KALYANI_PASSWORD"),
    ("shivaji@anicraze.in", "ANICRAZE SHIVAJI", "SALES", "SHIVAJI", "ANICRAZE_SHIVAJI_PASSWORD"),
    ("event.1@anicraze.in", "ANICRAZE EVENT 1", "SALES", "EVENT1", "ANICRAZE_EVENT1_PASSWORD"),
    ("event.2@anicraze.in", "ANICRAZE EVENT 2", "SALES", "EVENT2", "ANICRAZE_EVENT2_PASSWORD"),
)


def expected_database() -> str:
    settings = get_settings()
    name = os.environ.get("ANICRAZE_PRODUCTION_DATABASE", "").strip()
    confirmation = os.environ.get("ANICRAZE_CONFIRM_DATABASE", "").strip()
    configured = make_url(settings.database_url).database
    if settings.environment != "production":
        raise RuntimeError("Production bootstrap requires APP_ENV/ENVIRONMENT=production")
    if not name or name in {"anicraze_demo", "neondb"} or confirmation != name or configured != name:
        raise RuntimeError("Production bootstrap database identity or confirmation is invalid")
    return name


def password_for_new_user(variable: str, user: User) -> str:
    value = os.environ.get(variable, "")
    if len(value) < 12:
        raise RuntimeError(f"Missing or short password variable for new account: {variable}")
    PasswordService().validate_new_password(value, user)
    return value


async def bootstrap() -> dict[str, int]:
    expected = expected_database()  # fail before opening a write transaction
    async with AsyncSessionFactory() as session:
        actual = await session.scalar(text("SELECT current_database()"))
        if actual != expected:
            raise RuntimeError("Connected production database identity does not match confirmation")
        revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != EXPECTED_REVISION:
            raise RuntimeError("Production schema is not at the expected Alembic revision")
        await session.execute(text("SELECT pg_advisory_xact_lock(1602029)"))

        required_roles = {"OWNER", "MANAGER", "SALES"}
        role_rows = list((await session.scalars(select(Role))).all())
        if not role_rows:
            if (await session.scalar(select(User.id).limit(1))) is not None:
                raise RuntimeError("Users exist without a role catalog; manual review required")
            # A genuinely empty migrated database needs the initial permission
            # catalog. Never rewrite grants in an already provisioned database.
            roles = await seed_rbac(session)
        else:
            roles = {role.code: role for role in role_rows}
            if not required_roles.issubset(roles):
                raise RuntimeError("Existing role catalog is incomplete; manual review required")
        if any(not roles[code].is_active for code in required_roles):
            raise RuntimeError("A required role is inactive")

        approved_codes = {row[0] for row in DEMO_STORES}
        stores = {store.code: store for store in (await session.scalars(select(Store).where(Store.code.in_(approved_codes)))).all()}
        for code, name, short_name, address, kind in DEMO_STORES:
            existing = stores.get(code)
            if existing is not None:
                if existing.deleted_at or existing.status != LocationStatus.ACTIVE or existing.location_type != kind:
                    raise RuntimeError(f"Existing location {code} requires manual review")
                continue
            store = Store(code=code, name=name, short_name=short_name, address=address,
                          location_type=kind, status=LocationStatus.ACTIVE)
            session.add(store)
            await session.flush()
            stores[code] = store

        warehouse = await session.scalar(select(Warehouse).where(Warehouse.code == DEMO_WAREHOUSE_CODE))
        if warehouse is None:
            warehouse = Warehouse(code=DEMO_WAREHOUSE_CODE, name="ANICRAZE Central Warehouse",
                                  status=LocationStatus.ACTIVE)
            session.add(warehouse)
            await session.flush()
        elif warehouse.deleted_at or warehouse.status != LocationStatus.ACTIVE:
            raise RuntimeError("Existing Central Warehouse requires manual review")

        created = 0
        for email, name, role_code, store_code, variable in ACCOUNTS:
            user = await session.scalar(select(User).options(selectinload(User.roles)).where(User.email == email))
            store_id = stores[store_code].id if store_code else None
            if user is not None:
                if (user.deleted_at or user.status != UserStatus.ACTIVE or not user.is_active
                        or user.assigned_store_id != store_id
                        or {role.code for role in user.roles} != {role_code}):
                    raise RuntimeError(f"Existing account {email} requires manual review")
                continue
            employee_code = f"EMP-{store_code}-001" if store_code else None
            if employee_code and (await session.scalar(select(User.id).where(User.employee_code == employee_code))) is not None:
                raise RuntimeError(f"Employee code for {store_code} already exists; manual review required")
            new_user = User(email=email, full_name=name, password_hash="", assigned_store_id=store_id,
                            employee_code=employee_code,
                            status=UserStatus.ACTIVE, is_active=True, must_change_password=False)
            new_user.password_hash = hash_password(password_for_new_user(variable, new_user))
            session.add(new_user)
            await session.flush()
            await session.execute(insert(user_roles).values(user_id=new_user.id, role_id=roles[role_code].id))
            created += 1
        await session.commit()
        return {"accounts_created": created, "accounts_verified": len(ACCOUNTS) - created,
                "stores_present": len(stores), "warehouses_present": 1}


if __name__ == "__main__":
    print(asyncio.run(bootstrap()))
