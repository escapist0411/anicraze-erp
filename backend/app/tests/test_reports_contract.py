from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.reports import safe_cell
from app.main import app
from app.schemas.reports import ReportFilterRequest, ReportScheduleCreateRequest
from app.services.reports import resolve_date_range, scoped_store


def test_phase19_routes_are_registered():
    paths={route.path for route in app.routes}
    assert {"/api/v1/dashboard/owner","/api/v1/reports/export","/api/v1/reports/weekly-business-summary","/api/v1/report-schedules","/api/v1/expenses"} <= paths


def test_date_resolver_uses_exclusive_utc_end_boundary():
    start,end=resolve_date_range(ReportFilterRequest(date_from=date(2026,8,1),date_to=date(2026,8,1)))
    assert end > start and (end-start).days == 1


def test_csv_formula_injection_is_neutralized():
    assert safe_cell("=SUM(A1:A2)").startswith("'")
    assert safe_cell("@cmd").startswith("'")
    assert safe_cell("ordinary") == "ordinary"


def test_non_admin_store_scope_cannot_be_bypassed():
    assigned=uuid4(); actor=SimpleNamespace(roles=[SimpleNamespace(code="MANAGER")],assigned_store_id=assigned)
    assert scoped_store(actor,None)==assigned
    with pytest.raises(Exception): scoped_store(actor,uuid4())


def test_weekly_schedule_requires_weekday():
    with pytest.raises(ValueError): ReportScheduleCreateRequest(name="Weekly sales",report_type="sales_summary",format="PDF",frequency="WEEKLY",time_of_day="09:00",recipient_emails_json=[])
