"""phase 12 user role and permission management

Revision ID: 20260806_0003
Revises: 20260721_0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260806_0003"
down_revision = "20260721_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("roles", "name", type_=sa.String(100), postgresql_using="name::text")
    op.add_column("roles", sa.Column("code", sa.String(100), nullable=True))
    op.add_column("roles", sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("roles", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute("UPDATE roles SET code = upper(name), is_system = true")
    op.alter_column("roles", "code", nullable=False)
    op.create_index("ix_roles_code", "roles", ["code"], unique=True)
    op.execute("DROP TYPE IF EXISTS role_name")

    op.add_column("permissions", sa.Column("name", sa.String(120), nullable=True))
    op.add_column("permissions", sa.Column("module", sa.String(64), nullable=True))
    op.add_column("permissions", sa.Column("action", sa.String(64), nullable=True))
    op.add_column("permissions", sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE permissions SET name = initcap(replace(code, '.', ' ')), module = split_part(code, '.', 1), action = CASE WHEN code = '*' THEN '*' ELSE split_part(code, '.', 2) END, is_system = true")
    op.alter_column("permissions", "name", nullable=False)
    op.alter_column("permissions", "module", nullable=False)
    op.alter_column("permissions", "action", nullable=False)
    op.create_index("ix_permissions_module", "permissions", ["module"])

    for name, type_ in (("employee_code", sa.String(64)), ("designation", sa.String(120)), ("department", sa.String(120))):
        op.add_column("users", sa.Column(name, type_, nullable=True))
    op.add_column("users", sa.Column("assigned_store_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_users_employee_code", "users", ["employee_code"], unique=True)
    op.create_index("ix_users_department", "users", ["department"])
    op.create_index("ix_users_assigned_store_id", "users", ["assigned_store_id"])

    op.create_table(
        "user_permissions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("user_id", "permission_id"),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_target_user_id", "audit_logs", ["target_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("user_permissions")
    op.drop_index("ix_users_assigned_store_id", table_name="users")
    op.drop_index("ix_users_department", table_name="users")
    op.drop_index("ix_users_employee_code", table_name="users")
    for name in ("must_change_password", "assigned_store_id", "department", "designation", "employee_code"):
        op.drop_column("users", name)
    op.drop_index("ix_permissions_module", table_name="permissions")
    for name in ("is_system", "action", "module", "name"):
        op.drop_column("permissions", name)
    role_name = postgresql.ENUM("OWNER", "ADMIN", "MANAGER", "ACCOUNTANT", "SALES", "INVENTORY", "HR", "EMPLOYEE", name="role_name")
    role_name.create(op.get_bind(), checkfirst=True)
    op.drop_index("ix_roles_code", table_name="roles")
    for name in ("is_active", "is_system", "code"):
        op.drop_column("roles", name)
    op.alter_column("roles", "name", type_=role_name, postgresql_using="name::role_name")
