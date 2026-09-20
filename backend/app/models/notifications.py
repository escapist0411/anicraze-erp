from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import EntityBase


class NotificationCategory(StrEnum):
    INVENTORY="INVENTORY"; TRANSFER="TRANSFER"; PROCUREMENT="PROCUREMENT"; PAYMENT="PAYMENT"; COMMUNICATION="COMMUNICATION"; REPORT="REPORT"; SYSTEM="SYSTEM"
class NotificationSeverity(StrEnum):
    INFO="INFO"; WARNING="WARNING"; HIGH="HIGH"; CRITICAL="CRITICAL"


class Notification(EntityBase):
    __tablename__="notifications"
    __table_args__=(UniqueConstraint("user_id","dedupe_key",name="uq_notification_user_dedupe"),Index("ix_notifications_user_active","user_id","is_resolved","created_at"),)
    user_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("users.id",ondelete="CASCADE"),index=True)
    category:Mapped[NotificationCategory]=mapped_column(Enum(NotificationCategory,native_enum=False,length=30),index=True)
    severity:Mapped[NotificationSeverity]=mapped_column(Enum(NotificationSeverity,native_enum=False,length=20),index=True)
    title:Mapped[str]=mapped_column(String(160));message:Mapped[str]=mapped_column(Text)
    entity_type:Mapped[str|None]=mapped_column(String(50));entity_id:Mapped[UUID|None]=mapped_column(PGUUID(as_uuid=True));action_path:Mapped[str|None]=mapped_column(String(500))
    dedupe_key:Mapped[str]=mapped_column(String(220));is_read:Mapped[bool]=mapped_column(Boolean,default=False,index=True);read_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    is_resolved:Mapped[bool]=mapped_column(Boolean,default=False,index=True);resolved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True));resolution_reason:Mapped[str|None]=mapped_column(String(255))


class ReportDeliveryAttempt(EntityBase):
    __tablename__="report_delivery_attempts"
    report_export_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("report_export_history.id",ondelete="CASCADE"),index=True)
    schedule_id:Mapped[UUID|None]=mapped_column(PGUUID(as_uuid=True),ForeignKey("report_schedules.id",ondelete="SET NULL"),index=True)
    recipient:Mapped[str]=mapped_column(String(320),index=True);status:Mapped[str]=mapped_column(String(20),index=True)
    provider:Mapped[str]=mapped_column(String(40));sent_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True));failure_reason:Mapped[str|None]=mapped_column(String(500))
