"""simple stock receipts and godown intake

Revision ID: 20260907_0016
Revises: 20260831_0015
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260907_0016"
down_revision = "20260831_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_receipts",
        sa.Column("reference_number", sa.String(100), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("supplier_name", sa.String(180)),
        sa.Column("invoice_number", sa.String(100)),
        sa.Column("purchase_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.UniqueConstraint("reference_number", name="uq_stock_receipts_reference_number"),
    )
    for column in ("reference_number", "warehouse_id", "status", "deleted_at"):
        op.create_index(f"ix_stock_receipts_{column}", "stock_receipts", [column])
    op.create_table(
        "stock_receipt_items",
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stock_receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_variants.id", ondelete="RESTRICT")),
        sa.Column("expected_quantity", sa.Integer(), nullable=False),
        sa.Column("scanned_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("expected_quantity > 0 AND scanned_quantity >= 0 AND scanned_quantity <= expected_quantity", name="ck_stock_receipt_quantities"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_stock_receipt_unit_cost"),
        sa.UniqueConstraint("receipt_id", "product_id", "variant_id", name="uq_stock_receipt_product_variant", postgresql_nulls_not_distinct=True),
    )
    for column in ("receipt_id", "product_id", "variant_id"):
        op.create_index(f"ix_stock_receipt_items_{column}", "stock_receipt_items", [column])


def downgrade() -> None:
    op.drop_table("stock_receipt_items")
    op.drop_table("stock_receipts")
