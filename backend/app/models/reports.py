from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import EntityBase


class ExpenseStatus(StrEnum):
    DRAFT = "DRAFT"; APPROVED = "APPROVED"
class ReportFormat(StrEnum):
    PDF = "PDF"; XLSX = "XLSX"; CSV = "CSV"
class ScheduleFrequency(StrEnum):
    DAILY = "DAILY"; WEEKLY = "WEEKLY"; MONTHLY = "MONTHLY"
class ExportStatus(StrEnum):
    PENDING = "PENDING"; PROCESSING = "PROCESSING"; COMPLETED = "COMPLETED"; FAILED = "FAILED"; EXPIRED = "EXPIRED"
class TargetType(StrEnum):
    REVENUE = "REVENUE"; PROFIT = "PROFIT"; SALES = "SALES"; ORDERS = "ORDERS"; CUSTOMERS = "CUSTOMERS"; ATTENDANCE = "ATTENDANCE"
class PeriodType(StrEnum):
    WEEKLY = "WEEKLY"; MONTHLY = "MONTHLY"; QUARTERLY = "QUARTERLY"; YEARLY = "YEARLY"


class Expense(EntityBase):
    __tablename__ = "expenses"
    expense_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    expense_date: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str] = mapped_column(String(500))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    store_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    supplier_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"))
    payment_method: Mapped[str | None] = mapped_column(String(30))
    reference_number: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[ExpenseStatus] = mapped_column(Enum(ExpenseStatus, native_enum=False, length=20), default=ExpenseStatus.DRAFT, index=True)
    approved_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReportSchedule(EntityBase):
    __tablename__ = "report_schedules"
    name: Mapped[str] = mapped_column(String(160)); report_type: Mapped[str] = mapped_column(String(80), index=True)
    format: Mapped[ReportFormat] = mapped_column(Enum(ReportFormat, native_enum=False, length=10)); filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    frequency: Mapped[ScheduleFrequency] = mapped_column(Enum(ScheduleFrequency, native_enum=False, length=20)); day_of_week: Mapped[int | None] = mapped_column(Integer); day_of_month: Mapped[int | None] = mapped_column(Integer)
    time_of_day: Mapped[time] = mapped_column(Time); timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata"); recipient_emails_json: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True); last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class ReportExportHistory(EntityBase):
    __tablename__ = "report_export_history"
    report_type: Mapped[str] = mapped_column(String(80), index=True); format: Mapped[ReportFormat] = mapped_column(Enum(ReportFormat, native_enum=False, length=10)); filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    file_path: Mapped[str | None] = mapped_column(String(500)); file_url: Mapped[str | None] = mapped_column(String(500)); status: Mapped[ExportStatus] = mapped_column(Enum(ExportStatus, native_enum=False, length=20), index=True)
    generated_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")); generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True)); expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); error_message: Mapped[str | None] = mapped_column(Text); file_size: Mapped[int | None] = mapped_column(Integer)


class BusinessTarget(EntityBase):
    __tablename__ = "business_targets"
    target_type: Mapped[TargetType] = mapped_column(Enum(TargetType, native_enum=False, length=20), index=True); store_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True); employee_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    period_type: Mapped[PeriodType] = mapped_column(Enum(PeriodType, native_enum=False, length=20)); start_date: Mapped[date] = mapped_column(Date); end_date: Mapped[date] = mapped_column(Date); target_value: Mapped[Decimal] = mapped_column(Numeric(18, 2)); actual_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0); status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
