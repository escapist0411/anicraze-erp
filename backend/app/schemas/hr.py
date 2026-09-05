from datetime import date,datetime,time
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,EmailStr,Field,model_validator
from app.models.hr import *
class Strict(BaseModel):model_config=ConfigDict(extra="forbid")
class DepartmentRequest(Strict):name:str;code:str;description:str|None=None;parent_department_id:UUID|None=None;is_active:bool=True
class DepartmentResponse(BaseModel):model_config=ConfigDict(from_attributes=True);id:UUID;name:str;code:str;description:str|None;parent_department_id:UUID|None;is_active:bool
class DesignationRequest(Strict):name:str;code:str;description:str|None=None;department_id:UUID|None=None;level:int=Field(ge=1);is_active:bool=True
class DesignationResponse(BaseModel):model_config=ConfigDict(from_attributes=True);id:UUID;name:str;code:str;department_id:UUID|None;level:int;is_active:bool
class EmployeeCreateRequest(Strict):first_name:str;last_name:str;email:EmailStr;phone:str;joining_date:date;employment_type:EmploymentType=EmploymentType.FULL_TIME;department_id:UUID|None=None;designation_id:UUID|None=None;store_id:UUID|None=None;warehouse_id:UUID|None=None;shift_id:UUID|None=None;date_of_birth:date|None=None;gender:str|None=None;country:str="India";emergency_contact_name:str|None=None;emergency_contact_phone:str|None=None;bank_name:str|None=None;bank_account_number:str|None=None;bank_ifsc:str|None=None;pan_number:str|None=None;aadhaar_masked:str|None=None;notes:str|None=None
class EmployeeUpdateRequest(Strict):department_id:UUID|None=None;designation_id:UUID|None=None;store_id:UUID|None=None;warehouse_id:UUID|None=None;shift_id:UUID|None=None;phone:str|None=None;notes:str|None=None
class EmployeeStatusRequest(Strict):status:EmploymentStatus;deactivate_user:bool=False;reason:str|None=None
class EmployeeLinkRequest(Strict):user_id:UUID
class EmployeeAssignStoreRequest(Strict):store_id:UUID|None=None;warehouse_id:UUID|None=None
class EmployeeResponse(BaseModel):model_config=ConfigDict(from_attributes=True);id:UUID;employee_code:str;user_id:UUID|None;first_name:str;last_name:str;full_name:str;email:str;phone:str;joining_date:date;employment_type:EmploymentType;employment_status:EmploymentStatus;department_id:UUID|None;designation_id:UUID|None;store_id:UUID|None;warehouse_id:UUID|None;shift_id:UUID|None;created_at:datetime
class ShiftRequest(Strict):name:str;code:str;start_time:time;end_time:time;break_minutes:int=Field(ge=0);grace_minutes:int=Field(ge=0);half_day_minutes:int=Field(gt=0);full_day_minutes:int=Field(gt=0);overtime_after_minutes:int=Field(ge=0);crosses_midnight:bool=False;is_flexible:bool=False;is_active:bool=True
class ShiftResponse(BaseModel):model_config=ConfigDict(from_attributes=True);id:UUID;name:str;code:str;start_time:time;end_time:time;break_minutes:int;grace_minutes:int;half_day_minutes:int;full_day_minutes:int;overtime_after_minutes:int;crosses_midnight:bool;is_flexible:bool;is_active:bool
class ShiftAssignmentRequest(Strict):employee_id:UUID;shift_id:UUID;store_id:UUID|None=None;start_date:date;end_date:date|None=None;days_of_week_json:list[int]=[0,1,2,3,4,5]
class AttendanceRequest(Strict):employee_id:UUID|None=None;device:str|None=None
class AttendanceManualRequest(Strict):employee_id:UUID;attendance_date:date;status:AttendanceStatus;check_in_at:datetime|None=None;check_out_at:datetime|None=None;reason:str=Field(min_length=2)
class AttendanceResponse(BaseModel):model_config=ConfigDict(from_attributes=True);id:UUID;employee_id:UUID;attendance_date:date;store_id:UUID|None;warehouse_id:UUID|None;check_in_at:datetime|None;check_out_at:datetime|None;worked_minutes:int;break_minutes:int;overtime_minutes:int;late_minutes:int;early_exit_minutes:int;status:AttendanceStatus;source:AttendanceSource
class LeaveTypeRequest(Strict):name:str;code:str;annual_entitlement:Decimal=Field(ge=0);description:str|None=None;carry_forward_allowed:bool=False;maximum_carry_forward:Decimal=Field(0,ge=0);requires_document:bool=False;minimum_notice_days:int=Field(0,ge=0);maximum_consecutive_days:int|None=None;paid:bool=True;is_active:bool=True
class LeaveTypeResponse(BaseModel):model_config=ConfigDict(from_attributes=True);id:UUID;name:str;code:str;annual_entitlement:Decimal;paid:bool;is_active:bool
class LeaveCreateRequest(Strict):employee_id:UUID;leave_type_id:UUID;start_date:date;end_date:date;start_day_type:str="FULL_DAY";end_day_type:str="FULL_DAY";reason:str
class LeaveActionRequest(Strict):reason:str|None=None
class LeaveResponse(BaseModel):model_config=ConfigDict(from_attributes=True);id:UUID;request_number:str;employee_id:UUID;leave_type_id:UUID;start_date:date;end_date:date;total_days:Decimal;reason:str;status:LeaveStatus;created_at:datetime
class SalaryComponentRequest(Strict):name:str;code:str;component_type:ComponentType;calculation_type:CalculationType;default_value:Decimal|None=Field(None,ge=0);taxable:bool=False;affects_gross:bool=True;affects_net:bool=True;is_active:bool=True
class SalaryStructureRequest(Strict):name:str;code:str;description:str|None=None;effective_from:date;monthly_ctc:Decimal=Field(gt=0);is_active:bool=True
class PayrollPeriodRequest(Strict):name:str;start_date:date;end_date:date;payment_date:date
class PayrollRunRequest(Strict):period_id:UUID
class PayrollRunResponse(BaseModel):model_config=ConfigDict(from_attributes=True);id:UUID;period_id:UUID;run_number:str;status:PayrollStatus;gross_total:Decimal;deduction_total:Decimal;net_total:Decimal;created_at:datetime
class PerformanceReviewRequest(Strict):employee_id:UUID;reviewer_employee_id:UUID|None=None;review_period_start:date;review_period_end:date;attendance_score:Decimal=Field(ge=0,le=100);sales_score:Decimal=Field(ge=0,le=100);task_score:Decimal=Field(ge=0,le=100);customer_feedback_score:Decimal=Field(ge=0,le=100);strengths:str|None=None;improvement_areas:str|None=None;comments:str|None=None
class GoalRequest(Strict):employee_id:UUID;title:str;description:str|None=None;metric_type:str;target_value:Decimal=Field(gt=0);start_date:date;due_date:date;priority:str="NORMAL"
class TaskRequest(Strict):assigned_to_employee_id:UUID;assigned_by_employee_id:UUID|None=None;title:str;description:str|None=None;priority:str="NORMAL";due_at:datetime|None=None
