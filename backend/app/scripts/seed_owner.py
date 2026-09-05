import asyncio
import os

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.auth.passwords import hash_password
from app.database.session import AsyncSessionFactory
from app.models.auth import Permission, Role, RoleName, User, role_permissions, user_roles

ROLE_DESCRIPTIONS = {
    RoleName.OWNER: "Full enterprise authority",
    RoleName.ADMIN: "Platform administration authority",
    RoleName.MANAGER: "Store and operational management",
    RoleName.ACCOUNTANT: "Financial operations",
    RoleName.SALES: "Sales and billing operations",
    RoleName.INVENTORY: "Inventory and warehouse operations",
    RoleName.HR: "Human resources operations",
    RoleName.EMPLOYEE: "Standard employee access",
}
ROLE_DESCRIPTIONS = {role.value: description for role, description in ROLE_DESCRIPTIONS.items()}
PERMISSIONS = ["*", "dashboard.read", "users.read", "users.create", "users.update", "users.delete", "users.assign_roles", "users.assign_permissions", "users.manage_status", "users.reset_password", "users.manage_sessions", "roles.read", "roles.create", "roles.update", "roles.delete", "roles.assign_permissions", "permissions.read", "permissions.create", "permissions.update", "permissions.delete", "products.read", "products.create", "products.update", "products.delete", "products.update_status", "products.read_history", "products.import", "products.export", "products.manage_images", "products.manage_barcode", "categories.read", "categories.create", "categories.update", "categories.delete", "brands.read", "brands.create", "brands.update", "brands.delete", "anime.read", "anime.create", "anime.update", "anime.delete", "characters.read", "characters.create", "characters.update", "characters.delete", "inventory.read", "inventory.adjust", "inventory.transfer", "billing.read", "billing.create", "billing.refund", "customers.read", "customers.create", "customers.update", "employees.read", "employees.manage", "reports.read", "reports.export", "settings.manage", "stores.read", "finance.read", "finance.update", "gst.read", "expenses.manage", "purchases.read", "suppliers.read", "attendance.manage", "leave.manage", "payroll.read", "profile.read", "profile.update", "attendance.self", "tasks.self"]
MATRIX = {
    "OWNER": ["*"],
    "ADMIN": [p for p in PERMISSIONS if p != "*"],
    "MANAGER": ["dashboard.read", "products.read", "products.create", "products.update", "categories.read", "brands.read", "anime.read", "characters.read", "inventory.read", "inventory.adjust", "inventory.transfer", "billing.read", "reports.read", "employees.read", "stores.read"],
    "ACCOUNTANT": ["products.read", "categories.read", "finance.read", "finance.update", "billing.read", "reports.read", "reports.export", "gst.read", "expenses.manage"],
    "INVENTORY": ["products.read", "products.create", "products.update", "products.update_status", "products.import", "products.export", "products.manage_images", "products.manage_barcode", "categories.read", "brands.read", "anime.read", "characters.read", "inventory.read", "inventory.adjust", "inventory.transfer", "purchases.read", "suppliers.read"],
    "SALES": ["products.read", "categories.read", "brands.read", "anime.read", "characters.read", "inventory.read", "billing.create", "billing.read", "customers.read", "customers.create", "customers.update"],
    "HR": ["employees.read", "employees.manage", "attendance.manage", "leave.manage", "payroll.read"],
    "EMPLOYEE": ["profile.read", "profile.update", "attendance.self", "tasks.self"],
}
DEMOS = [
    ("owner@anicraze.com", "ANICRAZE Owner", "LOCAL_OWNER_PASSWORD", "OWNER"),
    ("manager@anicraze.com", "Demo Manager", "LOCAL_MANAGER_PASSWORD", "MANAGER"),
    ("accountant@anicraze.com", "Demo Accountant", "LOCAL_ACCOUNTANT_PASSWORD", "ACCOUNTANT"),
    ("inventory@anicraze.com", "Demo Warehouse", "LOCAL_INVENTORY_PASSWORD", "INVENTORY"),
    ("sales@anicraze.com", "Demo Billing", "LOCAL_SALES_PASSWORD", "SALES"),
    ("hr@anicraze.com", "Demo HR", "LOCAL_HR_PASSWORD", "HR"),
]

INVENTORY_PERMISSIONS = ["inventory.create", "inventory.update", "inventory.delete", "inventory.analytics"]
PERMISSIONS.extend(INVENTORY_PERMISSIONS)
MATRIX["ADMIN"].extend(INVENTORY_PERMISSIONS)
MATRIX["MANAGER"].extend(["inventory.create", "inventory.update", "inventory.analytics"])
MATRIX["INVENTORY"].extend(INVENTORY_PERMISSIONS)
MATRIX["ACCOUNTANT"].extend(["inventory.read", "inventory.analytics"])

BILLING_PERMISSIONS = ["billing.update", "billing.cancel", "billing.return", "billing.refund", "billing.pdf", "payments.read", "payments.create", "payments.refund"]
PERMISSIONS.extend(BILLING_PERMISSIONS)
MATRIX["ADMIN"].extend(BILLING_PERMISSIONS)
MATRIX["MANAGER"].extend(BILLING_PERMISSIONS)
MATRIX["SALES"].extend(["billing.update", "billing.cancel", "billing.return", "billing.pdf", "payments.read", "payments.create"])
MATRIX["ACCOUNTANT"].extend(["billing.read", "billing.refund", "billing.pdf", "payments.read", "payments.refund"])

PROCUREMENT_PERMISSIONS = [
    "suppliers.read", "suppliers.create", "suppliers.update", "suppliers.delete", "suppliers.view_statement", "suppliers.view_performance",
    "purchase_requests.read", "purchase_requests.create", "purchase_requests.update", "purchase_requests.delete", "purchase_requests.submit", "purchase_requests.approve", "purchase_requests.reject", "purchase_requests.convert",
    "purchase_orders.read", "purchase_orders.create", "purchase_orders.update", "purchase_orders.delete", "purchase_orders.submit", "purchase_orders.approve", "purchase_orders.reject", "purchase_orders.send", "purchase_orders.confirm", "purchase_orders.cancel", "purchase_orders.close", "purchase_orders.pdf",
    "grn.read", "grn.create", "grn.update", "grn.submit", "grn.complete", "grn.cancel", "grn.pdf",
    "supplier_invoices.read", "supplier_invoices.create", "supplier_invoices.update", "supplier_invoices.approve", "supplier_invoices.cancel", "supplier_invoices.pdf",
    "supplier_payments.read", "supplier_payments.create", "supplier_payments.reverse", "supplier_payments.receipt",
    "purchase_returns.read", "purchase_returns.create", "purchase_returns.update", "purchase_returns.approve", "purchase_returns.dispatch", "purchase_returns.complete", "purchase_returns.cancel", "purchase_returns.pdf", "procurement.analytics",
]
PERMISSIONS.extend(PROCUREMENT_PERMISSIONS)
MATRIX["ADMIN"].extend(PROCUREMENT_PERMISSIONS)
MATRIX["MANAGER"].extend(["suppliers.read", "purchase_requests.read", "purchase_requests.create", "purchase_requests.submit", "purchase_orders.read", "grn.read", "procurement.analytics"])
MATRIX["INVENTORY"].extend(["suppliers.read", "purchase_orders.read", "grn.read", "grn.create", "grn.submit", "grn.complete", "grn.pdf", "purchase_returns.read", "purchase_returns.create", "purchase_returns.dispatch", "purchase_returns.complete", "procurement.analytics"])
MATRIX["ACCOUNTANT"].extend(["suppliers.read", "suppliers.view_statement", "purchase_orders.read", "grn.read", "supplier_invoices.read", "supplier_invoices.create", "supplier_invoices.approve", "supplier_invoices.pdf", "supplier_payments.read", "supplier_payments.create", "supplier_payments.reverse", "supplier_payments.receipt", "procurement.analytics"])

CRM_PERMISSIONS = ["customers.update_status","customers.view_statement","customers.view_analytics","customers.manage_tags","customers.manage_segments","customers.manage_notes","loyalty.read","loyalty.configure","loyalty.adjust","loyalty.redeem","loyalty.reverse","loyalty.view_transactions","memberships.read","memberships.create","memberships.update","memberships.delete","memberships.assign","memberships.evaluate","memberships.analytics","customer_communications.read","customer_communications.create","customer_communications.update","customer_communications.delete","sales_returns.read","sales_returns.create","sales_returns.update","sales_returns.approve","sales_returns.receive","sales_returns.complete","sales_returns.cancel","sales_returns.pdf","customer_refunds.read","customer_refunds.create","customer_refunds.process","customer_refunds.reverse","customer_refunds.receipt","crm.analytics"]
PERMISSIONS.extend(CRM_PERMISSIONS)
MATRIX["ADMIN"].extend(CRM_PERMISSIONS)
MATRIX["MANAGER"].extend(["customers.update","customers.update_status","customers.view_analytics","customers.manage_notes","loyalty.read","memberships.read","sales_returns.read","sales_returns.approve","crm.analytics"])
MATRIX["SALES"].extend(["customers.update","loyalty.read","loyalty.redeem","memberships.read","customer_communications.read","customer_communications.create","sales_returns.read","sales_returns.create"])
MATRIX["ACCOUNTANT"].extend(["customers.view_statement","loyalty.read","sales_returns.read","customer_refunds.read","customer_refunds.process","customer_refunds.reverse","customer_refunds.receipt","crm.analytics"])
MATRIX["EMPLOYEE"].extend(["customers.read","customers.create"])

HR_PERMISSIONS=["employees.update_status","employees.link_user","employees.assign_store","employees.manage_documents","employees.view_sensitive","employees.view_history","departments.read","departments.create","departments.update","departments.delete","designations.read","designations.create","designations.update","designations.delete","attendance.read","attendance.check_in","attendance.check_out","attendance.correct","attendance.approve_correction","attendance.export","shifts.read","shifts.create","shifts.update","shifts.delete","shifts.assign","shifts.manage_roster","holidays.read","holidays.create","holidays.update","holidays.delete","leave.read","leave.self","leave.create","leave.update","leave.submit","leave.approve","leave.reject","leave.cancel","leave.manage_types","leave.manage_balances","payroll.view_self","payroll.manage_components","payroll.manage_structures","payroll.create_run","payroll.calculate","payroll.approve","payroll.finalize","payroll.cancel","payroll.payslip","performance.read","performance.create","performance.update","performance.submit","performance.approve","performance.manage_goals","performance.manage_tasks","hr.analytics"]
HR_PERMISSIONS.extend(["employees.create","employees.update","employees.delete"])
PERMISSIONS.extend(HR_PERMISSIONS);MATRIX["ADMIN"].extend(HR_PERMISSIONS);MATRIX["HR"].extend(HR_PERMISSIONS+["attendance.manage"])
MATRIX["MANAGER"].extend(["employees.read","attendance.read","shifts.read","shifts.assign","leave.read","leave.approve","leave.reject","performance.read","performance.manage_tasks"])
MATRIX["ACCOUNTANT"].extend(["employees.read","payroll.read","payroll.manage_components","payroll.manage_structures","payroll.create_run","payroll.calculate","payroll.approve","payroll.finalize","payroll.payslip"])
SELF_HR=["attendance.self","attendance.check_in","attendance.check_out","leave.self","leave.create","leave.submit","leave.cancel","payroll.view_self","performance.read"]
MATRIX["EMPLOYEE"].extend(SELF_HR);MATRIX["SALES"].extend(SELF_HR);MATRIX["INVENTORY"].extend(SELF_HR)

REPORT_PERMISSIONS=["dashboard.owner","dashboard.read","dashboard.read_all_stores","reports.sales.read","reports.sales.export","reports.inventory.read","reports.inventory.export","reports.finance.read","reports.finance.export","reports.gst.read","reports.gst.export","reports.purchases.read","reports.purchases.export","reports.customers.read","reports.customers.export","reports.employees.read","reports.employees.export","reports.payroll.read","reports.payroll.export","reports.stores.read","reports.stores.export","reports.warehouses.read","reports.warehouses.export","reports.payments.read","reports.payments.export","reports.returns.read","reports.returns.export","reports.loyalty.read","reports.loyalty.export","reports.schedules.read","reports.schedules.create","reports.schedules.update","reports.schedules.delete","reports.schedules.run","reports.targets.read","reports.targets.manage","expenses.read","expenses.create","expenses.update","expenses.delete","expenses.approve"]
PERMISSIONS.extend(REPORT_PERMISSIONS);MATRIX["ADMIN"].extend(REPORT_PERMISSIONS)
MATRIX["MANAGER"].extend(["dashboard.read","reports.sales.read","reports.sales.export","reports.inventory.read","reports.customers.read","reports.employees.read","reports.stores.read","reports.targets.read"])
MATRIX["ACCOUNTANT"].extend(["dashboard.read","reports.finance.read","reports.finance.export","reports.gst.read","reports.gst.export","reports.purchases.read","reports.purchases.export","reports.payroll.read","reports.payroll.export","reports.payments.read","reports.payments.export","reports.returns.read","reports.returns.export","reports.schedules.read","reports.schedules.create","reports.schedules.update","reports.schedules.run","expenses.read","expenses.create","expenses.update","expenses.approve"])
MATRIX["INVENTORY"].extend(["dashboard.read","reports.inventory.read","reports.inventory.export","reports.purchases.read","reports.warehouses.read","reports.warehouses.export"])
MATRIX["SALES"].extend(["dashboard.read","reports.sales.read","reports.customers.read","reports.loyalty.read"])
MATRIX["HR"].extend(["dashboard.read","reports.employees.read","reports.employees.export","reports.payroll.read","reports.payroll.export"])

async def seed_rbac(session) -> dict[str, Role]:
        roles: dict[str, Role] = {}
        for name, description in ROLE_DESCRIPTIONS.items():
            code = str(name)
            role = await session.scalar(select(Role).where(Role.code == code))
            if role is None:
                role = Role(name=code.title(), code=code, description=description, is_system=True, is_active=True)
                session.add(role)
                await session.flush()
            roles[name] = role
        permissions: dict[str, Permission] = {}
        for code in PERMISSIONS:
            permission = await session.scalar(select(Permission).where(Permission.code == code))
            if permission is None:
                module, action = (code.split(".", 1) if code != "*" else ("system", "*"))
                permission = Permission(code=code, name=code.replace(".", " ").title(), description=f"Allows {code}", module=module, action=action, is_system=True)
                session.add(permission)
                await session.flush()
            permissions[code] = permission
        for role_code, codes in MATRIX.items():
            for code in codes: await session.execute(insert(role_permissions).values(role_id=roles[role_code].id, permission_id=permissions[code].id).on_conflict_do_nothing())
        return roles


async def seed() -> None:
    async with AsyncSessionFactory() as session:
        roles = await seed_rbac(session)
        if os.environ.get("SEED_LOCAL_DEMO_USERS", "").lower() not in {"1", "true", "yes"}:
            await session.commit()
            return
        for email, name, password_variable, role_code in DEMOS:
            password = os.environ.get(password_variable, "")
            if len(password) < 12:
                raise RuntimeError(f"{password_variable} must be configured with at least 12 characters")
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, full_name=name, password_hash=hash_password(password)); session.add(user); await session.flush()
            await session.execute(insert(user_roles).values(user_id=user.id, role_id=roles[role_code].id).on_conflict_do_nothing())
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
