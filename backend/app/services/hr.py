import re
from calendar import monthrange
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from sqlalchemy import func,or_,select
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph,SimpleDocTemplate,Spacer,Table
from app.exceptions.domain import ConflictError,NotFoundError
from app.models.auth import AuditLog,User,UserStatus
from app.models.hr import *
from app.models.inventory import Store,Warehouse
from app.models.procurement import ProcurementSequence
from app.repositories.management import ManagementRepository
from app.utils.time import utc_now
def money(x):return Decimal(x).quantize(Decimal("0.01"))
class HRBase:
 def __init__(self,s,actor,ip=None,user_agent=None):self.s=s;self.actor=actor;self.audit_repo=ManagementRepository(s);self.ip=ip;self.user_agent=user_agent
 async def audit(self,a,k,i,m=None):await self.audit_repo.audit(AuditLog(actor_user_id=self.actor.id,action=a,entity_type=k,entity_id=i,metadata_json=m,ip_address=self.ip,user_agent=self.user_agent,created_at=utc_now()))
 async def next(self,key,prefix):
  x=await self.s.scalar(select(ProcurementSequence).where(ProcurementSequence.key==key).with_for_update())
  if not x:x=ProcurementSequence(key=key,current_value=0);self.s.add(x);await self.s.flush()
  x.current_value+=1;return f"{prefix}-{x.current_value:06d}"
 async def employee(self,id,lock=False):
  q=select(Employee).where(Employee.id==id,Employee.deleted_at.is_(None));x=await self.s.scalar(q.with_for_update() if lock else q)
  if not x:raise NotFoundError("Employee not found","EMPLOYEE_NOT_FOUND")
  return x
class EmployeeService(HRBase):
 async def create(self,d):
  if await self.s.scalar(select(Employee).where(or_(Employee.email==str(d.email).lower(),Employee.phone==re.sub(r"\D","",d.phone)))):raise ConflictError("Employee email or phone exists","EMPLOYEE_DUPLICATE")
  if (d.store_id is None)==(d.warehouse_id is None):raise ConflictError("Exactly one store or warehouse assignment is required","EMPLOYEE_LOCATION_INVALID")
  e=Employee(employee_code=await self.next("employee","ANI-EMP"),first_name=d.first_name,last_name=d.last_name,full_name=f"{d.first_name} {d.last_name}",email=str(d.email).lower(),phone=re.sub(r"\D","",d.phone),employment_status=EmploymentStatus.ACTIVE,**d.model_dump(exclude={"first_name","last_name","email","phone"}),created_by_id=self.actor.id,updated_by_id=self.actor.id);self.s.add(e);await self.s.flush();await self.audit("EMPLOYEE_CREATED","employee",e.id,{"code":e.employee_code});return e
 async def update(self,id,d):e=await self.employee(id,True);values=d.model_dump(exclude_unset=True);[setattr(e,k,v) for k,v in values.items()];e.updated_by_id=self.actor.id;await self.audit("EMPLOYEE_UPDATED","employee",e.id,{"fields":list(values)});return e
 async def link(self,id,user_id):
  e=await self.employee(id,True);u=await self.s.scalar(select(User).where(User.id==user_id,User.deleted_at.is_(None)))
  if not u:raise NotFoundError("User not found","USER_NOT_FOUND")
  if await self.s.scalar(select(Employee).where(Employee.user_id==user_id,Employee.id!=id)):raise ConflictError("User is linked to another employee","EMPLOYEE_USER_ALREADY_LINKED")
  e.user_id=user_id;await self.audit("EMPLOYEE_USER_LINKED","employee",e.id,{"user_id":str(user_id)});return e
 async def status(self,id,status,deactivate=False,reason=None):
  e=await self.employee(id,True);e.employment_status=status
  if deactivate and e.user_id:
   u=await self.s.scalar(select(User).where(User.id==e.user_id).with_for_update());u.status=UserStatus.INACTIVE;u.is_active=False
  await self.audit("EMPLOYEE_STATUS_CHANGED","employee",e.id,{"status":status.value,"reason":reason});return e
 async def delete(self,id):e=await self.employee(id,True);e.deleted_at=utc_now();e.employment_status=EmploymentStatus.INACTIVE;await self.audit("EMPLOYEE_DELETED","employee",id)
 async def list(self,search=None):
  q=select(Employee).where(Employee.deleted_at.is_(None));
  if search:q=q.where(or_(Employee.employee_code.ilike(f"%{search}%"),Employee.full_name.ilike(f"%{search}%"),Employee.email.ilike(f"%{search}%"),Employee.phone.ilike(f"%{search}%")))
  return list((await self.s.scalars(q.order_by(Employee.full_name))).all())
class AttendanceService(HRBase):
 async def linked(self,user_id):
  e=await self.s.scalar(select(Employee).where(Employee.user_id==user_id,Employee.employment_status==EmploymentStatus.ACTIVE,Employee.deleted_at.is_(None)))
  if not e:raise ConflictError("Authenticated user is not linked to an active employee","ATTENDANCE_EMPLOYEE_LINK_REQUIRED")
  return e
 async def check_in(self,employee_id=None,device=None):
  e=await self.employee(employee_id) if employee_id else await self.linked(self.actor.id);today=date.today()
  if await self.s.scalar(select(Attendance).where(Attendance.employee_id==e.id,Attendance.attendance_date==today)):raise ConflictError("Already checked in today","ATTENDANCE_DUPLICATE_CHECKIN")
  now=utc_now();late=0
  if e.shift_id:
   sh=await self.s.scalar(select(Shift).where(Shift.id==e.shift_id));scheduled=datetime.combine(today,sh.start_time,tzinfo=now.tzinfo)+timedelta(minutes=sh.grace_minutes);late=max(0,int((now-scheduled).total_seconds()/60))
  a=Attendance(employee_id=e.id,attendance_date=today,store_id=e.store_id,warehouse_id=e.warehouse_id,check_in_at=now,worked_minutes=0,break_minutes=0,overtime_minutes=0,late_minutes=late,early_exit_minutes=0,status=AttendanceStatus.LATE if late else AttendanceStatus.PRESENT,source=AttendanceSource.WEB,check_in_ip=self.ip,check_in_device=device or self.user_agent,correction_status=CorrectionStatus.NONE,created_by_id=self.actor.id,updated_by_id=self.actor.id);self.s.add(a);await self.s.flush();await self.audit("ATTENDANCE_CHECKED_IN","attendance",a.id);return a
 async def check_out(self,employee_id=None,device=None):
  e=await self.employee(employee_id) if employee_id else await self.linked(self.actor.id);a=await self.s.scalar(select(Attendance).where(Attendance.employee_id==e.id,Attendance.attendance_date==date.today()).with_for_update())
  if not a or not a.check_in_at:raise ConflictError("Check-in required","ATTENDANCE_CHECKIN_REQUIRED")
  if a.check_out_at:raise ConflictError("Already checked out","ATTENDANCE_DUPLICATE_CHECKOUT")
  now=utc_now();a.check_out_at=now;a.check_out_ip=self.ip;a.check_out_device=device or self.user_agent;shift=await self.s.scalar(select(Shift).where(Shift.id==e.shift_id)) if e.shift_id else None;a.break_minutes=shift.break_minutes if shift else 0;a.worked_minutes=max(0,int((now-a.check_in_at).total_seconds()/60)-a.break_minutes);a.overtime_minutes=max(0,a.worked_minutes-(shift.overtime_after_minutes if shift else 480));await self.audit("ATTENDANCE_CHECKED_OUT","attendance",a.id,{"worked_minutes":a.worked_minutes});return a
 async def manual(self,d):
  if await self.s.scalar(select(Attendance).where(Attendance.employee_id==d.employee_id,Attendance.attendance_date==d.attendance_date)):raise ConflictError("Attendance already exists","ATTENDANCE_EXISTS")
  worked=int((d.check_out_at-d.check_in_at).total_seconds()/60) if d.check_in_at and d.check_out_at else 0;a=Attendance(employee_id=d.employee_id,attendance_date=d.attendance_date,check_in_at=d.check_in_at,check_out_at=d.check_out_at,worked_minutes=worked,break_minutes=0,overtime_minutes=max(0,worked-480),late_minutes=0,early_exit_minutes=0,status=d.status,source=AttendanceSource.MANUAL,notes=d.reason,correction_status=CorrectionStatus.APPROVED,created_by_id=self.actor.id,updated_by_id=self.actor.id);self.s.add(a);await self.s.flush();await self.audit("ATTENDANCE_MANUALLY_CREATED","attendance",a.id);return a
class LeaveService(HRBase):
 async def create(self,d):
  await self.employee(d.employee_id);lt=await self.s.scalar(select(LeaveType).where(LeaveType.id==d.leave_type_id,LeaveType.is_active.is_(True),LeaveType.deleted_at.is_(None)))
  if not lt:raise NotFoundError("Leave type not found","LEAVE_TYPE_NOT_FOUND")
  if d.end_date<d.start_date:raise ConflictError("Leave end precedes start","LEAVE_DATES_INVALID")
  if await self.s.scalar(select(LeaveRequest).where(LeaveRequest.employee_id==d.employee_id,LeaveRequest.status.in_([LeaveStatus.SUBMITTED,LeaveStatus.APPROVED]),LeaveRequest.start_date<=d.end_date,LeaveRequest.end_date>=d.start_date)):raise ConflictError("Overlapping leave request","LEAVE_OVERLAP")
  days=Decimal((d.end_date-d.start_date).days+1);days-=Decimal("0.5") if d.start_day_type!="FULL_DAY" else 0;days-=Decimal("0.5") if d.end_day_type!="FULL_DAY" and d.end_date!=d.start_date else 0;r=LeaveRequest(request_number=await self.next("leave","ANI-LV"),**d.model_dump(),total_days=days,status=LeaveStatus.DRAFT,created_by_id=self.actor.id,updated_by_id=self.actor.id);self.s.add(r);await self.s.flush();await self.audit("LEAVE_REQUEST_CREATED","leave_request",r.id);return r
 async def transition(self,id,target,reason=None):
  r=await self.s.scalar(select(LeaveRequest).where(LeaveRequest.id==id,LeaveRequest.deleted_at.is_(None)).with_for_update())
  if not r:raise NotFoundError("Leave request not found","LEAVE_REQUEST_NOT_FOUND")
  bal=await self.s.scalar(select(LeaveBalance).where(LeaveBalance.employee_id==r.employee_id,LeaveBalance.leave_type_id==r.leave_type_id,LeaveBalance.year==r.start_date.year).with_for_update());now=utc_now()
  if target==LeaveStatus.SUBMITTED and r.status==LeaveStatus.DRAFT:
   if bal and bal.closing_balance-bal.pending<r.total_days:raise ConflictError("Insufficient leave balance","LEAVE_BALANCE_INSUFFICIENT")
   if bal:bal.pending+=r.total_days
   r.status=target;r.submitted_at=now
  elif target==LeaveStatus.APPROVED and r.status==LeaveStatus.SUBMITTED:
   if bal:bal.pending-=r.total_days;bal.used+=r.total_days;bal.closing_balance-=r.total_days
   r.status=target;r.approved_by_id=self.actor.id;r.approved_at=now
  elif target==LeaveStatus.REJECTED and r.status==LeaveStatus.SUBMITTED:
   if bal:bal.pending-=r.total_days
   r.status=target;r.rejected_by_id=self.actor.id;r.rejected_at=now;r.rejection_reason=reason
  elif target==LeaveStatus.CANCELLED and r.status in {LeaveStatus.DRAFT,LeaveStatus.SUBMITTED}:
   if bal and r.status==LeaveStatus.SUBMITTED:bal.pending-=r.total_days
   r.status=target;r.cancelled_at=now
  else:raise ConflictError("Invalid leave transition","LEAVE_STATUS_INVALID")
  await self.audit(f"LEAVE_REQUEST_{target.value}","leave_request",r.id,{"reason":reason});return r
class PayrollService(HRBase):
 async def create_run(self,period_id):
  p=await self.s.scalar(select(PayrollPeriod).where(PayrollPeriod.id==period_id,PayrollPeriod.deleted_at.is_(None)))
  if not p:raise NotFoundError("Payroll period not found","PAYROLL_PERIOD_NOT_FOUND")
  if await self.s.scalar(select(PayrollRun).where(PayrollRun.period_id==period_id,PayrollRun.status!=PayrollStatus.CANCELLED)):raise ConflictError("Payroll run exists","PAYROLL_RUN_EXISTS")
  r=PayrollRun(period_id=period_id,run_number=await self.next("payroll","ANI-PAY"),status=PayrollStatus.DRAFT,gross_total=0,deduction_total=0,net_total=0,calculation_snapshot_json={},created_by_id=self.actor.id,updated_by_id=self.actor.id);self.s.add(r);await self.s.flush();await self.audit("PAYROLL_RUN_CREATED","payroll_run",r.id);return r
 async def calculate(self,id):
  r=await self.s.scalar(select(PayrollRun).where(PayrollRun.id==id).with_for_update())
  if not r or r.status not in {PayrollStatus.DRAFT,PayrollStatus.CALCULATED}:raise ConflictError("Payroll cannot be calculated","PAYROLL_STATUS_INVALID")
  p=await self.s.scalar(select(PayrollPeriod).where(PayrollPeriod.id==r.period_id));employees=list((await self.s.scalars(select(Employee).where(Employee.employment_status==EmploymentStatus.ACTIVE,Employee.salary_structure_id.is_not(None),Employee.deleted_at.is_(None)))).all());await self.s.execute(__import__('sqlalchemy').delete(Payslip).where(Payslip.payroll_run_id==r.id));gross=deductions=net=Decimal(0);days=Decimal((p.end_date-p.start_date).days+1)
  for e in employees:
   structure=await self.s.scalar(select(SalaryStructure).where(SalaryStructure.id==e.salary_structure_id));present=Decimal(await self.s.scalar(select(func.count()).select_from(Attendance).where(Attendance.employee_id==e.id,Attendance.attendance_date.between(p.start_date,p.end_date),Attendance.status.in_([AttendanceStatus.PRESENT,AttendanceStatus.LATE]))) or 0);paid_leave=Decimal(await self.s.scalar(select(func.coalesce(func.sum(LeaveRequest.total_days),0)).where(LeaveRequest.employee_id==e.id,LeaveRequest.status==LeaveStatus.APPROVED,LeaveRequest.start_date<=p.end_date,LeaveRequest.end_date>=p.start_date)) or 0);payable=min(days,present+paid_leave);g=money(structure.monthly_ctc*payable/days);d=money(structure.monthly_ctc-g);n=g;self.s.add(Payslip(payroll_run_id=r.id,employee_id=e.id,payable_days=payable,present_days=present,paid_leave_days=paid_leave,unpaid_leave_days=days-payable,gross_salary=g,deductions=d,net_salary=n,snapshot_json={"monthly_ctc":str(structure.monthly_ctc),"period_days":str(days)},created_by_id=self.actor.id,updated_by_id=self.actor.id));gross+=g;deductions+=d;net+=n
  r.gross_total=money(gross);r.deduction_total=money(deductions);r.net_total=money(net);r.status=PayrollStatus.CALCULATED;r.calculation_snapshot_json={"employee_count":len(employees),"calculated_at":utc_now().isoformat()};await self.audit("PAYROLL_CALCULATED","payroll_run",r.id);return r
 async def transition(self,id,target):
  r=await self.s.scalar(select(PayrollRun).where(PayrollRun.id==id).with_for_update())
  allowed={PayrollStatus.CALCULATED:PayrollStatus.APPROVED,PayrollStatus.APPROVED:PayrollStatus.FINALIZED,PayrollStatus.DRAFT:PayrollStatus.CANCELLED,PayrollStatus.CALCULATED:PayrollStatus.APPROVED}
  if not r or allowed.get(r.status)!=target:raise ConflictError("Invalid payroll transition","PAYROLL_STATUS_INVALID")
  r.status=target
  if target==PayrollStatus.APPROVED:r.approved_by_id=self.actor.id
  if target==PayrollStatus.FINALIZED:r.finalized_at=utc_now()
  await self.audit(f"PAYROLL_{target.value}","payroll_run",r.id);return r
class PayslipPDFService:
 root=Path(__file__).resolve().parents[2]/"generated"/"payslips"
 def generate(self,p,e):
  self.root.mkdir(parents=True,exist_ok=True);path=self.root/f"{p.id}.pdf";st=getSampleStyleSheet();story=[Paragraph("<b>ANICRAZE</b>",st["Title"]),Paragraph("PAYSLIP",st["Heading2"]),Paragraph(f"Employee: {e.full_name}<br/>Code: {e.employee_code}",st["BodyText"]),Spacer(1,5*mm),Table([["Payable days",p.payable_days],["Present days",p.present_days],["Paid leave",p.paid_leave_days],["Unpaid leave",p.unpaid_leave_days],["Gross salary",p.gross_salary],["Deductions",p.deductions],["Net salary",p.net_salary]]),Spacer(1,7*mm),Paragraph("Authorized signatory: ____________________",st["BodyText"])];SimpleDocTemplate(str(path),pagesize=A4).build(story);return path
class HRAnalyticsService(HRBase):
 async def dashboard(self):
  total=int(await self.s.scalar(select(func.count()).select_from(Employee).where(Employee.deleted_at.is_(None))) or 0);active=int(await self.s.scalar(select(func.count()).select_from(Employee).where(Employee.employment_status==EmploymentStatus.ACTIVE,Employee.deleted_at.is_(None))) or 0);present=int(await self.s.scalar(select(func.count()).select_from(Attendance).where(Attendance.attendance_date==date.today(),Attendance.status.in_([AttendanceStatus.PRESENT,AttendanceStatus.LATE]))) or 0);late=int(await self.s.scalar(select(func.count()).select_from(Attendance).where(Attendance.attendance_date==date.today(),Attendance.status==AttendanceStatus.LATE)) or 0);pending=int(await self.s.scalar(select(func.count()).select_from(LeaveRequest).where(LeaveRequest.status==LeaveStatus.SUBMITTED)) or 0);pay=Decimal(await self.s.scalar(select(func.coalesce(func.sum(PayrollRun.net_total),0)).where(PayrollRun.status.in_([PayrollStatus.CALCULATED,PayrollStatus.APPROVED,PayrollStatus.FINALIZED]))) or 0);return {"total_employees":total,"active_employees":active,"present_today":present,"absent_today":max(0,active-present),"late_arrivals":late,"pending_leave_requests":pending,"monthly_payroll_estimate":str(pay),"attendance_percentage":round(100*present/active,2) if active else 0,"insights":[f"{pending} leave requests require approval.",f"{late} employees arrived late today."]}
