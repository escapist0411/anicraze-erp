"""phase 7 operational notifications and report delivery

Revision ID: 20260831_0015
Revises: 20260831_0014
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="20260831_0015";down_revision="20260831_0014";branch_labels=None;depends_on=None

def upgrade():
    op.create_table("notifications",sa.Column("user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("category",sa.String(30),nullable=False),sa.Column("severity",sa.String(20),nullable=False),sa.Column("title",sa.String(160),nullable=False),sa.Column("message",sa.Text(),nullable=False),sa.Column("entity_type",sa.String(50)),sa.Column("entity_id",postgresql.UUID(as_uuid=True)),sa.Column("action_path",sa.String(500)),sa.Column("dedupe_key",sa.String(220),nullable=False),sa.Column("is_read",sa.Boolean(),server_default=sa.false(),nullable=False),sa.Column("read_at",sa.DateTime(timezone=True)),sa.Column("is_resolved",sa.Boolean(),server_default=sa.false(),nullable=False),sa.Column("resolved_at",sa.DateTime(timezone=True)),sa.Column("resolution_reason",sa.String(255)),sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)),sa.Column("created_by_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("updated_by_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.UniqueConstraint("user_id","dedupe_key",name="uq_notification_user_dedupe"))
    op.create_index("ix_notifications_user_active","notifications",["user_id","is_resolved","created_at"]);op.create_index("ix_notifications_user_id","notifications",["user_id"]);op.create_index("ix_notifications_category","notifications",["category"]);op.create_index("ix_notifications_severity","notifications",["severity"]);op.create_index("ix_notifications_is_read","notifications",["is_read"]);op.create_index("ix_notifications_is_resolved","notifications",["is_resolved"]);op.create_index("ix_notifications_deleted_at","notifications",["deleted_at"])
    op.create_table("report_delivery_attempts",sa.Column("report_export_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("report_export_history.id",ondelete="CASCADE"),nullable=False),sa.Column("schedule_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("report_schedules.id",ondelete="SET NULL")),sa.Column("recipient",sa.String(320),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("provider",sa.String(40),nullable=False),sa.Column("sent_at",sa.DateTime(timezone=True)),sa.Column("failure_reason",sa.String(500)),sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)),sa.Column("created_by_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("updated_by_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL")))
    for col in ("report_export_id","schedule_id","recipient","status","deleted_at"):op.create_index(f"ix_report_delivery_attempts_{col}","report_delivery_attempts",[col])

def downgrade():
    op.drop_table("report_delivery_attempts");op.drop_table("notifications")
