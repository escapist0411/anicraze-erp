"""owner purchase payables, reminders, and selling location types

Revision ID: 20260921_0017
Revises: 20260907_0016
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="20260921_0017"
down_revision="20260907_0016"
branch_labels=None
depends_on=None

def audit_columns():
    return [sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)),sa.Column("created_by_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("updated_by_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL"))]

def upgrade():
    op.add_column("stores",sa.Column("contact_number",sa.String(30)))
    op.add_column("stores",sa.Column("location_type",sa.String(30),nullable=False,server_default="PERMANENT_STORE"))
    op.create_index("ix_stores_location_type","stores",["location_type"])
    op.create_table("purchase_payables",sa.Column("supplier_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("suppliers.id",ondelete="RESTRICT"),nullable=False),sa.Column("stock_receipt_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("stock_receipts.id",ondelete="RESTRICT"),unique=True),sa.Column("reference_number",sa.String(100),nullable=False,unique=True),sa.Column("invoice_number",sa.String(100)),sa.Column("invoice_date",sa.Date(),nullable=False),sa.Column("supplier_name_snapshot",sa.String(180),nullable=False),sa.Column("total_amount",sa.Numeric(18,2),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("due_date",sa.Date()),sa.Column("reminder_enabled",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("notes",sa.Text()),*audit_columns(),sa.CheckConstraint("total_amount >= 0",name="ck_purchase_payable_total_nonnegative"))
    for col in ("supplier_id","stock_receipt_id","reference_number","invoice_number","invoice_date","status","due_date","created_at","deleted_at"):op.create_index(f"ix_purchase_payables_{col}","purchase_payables",[col])
    op.create_index("ix_purchase_payables_status_due","purchase_payables",["status","due_date"])
    op.create_table("purchase_payment_transactions",sa.Column("payable_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("purchase_payables.id",ondelete="RESTRICT"),nullable=False),sa.Column("amount",sa.Numeric(18,2),nullable=False),sa.Column("payment_method",sa.String(30),nullable=False),sa.Column("payment_date",sa.Date(),nullable=False),sa.Column("reference_number",sa.String(120)),sa.Column("notes",sa.Text()),*audit_columns(),sa.CheckConstraint("amount > 0",name="ck_purchase_payment_amount_positive"))
    for col in ("payable_id","payment_method","payment_date","reference_number","deleted_at"):op.create_index(f"ix_purchase_payment_transactions_{col}","purchase_payment_transactions",[col])
    op.create_table("payment_reminders",sa.Column("payable_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("purchase_payables.id",ondelete="CASCADE"),nullable=False),sa.Column("remind_at",sa.DateTime(timezone=True),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("triggered_at",sa.DateTime(timezone=True)),sa.Column("dismissed_at",sa.DateTime(timezone=True)),sa.Column("snoozed_from_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("payment_reminders.id",ondelete="SET NULL")),*audit_columns())
    for col in ("payable_id","remind_at","status","deleted_at"):op.create_index(f"ix_payment_reminders_{col}","payment_reminders",[col])
    op.create_index("ix_payment_reminders_due","payment_reminders",["status","remind_at"])

def downgrade():
    op.drop_table("payment_reminders")
    op.drop_table("purchase_payment_transactions")
    op.drop_table("purchase_payables")
    op.drop_index("ix_stores_location_type",table_name="stores")
    op.drop_column("stores","location_type")
    op.drop_column("stores","contact_number")
