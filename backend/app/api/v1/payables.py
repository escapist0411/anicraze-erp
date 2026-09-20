from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from app.dependencies.auth import DatabaseSession
from app.models.auth import User
from app.models.payables import PayableStatus
from app.permissions.dependencies import require_owner
from app.schemas.common import APIResponse
from app.schemas.payables import *
from app.services.payables import PayableService

router=APIRouter(prefix="/purchase-payables",tags=["Owner purchase payments"])
def svc(session,actor,request):return PayableService(session,actor,request.client.host if request.client else None,request.headers.get("user-agent"))
@router.get("",response_model=APIResponse[list[PayableResponse]])
async def list_payables(request:Request,session:DatabaseSession,status:PayableStatus|None=None,actor:User=Depends(require_owner)):return APIResponse(data=await svc(session,actor,request).list(status))
@router.post("",response_model=APIResponse[PayableResponse],status_code=201)
async def create_payable(data:PayableCreate,request:Request,session:DatabaseSession,actor:User=Depends(require_owner)):return APIResponse(data=await svc(session,actor,request).create(data))
@router.get("/summary",response_model=APIResponse[PayableSummary])
async def payable_summary(request:Request,session:DatabaseSession,actor:User=Depends(require_owner)):return APIResponse(data=await svc(session,actor,request).summary())
@router.post("/reconcile-reminders",response_model=APIResponse[dict])
async def reconcile(request:Request,session:DatabaseSession,actor:User=Depends(require_owner)):return APIResponse(data={"triggered":await svc(session,actor,request).reconcile_due_reminders()})
@router.get("/{payable_id}",response_model=APIResponse[PayableResponse])
async def payable(payable_id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_owner)):service=svc(session,actor,request);return APIResponse(data=service.response(await service.get(payable_id)))
@router.patch("/{payable_id}",response_model=APIResponse[PayableResponse])
async def update_payable(payable_id:UUID,data:PayableUpdate,request:Request,session:DatabaseSession,actor:User=Depends(require_owner)):return APIResponse(data=await svc(session,actor,request).update(payable_id,data))
@router.post("/{payable_id}/payments",response_model=APIResponse[PayableResponse])
async def record_payment(payable_id:UUID,data:PaymentCreate,request:Request,session:DatabaseSession,actor:User=Depends(require_owner)):return APIResponse(data=await svc(session,actor,request).record_payment(payable_id,data))
@router.post("/{payable_id}/reminders",response_model=APIResponse[PayableResponse])
async def schedule_reminder(payable_id:UUID,data:ReminderCreate,request:Request,session:DatabaseSession,actor:User=Depends(require_owner)):return APIResponse(data=await svc(session,actor,request).schedule_reminder(payable_id,data.remind_at))
@router.post("/{payable_id}/reminders/{reminder_id}/dismiss",response_model=APIResponse[PayableResponse])
async def dismiss_reminder(payable_id:UUID,reminder_id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_owner)):return APIResponse(data=await svc(session,actor,request).dismiss_reminder(payable_id,reminder_id))
