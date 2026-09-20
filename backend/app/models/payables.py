from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import EntityBase


class PayableStatus(StrEnum):
    UNPAID = "UNPAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


class PayablePaymentMethod(StrEnum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    UPI = "UPI"
    CHEQUE = "CHEQUE"
    OTHER = "OTHER"


class ReminderStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    TRIGGERED = "TRIGGERED"
    DISMISSED = "DISMISSED"
    CANCELLED = "CANCELLED"


class PurchasePayable(EntityBase):
    __tablename__ = "purchase_payables"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_purchase_payable_total_nonnegative"),
        Index("ix_purchase_payables_status_due", "status", "due_date"),
    )
    supplier_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True)
    stock_receipt_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("stock_receipts.id", ondelete="RESTRICT"), unique=True, index=True)
    reference_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), index=True)
    invoice_date: Mapped[date] = mapped_column(Date, index=True)
    supplier_name_snapshot: Mapped[str] = mapped_column(String(180))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[PayableStatus] = mapped_column(Enum(PayableStatus, native_enum=False, length=30), index=True)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    supplier = relationship("Supplier")
    payments: Mapped[list["PurchasePaymentTransaction"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    reminders: Mapped[list["PaymentReminder"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class PurchasePaymentTransaction(EntityBase):
    __tablename__ = "purchase_payment_transactions"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_purchase_payment_amount_positive"),)
    payable_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("purchase_payables.id", ondelete="RESTRICT"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    payment_method: Mapped[PayablePaymentMethod] = mapped_column(Enum(PayablePaymentMethod, native_enum=False, length=30), index=True)
    payment_date: Mapped[date] = mapped_column(Date, index=True)
    reference_number: Mapped[str | None] = mapped_column(String(120), index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class PaymentReminder(EntityBase):
    __tablename__ = "payment_reminders"
    __table_args__ = (Index("ix_payment_reminders_due", "status", "remind_at"),)
    payable_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("purchase_payables.id", ondelete="CASCADE"), index=True)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[ReminderStatus] = mapped_column(Enum(ReminderStatus, native_enum=False, length=20), index=True)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snoozed_from_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("payment_reminders.id", ondelete="SET NULL"))
