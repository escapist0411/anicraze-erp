from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.reports import PeriodType, ReportFormat, ScheduleFrequency, TargetType


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportFilterRequest(Strict):
    date_from: date | None = None; date_to: date | None = None; preset: str | None = None
    store_id: UUID | None = None; warehouse_id: UUID | None = None; product_id: UUID | None = None
    category_id: UUID | None = None; employee_id: UUID | None = None; supplier_id: UUID | None = None
    payment_method: str | None = None; status: str | None = None; compare_with_previous: bool = False
    timezone: str = "Asia/Kolkata"
    @model_validator(mode="after")
    def valid_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to: raise ValueError("date_from must not exceed date_to")
        return self


class ExpenseCreateRequest(Strict):
    expense_date: date; category: str; description: str = Field(min_length=2, max_length=500); amount: Decimal = Field(gt=0); gst_amount: Decimal = Field(0, ge=0); store_id: UUID | None = None; supplier_id: UUID | None = None; payment_method: str | None = None; reference_number: str | None = None
class ExpenseUpdateRequest(Strict):
    expense_date: date | None = None; category: str | None = None; description: str | None = None; amount: Decimal | None = Field(None, gt=0); gst_amount: Decimal | None = Field(None, ge=0); payment_method: str | None = None; reference_number: str | None = None


class ReportExportRequest(Strict):
    report_type: str; format: ReportFormat; filters: ReportFilterRequest = Field(default_factory=ReportFilterRequest)


class ReportScheduleCreateRequest(Strict):
    name: str = Field(min_length=2); report_type: str; format: ReportFormat; filters_json: dict[str, Any] = Field(default_factory=dict); frequency: ScheduleFrequency; day_of_week: int | None = Field(None, ge=0, le=6); day_of_month: int | None = Field(None, ge=1, le=31); time_of_day: time; timezone: str = "Asia/Kolkata"; recipient_emails_json: list[EmailStr] = Field(default_factory=list); is_active: bool = True
    @model_validator(mode="after")
    def frequency_fields(self):
        if self.frequency == ScheduleFrequency.WEEKLY and self.day_of_week is None: raise ValueError("day_of_week is required for weekly schedules")
        if self.frequency == ScheduleFrequency.MONTHLY and self.day_of_month is None: raise ValueError("day_of_month is required for monthly schedules")
        return self
class ReportScheduleUpdateRequest(Strict):
    name: str | None = None; format: ReportFormat | None = None; filters_json: dict[str, Any] | None = None; frequency: ScheduleFrequency | None = None; day_of_week: int | None = Field(None, ge=0, le=6); day_of_month: int | None = Field(None, ge=1, le=31); time_of_day: time | None = None; timezone: str | None = None; recipient_emails_json: list[EmailStr] | None = None; is_active: bool | None = None


class BusinessTargetCreateRequest(Strict):
    target_type: TargetType; store_id: UUID | None = None; employee_id: UUID | None = None; period_type: PeriodType; start_date: date; end_date: date; target_value: Decimal = Field(gt=0)
    @model_validator(mode="after")
    def dates(self):
        if self.start_date > self.end_date: raise ValueError("start_date must not exceed end_date")
        return self
class BusinessTargetUpdateRequest(Strict):
    target_value: Decimal | None = Field(None, gt=0); actual_value: Decimal | None = Field(None, ge=0); status: str | None = None
