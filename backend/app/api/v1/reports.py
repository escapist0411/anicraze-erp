import csv, io, re
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from app.pdf.documents import report_pdf
from app.pdf.formatters import format_date
from app.models.inventory import Store, Warehouse
from sqlalchemy import func, select

from app.dependencies.auth import DatabaseSession
from app.exceptions.domain import AuthorizationError, NotFoundError
from app.models.auth import User
from app.models.reports import BusinessTarget, Expense, ExpenseStatus, ExportStatus, ReportExportHistory, ReportFormat, ReportSchedule
from app.models.notifications import Notification, NotificationCategory, NotificationSeverity, ReportDeliveryAttempt
from app.config.settings import get_settings
from app.services.email_service import EmailService
from app.permissions.dependencies import require_any_permission, require_permission
from app.schemas.common import APIResponse
from app.schemas.reports import *
from app.services.reports import ReportingService, resolve_date_range, scoped_store
from app.utils.time import utc_now

dashboard_router=APIRouter(prefix="/dashboard",tags=["Owner dashboard"])
reports_router=APIRouter(prefix="/reports",tags=["Reports"])
expenses_router=APIRouter(prefix="/expenses",tags=["Expenses"])
schedules_router=APIRouter(prefix="/report-schedules",tags=["Report schedules"])

def filters(date_from=None,date_to=None,preset=None,store_id=None,warehouse_id=None,timezone="Asia/Kolkata",compare_with_previous=False): return ReportFilterRequest(date_from=date_from,date_to=date_to,preset=preset,store_id=store_id,warehouse_id=warehouse_id,timezone=timezone,compare_with_previous=compare_with_previous)
def report_dep(): return Depends(require_any_permission("dashboard.read","dashboard.owner","reports.sales.read","reports.inventory.read","reports.finance.read"))

def permission_codes(actor: User) -> set[str]:
 return {p.code for role in actor.roles for p in role.permissions} | {p.code for p in actor.direct_permissions}
def ensure_permission(actor: User, code: str):
 codes=permission_codes(actor)
 if "*" not in codes and code not in codes: raise AuthorizationError("You do not have permission to access this report", "REPORT_PERMISSION_DENIED")
def ensure_management_dashboard(actor: User):
 if not ({r.code for r in actor.roles} & {"OWNER","ADMIN","MANAGER","ACCOUNTANT"}): raise AuthorizationError("The management command center is restricted", "DASHBOARD_MANAGEMENT_ONLY")

@dashboard_router.get("/owner",response_model=APIResponse[dict])
async def owner(session:DatabaseSession,actor:User=Depends(require_any_permission("dashboard.owner","dashboard.read")),date_from:date|None=None,date_to:date|None=None,preset:str|None=None,store_id:UUID|None=None,warehouse_id:UUID|None=None,timezone:str="Asia/Kolkata",compare_with_previous:bool=False):
 ensure_management_dashboard(actor);return APIResponse(data=await ReportingService(session,actor).owner_dashboard(filters(date_from,date_to,preset,store_id,warehouse_id,timezone,compare_with_previous)))

@dashboard_router.get("/{section}",response_model=APIResponse[dict])
async def dashboard_section(section:str,session:DatabaseSession,actor:User=Depends(require_any_permission("dashboard.owner","dashboard.read")),date_from:date|None=None,date_to:date|None=None,preset:str|None=None,store_id:UUID|None=None,warehouse_id:UUID|None=None,timezone:str="Asia/Kolkata"):
 data=await ReportingService(session,actor).owner_dashboard(filters(date_from,date_to,preset,store_id,warehouse_id,timezone)); mapping={"kpis":"kpis","sales-trend":"sales_trend","store-performance":"store_performance","inventory-health":"inventory_summary","finance-summary":"kpis","employee-summary":"active_employees","alerts":"alerts","business-insights":"business_insights"}; key=mapping.get(section)
 return APIResponse(data={key:data.get(key)} if key else {"items":[]})

@reports_router.get("/weekly-business-summary",response_model=APIResponse[dict])
async def weekly(session:DatabaseSession,actor:User=report_dep(),store_id:UUID|None=None,timezone:str="Asia/Kolkata"):
 ensure_management_dashboard(actor);return APIResponse(data=await ReportingService(session,actor).owner_dashboard(filters(preset="THIS_WEEK",store_id=store_id,timezone=timezone)))

@reports_router.get("/export-history",response_model=APIResponse[list[dict]])
async def export_history(session:DatabaseSession,actor:User=Depends(require_any_permission("reports.sales.export","reports.finance.export","reports.inventory.export"))):
 rows=list((await session.scalars(select(ReportExportHistory).where(ReportExportHistory.generated_by==actor.id).order_by(ReportExportHistory.generated_at.desc()).limit(100))).all());return APIResponse(data=[{"id":x.id,"report_type":x.report_type,"format":x.format,"status":x.status,"generated_at":x.generated_at,"file_size":x.file_size} for x in rows])

def safe_cell(value):
 s=str(value if value is not None else ""); return "'"+s if s[:1] in "=+-@" else s
def file_response(report_type:str,fmt:ReportFormat,payload:dict):
 stamp=datetime.now().strftime("%Y-%m-%d"); safe=re.sub(r"[^A-Za-z0-9_-]+","_",report_type); rows=payload.get("rows") or [payload.get("summary",{})]
 if fmt==ReportFormat.CSV:
  out=io.StringIO(); keys=list(rows[0].keys()) if rows else []; w=csv.DictWriter(out,fieldnames=keys);w.writeheader();w.writerows([{k:safe_cell(v) for k,v in row.items()} for row in rows]);raw=b"\xef\xbb\xbf"+out.getvalue().encode();mime="text/csv";ext="csv"
 elif fmt==ReportFormat.PDF:
  raw=report_pdf(report_type,payload);mime="application/pdf";ext="pdf"
 else:
  # SpreadsheetML is a standards-compliant Excel-readable workbook without formula evaluation.
  keys=list(rows[0].keys()) if rows else []; body="".join("<Row>"+"".join(f'<Cell><Data ss:Type="String">{safe_cell(row.get(k)).replace("&","&amp;").replace("<","&lt;")}</Data></Cell>' for k in keys)+"</Row>" for row in [dict(zip(keys,keys)),*rows]);raw=(f'<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Worksheet ss:Name="Report"><Table>{body}</Table></Worksheet></Workbook>').encode();mime="application/vnd.ms-excel";ext="xls"
 return raw,mime,f"ANICRAZE_{safe}_{stamp}.{ext}"

async def document_metadata(session, actor, report_filters, domain):
 start,end=resolve_date_range(report_filters)
 sid=scoped_store(actor,report_filters.store_id)
 store=await session.get(Store,sid) if sid else None
 warehouse=await session.get(Warehouse,report_filters.warehouse_id) if domain=="inventory" and report_filters.warehouse_id else None
 location=store.name if store else "All Locations" if domain=="inventory" else "All Shops"
 if warehouse:location+=f" / {warehouse.name}" if store else warehouse.name
 return {"period":f"{format_date(start)} - {format_date(end-timedelta(days=1))}","location":location}

async def export_impl(data:ReportExportRequest,session,actor):
 domain=(data.report_type.split("_",1)[0] or "sales");ensure_permission(actor,f"reports.{domain}.export");report=data.report_type[len(domain)+1:] or "summary";svc=ReportingService(session,actor);payload=await svc.report(domain,report,data.filters)
 if data.format==ReportFormat.PDF:
  payload["document_metadata"]=await document_metadata(session,actor,data.filters,domain)
 raw,mime,name=file_response(data.report_type,data.format,payload);h=ReportExportHistory(report_type=data.report_type,format=data.format,filters_json=data.filters.model_dump(mode="json"),file_path=None,file_url=None,status=ExportStatus.COMPLETED,generated_by=actor.id,generated_at=utc_now(),expires_at=utc_now()+timedelta(days=7),error_message=None,file_size=len(raw),created_by_id=actor.id,updated_by_id=actor.id);session.add(h);await svc.audit("REPORT_EXPORTED",data.report_type,{"format":data.format.value});await session.flush();return StreamingResponse(io.BytesIO(raw),media_type=mime,headers={"Content-Disposition":f'attachment; filename="{name}"',"X-Export-History-Id":str(h.id)})

@reports_router.post("/export")
async def export_post(data:ReportExportRequest,session:DatabaseSession,actor:User=Depends(require_any_permission("reports.sales.export","reports.inventory.export","reports.finance.export"))):return await export_impl(data,session,actor)
@reports_router.get("/export")
async def export_get(session:DatabaseSession,report_type:str,format:ReportFormat,date_from:date|None=None,date_to:date|None=None,store_id:UUID|None=None,actor:User=Depends(require_any_permission("reports.sales.export","reports.inventory.export","reports.finance.export"))):return await export_impl(ReportExportRequest(report_type=report_type,format=format,filters=filters(date_from,date_to,store_id=store_id)),session,actor)

@reports_router.get("/targets",response_model=APIResponse[list[dict]])
async def targets(session:DatabaseSession,actor:User=Depends(require_permission("reports.targets.read"))):
 rows=list((await session.scalars(select(BusinessTarget).where(BusinessTarget.deleted_at.is_(None)))).all());return APIResponse(data=[target_dict(x) for x in rows])
def target_dict(x): return {"id":x.id,"target_type":x.target_type,"store_id":x.store_id,"employee_id":x.employee_id,"period_type":x.period_type,"start_date":x.start_date,"end_date":x.end_date,"target_value":x.target_value,"actual_value":x.actual_value,"status":x.status,"progress_percentage":min(Decimal(100),x.actual_value*100/x.target_value) if x.target_value else Decimal(0),"remaining_value":max(Decimal(0),x.target_value-x.actual_value)}
@reports_router.post("/targets",response_model=APIResponse[dict],status_code=201)
async def create_target(data:BusinessTargetCreateRequest,session:DatabaseSession,actor:User=Depends(require_permission("reports.targets.manage"))):x=BusinessTarget(**data.model_dump(),actual_value=0,status="ACTIVE",created_by_id=actor.id,updated_by_id=actor.id);session.add(x);await session.flush();return APIResponse(data=target_dict(x))
@reports_router.patch("/targets/{id}",response_model=APIResponse[dict])
async def update_target(id:UUID,data:BusinessTargetUpdateRequest,session:DatabaseSession,actor:User=Depends(require_permission("reports.targets.manage"))):
 x=await session.get(BusinessTarget,id)
 if not x:raise NotFoundError("Target not found","TARGET_NOT_FOUND")
 for k,v in data.model_dump(exclude_unset=True).items():setattr(x,k,v)
 x.updated_by_id=actor.id;await session.flush();return APIResponse(data=target_dict(x))
@reports_router.delete("/targets/{id}",status_code=204)
async def delete_target(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("reports.targets.manage"))):
 x=await session.get(BusinessTarget,id)
 if not x:raise NotFoundError("Target not found","TARGET_NOT_FOUND")
 x.deleted_at=utc_now()

@reports_router.get("/{domain}/{report}",response_model=APIResponse[dict])
async def generic_report(domain:str,report:str,session:DatabaseSession,actor:User=report_dep(),date_from:date|None=None,date_to:date|None=None,preset:str|None=None,store_id:UUID|None=None,warehouse_id:UUID|None=None,timezone:str="Asia/Kolkata",compare_with_previous:bool=False):
 ensure_permission(actor,f"reports.{domain}.read");return APIResponse(data=await ReportingService(session,actor).report(domain,report,filters(date_from,date_to,preset,store_id,warehouse_id,timezone,compare_with_previous)))

@expenses_router.get("",response_model=APIResponse[list[dict]])
async def list_expenses(session:DatabaseSession,actor:User=Depends(require_permission("expenses.read")),store_id:UUID|None=None):
 sid=scoped_store(actor,store_id);q=select(Expense).where(Expense.deleted_at.is_(None));q=q.where(Expense.store_id==sid) if sid else q;rows=list((await session.scalars(q.order_by(Expense.expense_date.desc()))).all());return APIResponse(data=[expense_dict(x) for x in rows])
def expense_dict(x):return {"id":x.id,"expense_number":x.expense_number,"expense_date":x.expense_date,"category":x.category,"description":x.description,"amount":x.amount,"store_id":x.store_id,"status":x.status,"approved_at":x.approved_at}
@expenses_router.post("",response_model=APIResponse[dict],status_code=201)
async def create_expense(data:ExpenseCreateRequest,session:DatabaseSession,actor:User=Depends(require_permission("expenses.create"))):
 sid=scoped_store(actor,data.store_id);n=(await session.scalar(select(func.count(Expense.id))))+1;x=Expense(**data.model_dump(exclude={"store_id"}),gst_amount=0,store_id=sid,expense_number=f"EXP-{datetime.now().year}-{n:06d}",status=ExpenseStatus.DRAFT,created_by_id=actor.id,updated_by_id=actor.id);session.add(x);await session.flush();return APIResponse(data=expense_dict(x))
@expenses_router.patch("/{id}",response_model=APIResponse[dict])
async def update_expense(id:UUID,data:ExpenseUpdateRequest,session:DatabaseSession,actor:User=Depends(require_permission("expenses.update"))):
 x=await session.get(Expense,id)
 if not x:raise NotFoundError("Expense not found","EXPENSE_NOT_FOUND")
 scoped_store(actor,x.store_id)
 for k,v in data.model_dump(exclude_unset=True).items():setattr(x,k,v)
 x.updated_by_id=actor.id;await session.flush();return APIResponse(data=expense_dict(x))
@expenses_router.get("/{id}",response_model=APIResponse[dict])
async def get_expense(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("expenses.read"))):
 x=await session.get(Expense,id)
 if not x or x.deleted_at:raise NotFoundError("Expense not found","EXPENSE_NOT_FOUND")
 scoped_store(actor,x.store_id);return APIResponse(data=expense_dict(x))
@expenses_router.delete("/{id}",status_code=204)
async def delete_expense(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("expenses.delete"))):
 x=await session.get(Expense,id)
 if not x:raise NotFoundError("Expense not found","EXPENSE_NOT_FOUND")
 scoped_store(actor,x.store_id)
 x.deleted_at=utc_now()
@expenses_router.post("/{id}/approve",response_model=APIResponse[dict])
async def approve_expense(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("expenses.approve"))):
 x=await session.get(Expense,id)
 if not x:raise NotFoundError("Expense not found","EXPENSE_NOT_FOUND")
 scoped_store(actor,x.store_id)
 x.status=ExpenseStatus.APPROVED;x.approved_by_id=actor.id;x.approved_at=utc_now();await session.flush();return APIResponse(data=expense_dict(x))

def schedule_dict(x):return {"id":x.id,"name":x.name,"report_type":x.report_type,"format":x.format,"filters_json":x.filters_json,"frequency":x.frequency,"day_of_week":x.day_of_week,"day_of_month":x.day_of_month,"time_of_day":x.time_of_day,"timezone":x.timezone,"recipient_emails_json":x.recipient_emails_json,"is_active":x.is_active,"last_run_at":x.last_run_at,"next_run_at":x.next_run_at}
@schedules_router.get("",response_model=APIResponse[list[dict]])
async def schedules(session:DatabaseSession,actor:User=Depends(require_permission("reports.schedules.read"))):return APIResponse(data=[schedule_dict(x) for x in (await session.scalars(select(ReportSchedule).where(ReportSchedule.deleted_at.is_(None)))).all()])
@schedules_router.post("",response_model=APIResponse[dict],status_code=201)
async def create_schedule(data:ReportScheduleCreateRequest,session:DatabaseSession,actor:User=Depends(require_permission("reports.schedules.create"))):x=ReportSchedule(**data.model_dump(mode="python"),created_by_id=actor.id,updated_by_id=actor.id);x.next_run_at=utc_now()+timedelta(days=1 if data.frequency.value=="DAILY" else 7 if data.frequency.value=="WEEKLY" else 30);session.add(x);await session.flush();return APIResponse(data=schedule_dict(x))
@schedules_router.post("/{id}/run-now",response_model=APIResponse[dict])
async def run_schedule(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("reports.schedules.run"))):
 x=await session.get(ReportSchedule,id)
 if not x:raise NotFoundError("Schedule not found","SCHEDULE_NOT_FOUND")
 now=utc_now();x.last_run_at=now;x.next_run_at=now+timedelta(days=1 if x.frequency.value=="DAILY" else 7 if x.frequency.value=="WEEKLY" else 30)
 try:
  raw_filters=dict(x.filters_json or {});raw_filters.setdefault("preset","THIS_WEEK");report_filters=ReportFilterRequest(**raw_filters);dashboard=await ReportingService(session,actor).owner_dashboard(report_filters);start,end=resolve_date_range(report_filters)
  rows=[{"section":"Business Summary","metric":"Net Sales","value":dashboard["kpis"]["net_sales"]},{"section":"Business Summary","metric":"Gross Profit","value":dashboard["kpis"]["gross_profit"]},{"section":"Business Summary","metric":"Estimated Operating Profit","value":dashboard["kpis"]["estimated_net_operating_profit"]},{"section":"Business Summary","metric":"Bills","value":dashboard["kpis"]["orders"]},{"section":"Business Summary","metric":"Average Bill","value":dashboard["kpis"]["average_order_value"]},{"section":"Inventory","metric":"Inventory Value","value":dashboard["inventory_summary"]["inventory_value"]},{"section":"Inventory","metric":"Low Stock","value":dashboard["inventory_summary"]["low_stock_count"]},{"section":"Inventory","metric":"Out of Stock","value":dashboard["inventory_summary"]["out_of_stock_count"]}]
  rows += [{"section":"Store Performance","metric":s["store_name"],"value":s["net_sales"]} for s in dashboard["store_performance"]]
  rows += [{"section":"Payments","metric":p["payment_method"],"value":p["amount"]} for p in dashboard["payment_summary"]]
  raw,_,_=file_response("weekly_owner_report",ReportFormat.PDF,{"dashboard":dashboard,"document_metadata":await document_metadata(session,actor,report_filters,"weekly")});filename=f'ANICRAZE_Weekly_Report_{start.strftime("%d")}-{(end-timedelta(days=1)).strftime("%d_%b_%Y")}.pdf';folder=Path("generated/reports");folder.mkdir(parents=True,exist_ok=True);path=folder/f'{now.strftime("%Y%m%dT%H%M%S")}_{filename}';path.write_bytes(raw)
  history=ReportExportHistory(report_type="weekly_owner_report",format=ReportFormat.PDF,filters_json=report_filters.model_dump(mode="json"),file_path=str(path),file_url=f"/reports/history/{{id}}/download",status=ExportStatus.COMPLETED,generated_by=actor.id,generated_at=now,expires_at=None,error_message=None,file_size=len(raw),created_by_id=actor.id,updated_by_id=actor.id);session.add(history);await session.flush();history.file_url=f"/reports/history/{history.id}/download"
  recipients=list(x.recipient_emails_json or []);settings=get_settings()
  if not recipients and settings.owner_report_email:recipients=[settings.owner_report_email]
  email_results=[]
  for recipient in recipients:
   result=await EmailService().send_report(str(recipient),f'ANICRAZE Weekly Business Report — {start.strftime("%d %b")}–{(end-timedelta(days=1)).strftime("%d %b %Y")}',f'Hello,\n\nYour ANICRAZE weekly business report is ready.\n\nNet Sales: ₹{dashboard["kpis"]["net_sales"]}\nGross Profit: ₹{dashboard["kpis"]["gross_profit"]}\nBills: {dashboard["kpis"]["orders"]}\n\nThe complete report is attached.\n\nANICRAZE ERP',filename,raw);email_results.append({"recipient":str(recipient),**result});session.add(ReportDeliveryAttempt(report_export_id=history.id,schedule_id=x.id,recipient=str(recipient),status=result["status"],provider=result["provider"],sent_at=now if result["status"]=="SENT" else None,failure_reason=result["failure_reason"],created_by_id=actor.id,updated_by_id=actor.id))
  email_status="DISABLED" if not recipients else "SENT" if all(r["status"]=="SENT" for r in email_results) else "FAILED"
  session.add(Notification(user_id=actor.id,category=NotificationCategory.REPORT,severity=NotificationSeverity.INFO if email_status in {"SENT","DISABLED"} else NotificationSeverity.WARNING,title="Weekly report ready",message=f"ANICRAZE Weekly Report {start.strftime('%d %b')}–{(end-timedelta(days=1)).strftime('%d %b %Y')} was generated. Email: {email_status}.",entity_type="REPORT_EXPORT",entity_id=history.id,action_path="reports",dedupe_key=f"report:weekly:{history.id}",created_by_id=actor.id,updated_by_id=actor.id));await session.flush();return APIResponse(data={"schedule":schedule_dict(x),"report":{"status":"SUCCESS","history_id":history.id,"filename":filename,"download_url":history.file_url},"email":{"status":email_status,"attempts":email_results}})
 except Exception as exc:
  session.add(Notification(user_id=actor.id,category=NotificationCategory.REPORT,severity=NotificationSeverity.HIGH,title="Report failed",message="Weekly Owner Report could not be generated.",entity_type="REPORT_SCHEDULE",entity_id=x.id,action_path="reports",dedupe_key=f"report:failed:{x.id}:{now.date()}",created_by_id=actor.id,updated_by_id=actor.id));await session.flush();return APIResponse(data={"schedule":schedule_dict(x),"report":{"status":"FAILED","reason":str(exc)[:500]},"email":{"status":"NOT_ATTEMPTED","attempts":[]}})

@reports_router.get("/history/{id}/download")
async def download_history(id:UUID,session:DatabaseSession,actor:User=Depends(require_any_permission("reports.finance.read","reports.schedules.read"))):
 row=await session.get(ReportExportHistory,id)
 if not row or row.generated_by!=actor.id or not row.file_path:raise NotFoundError("Report file not found","REPORT_FILE_NOT_FOUND")
 path=Path(row.file_path)
 if not path.is_file():raise NotFoundError("Report file not found","REPORT_FILE_NOT_FOUND")
 return StreamingResponse(io.BytesIO(path.read_bytes()),media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{path.name.split("_",1)[-1]}"'})
@schedules_router.get("/{id}",response_model=APIResponse[dict])
async def get_schedule(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("reports.schedules.read"))):
 x=await session.get(ReportSchedule,id)
 if not x or x.deleted_at:raise NotFoundError("Schedule not found","SCHEDULE_NOT_FOUND")
 return APIResponse(data=schedule_dict(x))
@schedules_router.patch("/{id}",response_model=APIResponse[dict])
async def update_schedule(id:UUID,data:ReportScheduleUpdateRequest,session:DatabaseSession,actor:User=Depends(require_permission("reports.schedules.update"))):
 x=await session.get(ReportSchedule,id)
 if not x:raise NotFoundError("Schedule not found","SCHEDULE_NOT_FOUND")
 for k,v in data.model_dump(exclude_unset=True).items():setattr(x,k,v)
 x.updated_by_id=actor.id;await session.flush();return APIResponse(data=schedule_dict(x))
@schedules_router.delete("/{id}",status_code=204)
async def delete_schedule(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("reports.schedules.delete"))):
 x=await session.get(ReportSchedule,id)
 if not x:raise NotFoundError("Schedule not found","SCHEDULE_NOT_FOUND")
 x.deleted_at=utc_now()
