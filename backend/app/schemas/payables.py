from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.payables import PayablePaymentMethod, PayableStatus, ReminderStatus


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PayableCreate(StrictModel):
    supplier_id: UUID
    stock_receipt_id: UUID | None = None
    invoice_number: str | None = Field(None, max_length=100)
    invoice_date: date = Field(default_factory=date.today)
    total_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    initially_paid: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    initial_payment_method: PayablePaymentMethod | None = None
    due_date: date | None = None
    remind_at: datetime | None = None
    notes: str | None = Field(None, max_length=2000)


class PaymentCreate(StrictModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    payment_method: PayablePaymentMethod
    payment_date: date = Field(default_factory=date.today)
    reference_number: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=1000)


class ReminderCreate(StrictModel):
    remind_at: datetime


class PayableUpdate(StrictModel):
    due_date: date | None = None
    notes: str | None = Field(None, max_length=2000)


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    amount: Decimal
    payment_method: PayablePaymentMethod
    payment_date: date
    reference_number: str | None
    notes: str | None
    created_at: datetime


class ReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    remind_at: datetime
    status: ReminderStatus
    triggered_at: datetime | None
    dismissed_at: datetime | None
    snoozed_from_id: UUID | None


class PayableResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    stock_receipt_id: UUID | None
    reference_number: str
    invoice_number: str | None
    invoice_date: date
    total_amount: Decimal
    amount_paid: Decimal
    pending_amount: Decimal
    status: PayableStatus
    due_date: date | None
    next_reminder_at: datetime | None
    reminder_enabled: bool
    notes: str | None
    payments: list[PaymentResponse]
    reminders: list[ReminderResponse]
    created_at: datetime
    updated_at: datetime


class PayableSummary(BaseModel):
    total_purchase_value: Decimal
    total_paid: Decimal
    total_pending: Decimal
    overdue: Decimal
    due_this_week: Decimal
    next_payment: PayableResponse | None
