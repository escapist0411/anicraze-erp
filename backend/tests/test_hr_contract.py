from datetime import date,time
from decimal import Decimal
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.models.hr import EmploymentType
from app.schemas.hr import EmployeeCreateRequest,LeaveCreateRequest,SalaryStructureRequest,ShiftRequest
def test_employee_requires_contact_and_location_contract():
 x=EmployeeCreateRequest(first_name="A",last_name="B",email="a@example.com",phone="9999999999",joining_date=date.today(),store_id=uuid4());assert x.employment_type==EmploymentType.FULL_TIME
def test_shift_minutes_nonnegative():
 with pytest.raises(ValidationError):ShiftRequest(name="Bad",code="BAD",start_time=time(9),end_time=time(18),break_minutes=-1,grace_minutes=0,half_day_minutes=240,full_day_minutes=480,overtime_after_minutes=480)
def test_leave_payload_dates_are_typed():
 x=LeaveCreateRequest(employee_id=uuid4(),leave_type_id=uuid4(),start_date=date.today(),end_date=date.today(),reason="Sick");assert x.start_day_type=="FULL_DAY"
def test_salary_is_decimal_and_positive():
 x=SalaryStructureRequest(name="Standard",code="STD",effective_from=date.today(),monthly_ctc=Decimal("35000"));assert x.monthly_ctc==Decimal("35000")
 with pytest.raises(ValidationError):SalaryStructureRequest(name="Bad",code="BAD",effective_from=date.today(),monthly_ctc=0)
