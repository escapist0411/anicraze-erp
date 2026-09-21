"""decouple new invoices from CRM and snapshot sale cost

Revision ID: 20260921_0020
Revises: 20260921_0019
"""
from alembic import op
import sqlalchemy as sa

revision = "20260921_0020"
down_revision = "20260921_0019"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("invoices", sa.Column("customer_name_snapshot", sa.String(180), nullable=True))
    op.add_column("invoices", sa.Column("customer_phone_snapshot", sa.String(20), nullable=True))
    op.execute("""UPDATE invoices i SET customer_name_snapshot=COALESCE(c.name,'Walk-in Customer'), customer_phone_snapshot=c.phone FROM customers c WHERE i.customer_id=c.id""")
    op.execute("UPDATE invoices SET customer_name_snapshot='Walk-in Customer' WHERE customer_name_snapshot IS NULL")
    op.alter_column("invoices", "customer_name_snapshot", nullable=False)
    op.alter_column("invoices", "customer_id", nullable=True)
    op.add_column("invoice_items", sa.Column("unit_cost", sa.Numeric(14,2), nullable=True))
    op.execute("""UPDATE invoice_items ii SET unit_cost=COALESCE(inv.average_cost,0) FROM inventory inv WHERE ii.inventory_id=inv.id""")
    op.execute("UPDATE invoice_items SET unit_cost=0 WHERE unit_cost IS NULL")
    op.alter_column("invoice_items", "unit_cost", nullable=False)
    op.alter_column("customer_communications", "customer_id", nullable=True)

def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM invoices WHERE customer_id IS NULL")).scalar_one():
        raise RuntimeError("Cannot restore mandatory customer_id while snapshot-only invoices exist")
    op.alter_column("customer_communications", "customer_id", nullable=False)
    op.drop_column("invoice_items", "unit_cost")
    op.alter_column("invoices", "customer_id", nullable=False)
    op.drop_column("invoices", "customer_phone_snapshot")
    op.drop_column("invoices", "customer_name_snapshot")
