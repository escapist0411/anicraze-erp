"""phase 3 stock transfer lifecycle

Revision ID: 20260831_0012
Revises: 20addf49befe
"""
from alembic import op
import sqlalchemy as sa

revision="20260831_0012"
down_revision="20addf49befe"
branch_labels=None
depends_on=None

def upgrade():
    for name in ("picked_by_id","packed_by_id","dispatched_by_id","received_by_id"):
        op.add_column("stock_transfers",sa.Column(name,sa.UUID(),nullable=True)); op.create_foreign_key(f"fk_stock_transfers_{name}_users","stock_transfers","users",[name],["id"],ondelete="SET NULL")
    for name in ("approved_at","picking_started_at","picked_at","packed_at","receiving_started_at"):
        op.add_column("stock_transfers",sa.Column(name,sa.DateTime(timezone=True),nullable=True))
    op.add_column("stock_transfers",sa.Column("cancellation_reason",sa.Text(),nullable=True)); op.add_column("stock_transfers",sa.Column("discrepancy_notes",sa.Text(),nullable=True))
    for name in ("picked_quantity","received_quantity","damaged_quantity","shortage_quantity","excess_quantity"):
        op.add_column("stock_transfer_items",sa.Column(name,sa.Integer(),server_default="0",nullable=False))
    op.add_column("stock_transfer_items",sa.Column("discrepancy_note",sa.Text(),nullable=True))

def downgrade():
    op.drop_column("stock_transfer_items","discrepancy_note")
    for name in reversed(("picked_quantity","received_quantity","damaged_quantity","shortage_quantity","excess_quantity")): op.drop_column("stock_transfer_items",name)
    op.drop_column("stock_transfers","discrepancy_notes"); op.drop_column("stock_transfers","cancellation_reason")
    for name in reversed(("approved_at","picking_started_at","picked_at","packed_at","receiving_started_at")): op.drop_column("stock_transfers",name)
    for name in reversed(("picked_by_id","packed_by_id","dispatched_by_id","received_by_id")):
        op.drop_constraint(f"fk_stock_transfers_{name}_users","stock_transfers",type_="foreignkey"); op.drop_column("stock_transfers",name)
