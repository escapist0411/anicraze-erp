"""phase 5 provider-backed customer communications

Revision ID: 20260831_0014
Revises: 20260831_0013
"""
from alembic import op
import sqlalchemy as sa

revision="20260831_0014";down_revision="20260831_0013";branch_labels=None;depends_on=None

def upgrade():
    columns=[
        sa.Column("purpose",sa.String(40),server_default="INVOICE",nullable=False),sa.Column("recipient",sa.String(40)),sa.Column("provider",sa.String(30),server_default="development",nullable=False),sa.Column("provider_message_id",sa.String(160)),sa.Column("idempotency_key",sa.String(160)),sa.Column("attempt_count",sa.Integer(),server_default="0",nullable=False),sa.Column("last_attempt_at",sa.DateTime(timezone=True)),sa.Column("delivered_at",sa.DateTime(timezone=True)),sa.Column("read_at",sa.DateTime(timezone=True)),sa.Column("failed_at",sa.DateTime(timezone=True)),sa.Column("failure_code",sa.String(80)),sa.Column("failure_message",sa.String(500))]
    for column in columns:op.add_column("customer_communications",column)
    op.execute("UPDATE customer_communications SET idempotency_key='legacy:'||id::text WHERE idempotency_key IS NULL")
    op.alter_column("customer_communications","idempotency_key",nullable=False)
    op.alter_column("customer_communications","status",type_=sa.String(30),existing_type=sa.String(20))
    op.create_index("ix_customer_communications_idempotency_key","customer_communications",["idempotency_key"],unique=True)
    op.create_index("ix_customer_communications_provider_message_id","customer_communications",["provider_message_id"])
    op.create_index("ix_customer_communications_related_invoice_id","customer_communications",["related_invoice_id"])
    op.create_index("ix_customer_communications_status","customer_communications",["status"])

def downgrade():
    for name in ("status","related_invoice_id","provider_message_id","idempotency_key"):op.drop_index(f"ix_customer_communications_{name}",table_name="customer_communications")
    op.alter_column("customer_communications","status",type_=sa.String(20),existing_type=sa.String(30))
    for name in reversed(("purpose","recipient","provider","provider_message_id","idempotency_key","attempt_count","last_attempt_at","delivered_at","read_at","failed_at","failure_code","failure_message")):op.drop_column("customer_communications",name)
