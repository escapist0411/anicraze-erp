"""phase 4 invoice idempotency

Revision ID: 20260831_0013
Revises: 20260831_0012
"""
from alembic import op
import sqlalchemy as sa

revision="20260831_0013"
down_revision="20260831_0012"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("invoices",sa.Column("idempotency_key",sa.String(100),nullable=True))
    op.execute("UPDATE invoices SET idempotency_key = 'legacy:' || id::text WHERE idempotency_key IS NULL")
    op.alter_column("invoices","idempotency_key",nullable=False)
    op.create_index("ix_invoices_idempotency_key","invoices",["idempotency_key"],unique=True)

def downgrade():
    op.drop_index("ix_invoices_idempotency_key",table_name="invoices")
    op.drop_column("invoices","idempotency_key")
