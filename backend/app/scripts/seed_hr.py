import asyncio
from calendar import monthrange
from datetime import date,datetime,time,timedelta,timezone
from decimal import Decimal
from sqlalchemy import func,select
from app.database.session import AsyncSessionFactory
from app.models.auth import User
from app.models.hr import *
from app.models.inventory import Store,Warehouse
from app.schemas.hr import EmployeeCreateRequest
from app.services.hr import EmployeeService,PayrollService
from app.utils.time import utc_now
DEPTS=["Management","Sales","Billing","Inventory","Warehouse","Accounts","Human Resources","Operations"]
DESIG=["Owner","Store Manager","Accountant","Inventory Manager","Billing Executive","Sales Associate","Warehouse Assistant","HR Executive"]
NAMES=[("Aarav","Shah"),("Diya","Patel"),("Vivaan","Mehta"),("Anaya","Joshi"),("Arjun","Rao"),("Ishita","Nair"),("Kabir","Desai"),("Meera","Kapoor"),("Rohan","Sen"),("Sara","Iyer"),("Dev","Malhotra"),("Tara","Sharma"),("Neil","Verma"),("Maya","Gupta"),("Kiran","Bose")]
async def seed():
 async with AsyncSessionFactory() as s:
  owner=await s.scalar(select(User).where(User.email=="owner@anicraze.com"));stores=list((await s.scalars(select(Store).where(Store.deleted_at.is_(None)).order_by(Store.code))).all());warehouse=await s.scalar(select(Warehouse).order_by(Warehouse.code));departments=[]
  for name in DEPTS:
   code=name.upper().replace(" ","_");x=await s.scalar(select(Department).where(Department.code==code))
   if not x:x=Department(name=name,code=code,is_active=True,created_by_id=owner.id,updated_by_id=owner.id);s.add(x);await s.flush()
   departments.append(x)
  designations=[]
  for i,name in enumerate(DESIG):
   code=name.upper().replace(" ","_");x=await s.scalar(select(Designation).where(Designation.code==code))
   if not x:x=Designation(name=name,code=code,department_id=departments[i].id,level=i+1,is_active=True,created_by_id=owner.id,updated_by_id=owner.id);s.add(x);await s.flush()
   designations.append(x)
  shifts=[]
  for name,start,end in (("Morning",time(9),time(18)),("Afternoon",time(12),time(21)),("Evening",time(15),time(23)),("General",time(10),time(19))):
   x=await s.scalar(select(Shift).where(Shift.code==name.upper()))
   if not x:x=Shift(name=name,code=name.upper(),start_time=start,end_time=end,break_minutes=60,grace_minutes=10,half_day_minutes=240,full_day_minutes=480,overtime_after_minutes=480,crosses_midnight=False,is_flexible=False,is_active=True,created_by_id=owner.id,updated_by_id=owner.id);s.add(x);await s.flush()
   shifts.append(x)
  leaves=[]
  for code,days,paid in (("CASUAL",12,True),("SICK",10,True),("EARNED",15,True),("UNPAID",365,False),("MATERNITY",180,True),("PATERNITY",15,True),("COMPENSATORY",10,True)):
   x=await s.scalar(select(LeaveType).where(LeaveType.code==code))
   if not x:x=LeaveType(name=code.title(),code=code,annual_entitlement=days,carry_forward_allowed=code=="EARNED",maximum_carry_forward=5,requires_document=code in {"SICK","MATERNITY"},minimum_notice_days=0,paid=paid,is_active=True,created_by_id=owner.id,updated_by_id=owner.id);s.add(x);await s.flush()
   leaves.append(x)
  if not await s.scalar(select(Holiday)):s.add_all([Holiday(name="Independence Day",holiday_date=date(date.today().year,8,15),holiday_type="NATIONAL",is_optional=False,created_by_id=owner.id,updated_by_id=owner.id),Holiday(name="Diwali",holiday_date=date(date.today().year,11,8),holiday_type="COMPANY",is_optional=False,created_by_id=owner.id,updated_by_id=owner.id)])
  structure=await s.scalar(select(SalaryStructure).where(SalaryStructure.code=="RETAIL_STANDARD"))
  if not structure:structure=SalaryStructure(name="Retail Standard",code="RETAIL_STANDARD",description="Demo monthly CTC structure",effective_from=date(date.today().year,1,1),is_active=True,monthly_ctc=Decimal("35000"),created_by_id=owner.id,updated_by_id=owner.id);s.add(structure);await s.flush()
  for name,code,kind,value in (("Basic","BASIC",ComponentType.EARNING,20000),("House Rent Allowance","HRA",ComponentType.EARNING,10000),("Special Allowance","SPECIAL",ComponentType.EARNING,5000),("Provident Fund","PF",ComponentType.DEDUCTION,1800)):
   if not await s.scalar(select(SalaryComponent).where(SalaryComponent.code==code)):s.add(SalaryComponent(name=name,code=code,component_type=kind,calculation_type=CalculationType.FIXED,default_value=value,taxable=kind==ComponentType.EARNING,affects_gross=kind==ComponentType.EARNING,affects_net=True,is_active=True,created_by_id=owner.id,updated_by_id=owner.id))
  es=EmployeeService(s,owner);employees=[];users=list((await s.scalars(select(User).where(User.deleted_at.is_(None)).order_by(User.created_at))).all())
  for i,(first,last) in enumerate(NAMES):
   email=f"employee{i+1}@anicraze.demo";e=await s.scalar(select(Employee).where(Employee.email==email))
   if not e:
    use_store=i%6!=5;e=await es.create(EmployeeCreateRequest(first_name=first,last_name=last,email=email,phone=f"97000{i:05d}",joining_date=date.today()-timedelta(days=180+i*10),department_id=departments[i%len(departments)].id,designation_id=designations[i%len(designations)].id,store_id=stores[i%len(stores)].id if use_store else None,warehouse_id=None if use_store else warehouse.id,shift_id=shifts[i%len(shifts)].id));e.salary_structure_id=structure.id
    if i<len(users) and not await s.scalar(select(Employee).where(Employee.user_id==users[i].id)):e.user_id=users[i].id
   employees.append(e)
  await s.flush()
  start=date.today().replace(day=1)
  for e in employees:
   for offset in range((date.today()-start).days+1):
    day=start+timedelta(days=offset)
    if day.weekday()<6 and not await s.scalar(select(Attendance).where(Attendance.employee_id==e.id,Attendance.attendance_date==day)):
     ci=datetime.combine(day,time(9,5),tzinfo=timezone.utc);co=ci+timedelta(hours=9);s.add(Attendance(employee_id=e.id,attendance_date=day,store_id=e.store_id,warehouse_id=e.warehouse_id,check_in_at=ci,check_out_at=co,worked_minutes=480,break_minutes=60,overtime_minutes=0,late_minutes=0,early_exit_minutes=0,status=AttendanceStatus.PRESENT,source=AttendanceSource.SYSTEM,correction_status=CorrectionStatus.NONE,created_by_id=owner.id,updated_by_id=owner.id))
   for lt in leaves:
    if not await s.scalar(select(LeaveBalance).where(LeaveBalance.employee_id==e.id,LeaveBalance.leave_type_id==lt.id,LeaveBalance.year==date.today().year)):s.add(LeaveBalance(employee_id=e.id,leave_type_id=lt.id,year=date.today().year,opening_balance=lt.annual_entitlement,accrued=0,used=0,pending=0,adjusted=0,closing_balance=lt.annual_entitlement,created_by_id=owner.id,updated_by_id=owner.id))
  await s.flush()
  if not await s.scalar(select(PerformanceReview)):
   for e in employees[:5]:s.add(PerformanceReview(employee_id=e.id,review_period_start=start,review_period_end=date.today(),attendance_score=90,sales_score=80,task_score=85,customer_feedback_score=88,overall_score=Decimal("85.75"),rating="EXCEEDS_EXPECTATIONS",strengths="Customer service",improvement_areas="Product training",status=PerformanceStatus.DRAFT,created_by_id=owner.id,updated_by_id=owner.id));s.add(Goal(employee_id=e.id,title="Monthly sales growth",metric_type="REVENUE",target_value=100000,current_value=40000,start_date=start,due_date=start+timedelta(days=30),priority="HIGH",status=WorkStatus.IN_PROGRESS,created_by_id=owner.id,updated_by_id=owner.id));s.add(Task(assigned_to_employee_id=e.id,title="Complete product training",priority="NORMAL",due_at=utc_now()+timedelta(days=14),status=WorkStatus.TODO,progress_percentage=0,created_by_id=owner.id,updated_by_id=owner.id))
  period=await s.scalar(select(PayrollPeriod).where(PayrollPeriod.name==date.today().strftime("%B %Y")))
  if not period:period=PayrollPeriod(name=date.today().strftime("%B %Y"),start_date=start,end_date=date(start.year,start.month,monthrange(start.year,start.month)[1]),payment_date=date(start.year,start.month,monthrange(start.year,start.month)[1]),status=PayrollStatus.DRAFT,created_by_id=owner.id,updated_by_id=owner.id);s.add(period);await s.flush()
  if not await s.scalar(select(PayrollRun).where(PayrollRun.period_id==period.id)):r=await PayrollService(s,owner).create_run(period.id);await PayrollService(s,owner).calculate(r.id)
  await s.commit()
if __name__=="__main__":asyncio.run(seed())
