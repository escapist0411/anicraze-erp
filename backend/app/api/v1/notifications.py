from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.dependencies.auth import DatabaseSession
from app.models.auth import User
from app.models.notifications import NotificationCategory
from app.permissions.dependencies import require_any_permission
from app.schemas.common import APIResponse
from app.services.notifications import NotificationService, notification_dict
from app.exceptions.domain import AuthorizationError

router=APIRouter(prefix="/notifications",tags=["Notifications"])
dep=Depends(require_any_permission("dashboard.owner","dashboard.read"))
def management(actor:User):
    if not ({r.code for r in actor.roles}&{"OWNER","ADMIN","MANAGER","ACCOUNTANT"}):raise AuthorizationError("Notification Center is restricted to management", "NOTIFICATIONS_MANAGEMENT_ONLY")

@router.get("",response_model=APIResponse[list[dict]])
async def list_notifications(session:DatabaseSession,actor:User=dep,category:NotificationCategory|None=None,unread:bool=False,limit:int=Query(100,ge=1,le=200)):
    management(actor);rows=await NotificationService(session,actor).list(category,unread,limit);return APIResponse(data=[notification_dict(x) for x in rows])
@router.get("/summary",response_model=APIResponse[dict])
async def summary(session:DatabaseSession,actor:User=dep):
    management(actor);rows=await NotificationService(session,actor).list();return APIResponse(data={"unread_count":sum(not x.is_read for x in rows),"active_count":len(rows),"critical_count":sum(x.severity.value in {"HIGH","CRITICAL"} for x in rows),"warning_count":sum(x.severity.value=="WARNING" for x in rows),"recent":[notification_dict(x) for x in rows[:5]]})
@router.post("/{id}/read",response_model=APIResponse[dict])
async def mark_read(id:UUID,session:DatabaseSession,actor:User=dep):management(actor);return APIResponse(data=notification_dict(await NotificationService(session,actor).mark_read(id)))
@router.post("/mark-all-read",response_model=APIResponse[dict])
async def mark_all_read(session:DatabaseSession,actor:User=dep):management(actor);return APIResponse(data={"updated":await NotificationService(session,actor).mark_all_read()})
