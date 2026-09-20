"""retire the superseded demo shop without deleting history

Revision ID: 20260921_0019
Revises: 20260921_0018
"""
from alembic import op
import sqlalchemy as sa

revision = "20260921_0019"
down_revision = "20260921_0018"
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    old_id = connection.execute(sa.text("SELECT id FROM stores WHERE code='DEMO_SHOP' AND deleted_at IS NULL")).scalar()
    elpro_id = connection.execute(sa.text("SELECT id FROM stores WHERE code='ELPRO' AND deleted_at IS NULL")).scalar()
    if not old_id:
        return
    if not elpro_id:
        raise RuntimeError("ELPRO must exist before DEMO_SHOP can be retired")
    nonzero = connection.execute(sa.text("SELECT count(*) FROM inventory WHERE store_id=:id AND (available_quantity<>0 OR reserved_quantity<>0 OR damaged_quantity<>0)"), {"id": old_id}).scalar_one()
    history = connection.execute(sa.text("SELECT count(*) FROM invoices WHERE store_id=:id"), {"id": old_id}).scalar_one()
    if nonzero or history:
        raise RuntimeError("DEMO_SHOP contains stock or invoice history; manual merge required")
    connection.execute(sa.text("UPDATE users SET assigned_store_id=:elpro WHERE assigned_store_id=:old"), {"elpro":elpro_id,"old":old_id})
    connection.execute(sa.text("UPDATE stores SET status='INACTIVE', deleted_at=now(), updated_at=now() WHERE id=:old"), {"old":old_id})

def downgrade():
    op.execute("UPDATE stores SET status='ACTIVE', deleted_at=NULL, updated_at=now() WHERE code='DEMO_SHOP'")
