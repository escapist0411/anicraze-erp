"""align unique indexes with SQLAlchemy metadata

Revision ID: 20260806_0005
Revises: 20260806_0004
"""
from alembic import op

revision = "20260806_0005"
down_revision = "20260806_0004"
branch_labels = None
depends_on = None


def replace_with_unique_index(table: str, field: str, constraint: str) -> None:
    op.drop_constraint(constraint, table, type_="unique")
    op.drop_index(f"ix_{table}_{field}", table_name=table)
    op.create_index(f"ix_{table}_{field}", table, [field], unique=True)


def upgrade() -> None:
    replace_with_unique_index("permissions", "code", "permissions_code_key")
    replace_with_unique_index("users", "email", "users_email_key")
    for field in ("sku", "barcode", "slug"):
        replace_with_unique_index("products", field, f"products_{field}_key")
    for field in ("sku", "barcode"):
        replace_with_unique_index("product_variants", field, f"product_variants_{field}_key")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_constraint("roles_name_key", "roles", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("roles_name_key", "roles", ["name"])
    op.create_index("ix_roles_name", "roles", ["name"])
    for table, fields in (("product_variants", ("sku", "barcode")), ("products", ("sku", "barcode", "slug")), ("users", ("email",)), ("permissions", ("code",))):
        for field in fields:
            op.drop_index(f"ix_{table}_{field}", table_name=table)
            op.create_unique_constraint(f"{table}_{field}_key", table, [field])
            op.create_index(f"ix_{table}_{field}", table, [field])
