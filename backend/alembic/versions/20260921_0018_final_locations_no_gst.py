"""final client locations, employee sequences, and tax-free defaults

Revision ID: 20260921_0018
Revises: 20260921_0017
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260921_0018"
down_revision = "20260921_0017"
branch_labels = None
depends_on = None

LOCATIONS = (
    ("CHI", "ELPRO", "ANICRAZE Elpro City Square Mall", "Elpro Chinchwad", "Elpro City Square Mall,\nChinchwad Gaon,\nChinchwad,\nPune,\nPimpri-Chinchwad,\nMaharashtra 411033", "PERMANENT_STORE"),
    ("WES", "WESTEND", "ANICRAZE Westend Mall", "Westend Mall", "Ground Floor,\nWESTEND MALL,\nWard No. 8,\nWireless Colony,\nAundh,\nPune,\nMaharashtra 411067", "PERMANENT_STORE"),
    ("CIV", "CIVIL", "ANICRAZE Civil Court Metro Station", "Civil Court Metro", "Civil Court Metro Station,\nPune,\nMaharashtra", "PERMANENT_STORE"),
    ("SWA", "SWARGATE", "ANICRAZE Swargate Metro Station", "Swargate Metro", "Swargate Metro Station,\nPune,\nMaharashtra", "PERMANENT_STORE"),
    ("KAL", "KALYANI", "ANICRAZE Kalyani Nagar Metro Station", "Kalyani Nagar Metro", "Kalyani Nagar Metro Station,\nPune,\nMaharashtra", "PERMANENT_STORE"),
    ("SHI", "SHIVAJI", "ANICRAZE Shivaji Nagar Metro Station", "Shivaji Nagar Metro", "Shivaji Nagar Metro Station,\nPune,\nMaharashtra", "PERMANENT_STORE"),
    ("EV1", "EVENT1", "ANICRAZE Event 1", "Event 1", None, "EVENT_LOCATION"),
    ("EV2", "EVENT2", "ANICRAZE Event 2", "Event 2", None, "EVENT_LOCATION"),
)

def upgrade():
    op.add_column("stores", sa.Column("short_name", sa.String(100)))
    op.create_table("employee_location_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_employee_location_sequences_store_id", "employee_location_sequences", ["store_id"], unique=True)
    connection = op.get_bind()
    for old, code, name, short_name, address, kind in LOCATIONS:
        existing = connection.execute(sa.text("SELECT id FROM stores WHERE code=:code"), {"code": code}).scalar()
        old_id = connection.execute(sa.text("SELECT id FROM stores WHERE code=:old"), {"old": old}).scalar()
        if existing and old_id and existing != old_id:
            raise RuntimeError(f"Duplicate selling locations found for {old}/{code}; manual merge required")
        target = existing or old_id
        if target:
            connection.execute(sa.text("UPDATE stores SET code=:code,name=:name,short_name=:short,address=:address,location_type=:kind,deleted_at=NULL WHERE id=:id"), {"code":code,"name":name,"short":short_name,"address":address,"kind":kind,"id":target})
        else:
            connection.execute(sa.text("INSERT INTO stores (id,code,name,short_name,address,location_type,status,created_at,updated_at) VALUES (gen_random_uuid(),:code,:name,:short,:address,:kind,'ACTIVE',now(),now())"), {"code":code,"name":name,"short":short_name,"address":address,"kind":kind})
    connection.execute(sa.text("UPDATE products SET gst_rate=0"))

def downgrade():
    op.drop_table("employee_location_sequences")
    op.drop_column("stores", "short_name")
