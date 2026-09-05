from uuid import UUID
from fastapi import APIRouter,Depends,Query,Request,Response
from fastapi.responses import FileResponse
from sqlalchemy import delete,func,or_,select
from app.dependencies.auth import DatabaseSession
from app.exceptions.domain import ConflictError,NotFoundError
from app.models.auth import AuditLog,User
from app.models.billing import Customer,Invoice,Refund,Return
from app.models.crm import *
from app.permissions.dependencies import require_permission
from app.schemas.common import APIResponse
from app.schemas.crm import *
from app.schemas.billing import ReturnCreate,ReturnItemInput
from app.services.billing import InvoicePDFService,ReturnService
from app.services.crm import *
from app.services.communications import CommunicationService,valid_meta_signature
from app.config.settings import get_settings
from app.middleware.rate_limit import rate_limiter
from uuid import uuid4
from app.services.procurement import ProcurementPDFService
router=APIRouter(tags=["Customer CRM"])
def svc(c,s,a,r): return c(s,a,r.client.host if r.client else None,r.headers.get("user-agent"))
@router.get("/customers/lookup",response_model=APIResponse[CustomerResponse|None])
async def lookup(request:Request,session:DatabaseSession,mobile:str|None=None,email:str|None=None,customer_code:str|None=None,gst_number:str|None=None,actor:User=Depends(require_permission("customers.read"))):
 rows=await svc(CustomerService,session,actor,request).rows(mobile or email or customer_code or gst_number); return APIResponse(data=svc(CustomerService,session,actor,request).response(*rows[0]) if rows else None)
@router.get("/customers",response_model=APIResponse[list[CustomerResponse]])
async def customers(request:Request,session:DatabaseSession,search:str|None=None,actor:User=Depends(require_permission("customers.read"))):
 s=svc(CustomerService,session,actor,request); return APIResponse(data=[s.response(*x) for x in await s.rows(search)])
@router.post("/customers",response_model=APIResponse[CustomerResponse],status_code=201)
async def create_customer(data:CustomerCreateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("customers.create"))): s=svc(CustomerService,session,actor,request); c,p=await s.create(data); return APIResponse(data=s.response(c,p))
@router.get("/customers/{id}",response_model=APIResponse[CustomerResponse])
async def customer(id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("customers.read"))):
 row=(await session.execute(select(Customer,CustomerProfile).join(CustomerProfile).where(Customer.id==id,Customer.deleted_at.is_(None)))).first()
 if not row: raise NotFoundError("Customer not found","CUSTOMER_NOT_FOUND")
 return APIResponse(data=svc(CustomerService,session,actor,request).response(*row))
@router.get("/customers/{id}/loyalty/transactions",response_model=APIResponse[list[LoyaltyTransactionResponse]])
async def customer_loyalty_transactions(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("loyalty.read"))): return APIResponse(data=list((await session.scalars(select(LoyaltyTransaction).where(LoyaltyTransaction.customer_id==id).order_by(LoyaltyTransaction.created_at.desc()))).all()))
@router.get("/customers/{id}/memberships",response_model=APIResponse[list[CustomerMembershipResponse]])
async def customer_memberships(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("memberships.read"))): return APIResponse(data=list((await session.scalars(select(CustomerMembership).where(CustomerMembership.customer_id==id,CustomerMembership.deleted_at.is_(None)).order_by(CustomerMembership.started_at.desc()))).all()))
@router.get("/customers/{id}/store-credit",response_model=APIResponse[dict])
async def customer_store_credit(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("customers.read"))):
 rows=list((await session.scalars(select(StoreCreditLedger).where(StoreCreditLedger.customer_id==id).order_by(StoreCreditLedger.created_at.desc()))).all());return APIResponse(data={"balance":str(rows[0].balance_after if rows else 0),"transactions":[{"id":str(x.id),"type":x.transaction_type,"amount":str(x.amount),"balance_after":str(x.balance_after),"description":x.description,"created_at":x.created_at.isoformat()} for x in rows]})
@router.get("/customers/{id}/notes",response_model=APIResponse[list[dict]])
async def customer_notes(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("customers.manage_notes"))):
 rows=list((await session.scalars(select(CustomerNote).where(CustomerNote.customer_id==id,CustomerNote.deleted_at.is_(None)).order_by(CustomerNote.created_at.desc()))).all());return APIResponse(data=[{"id":str(x.id),"note_type":x.note_type,"content":x.content,"author_id":str(x.created_by_id) if x.created_by_id else None,"created_at":x.created_at.isoformat()} for x in rows])
@router.post("/customers/{id}/notes",response_model=APIResponse[dict],status_code=201)
async def add_customer_note(id:UUID,data:dict,session:DatabaseSession,actor:User=Depends(require_permission("customers.manage_notes"))):
 content=str(data.get("content","")).strip()
 if len(content)<2:raise ConflictError("Note content is required","CUSTOMER_NOTE_INVALID")
 x=CustomerNote(customer_id=id,note_type=str(data.get("note_type","GENERAL"))[:30],content=content,is_internal=True,created_by_id=actor.id,updated_by_id=actor.id);session.add(x);await session.flush();return APIResponse(data={"id":str(x.id),"content":x.content,"created_at":x.created_at.isoformat()})
@router.patch("/customers/{id}",response_model=APIResponse[CustomerResponse])
async def update_customer(id:UUID,data:CustomerUpdateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("customers.update"))): s=svc(CustomerService,session,actor,request);return APIResponse(data=s.response(*await s.update(id,data)))
@router.patch("/customers/{id}/status",response_model=APIResponse[CustomerResponse])
async def customer_status(id:UUID,data:CustomerStatusUpdateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("customers.update_status"))): s=svc(CustomerService,session,actor,request);return APIResponse(data=s.response(*await s.status(id,data.status,data.reason)))
@router.delete("/customers/{id}",status_code=204)
async def delete_customer(id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("customers.delete"))):await svc(CustomerService,session,actor,request).delete(id);return Response(status_code=204)
@router.get("/customers/{id}/invoices",response_model=APIResponse[list[dict]])
@router.get("/customers/{id}/orders",response_model=APIResponse[list[dict]])
async def orders(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("customers.read"))):
 rows=list((await session.scalars(select(Invoice).where(Invoice.customer_id==id).order_by(Invoice.created_at.desc()))).all()); return APIResponse(data=[{"id":str(x.id),"invoice_number":x.invoice_number,"date":x.created_at.isoformat(),"store_id":str(x.store_id),"subtotal":str(x.subtotal),"discount":str(x.discount),"gst":str(x.gst_total),"total":str(x.grand_total),"status":x.invoice_status.value} for x in rows])
@router.get("/customers/{id}/returns",response_model=APIResponse[list[dict]])
async def customer_returns(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("sales_returns.read"))):
 rows=(await session.execute(select(Return).join(Invoice,Return.invoice_id==Invoice.id).where(Invoice.customer_id==id))).scalars().all(); return APIResponse(data=[{"id":str(x.id),"return_number":x.return_number,"amount":str(x.total_amount),"status":x.status.value} for x in rows])
@router.get("/customers/{id}/refunds",response_model=APIResponse[list[dict]])
async def customer_refunds(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("customer_refunds.read"))):
 rows=(await session.execute(select(Refund).join(Return,Refund.return_id==Return.id).join(Invoice,Return.invoice_id==Invoice.id).where(Invoice.customer_id==id))).scalars().all(); return APIResponse(data=[{"id":str(x.id),"refund_number":x.refund_number,"amount":str(x.amount),"status":x.status.value} for x in rows])
@router.get("/customers/{id}/statement",response_model=APIResponse[dict])
async def statement(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("customers.view_statement"))):
 inv=list((await session.scalars(select(Invoice).where(Invoice.customer_id==id))).all()); entries=[]
 for x in inv: entries.append({"date":x.created_at.isoformat(),"type":"INVOICE","reference":x.invoice_number,"amount":str(x.grand_total)})
 return APIResponse(data={"customer_id":str(id),"opening_balance":"0.00","entries":sorted(entries,key=lambda x:x["date"]),"closing_balance":"0.00"})
@router.get("/customers/{id}/loyalty",response_model=APIResponse[LoyaltyAccountResponse])
async def loyalty(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("loyalty.read"))):
 a=await session.scalar(select(LoyaltyAccount).where(LoyaltyAccount.customer_id==id,LoyaltyAccount.deleted_at.is_(None)))
 if not a: raise NotFoundError("Loyalty account not found","LOYALTY_ACCOUNT_NOT_FOUND")
 return APIResponse(data=a)
@router.post("/customers/{id}/loyalty/adjust",response_model=APIResponse[LoyaltyTransactionResponse])
async def adjust_customer(id:UUID,data:LoyaltyAdjustmentRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("loyalty.adjust"))): return APIResponse(data=await svc(LoyaltyService,session,actor,request).adjust(id,data.points,data.description))
@router.post("/customers/{id}/membership",response_model=APIResponse[CustomerMembershipResponse])
@router.patch("/customers/{id}/membership",response_model=APIResponse[CustomerMembershipResponse])
async def membership(id:UUID,data:MembershipAssignmentRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("memberships.assign"))): return APIResponse(data=await svc(MembershipService,session,actor,request).assign(id,data))
@router.get("/customers/{id}/analytics",response_model=APIResponse[dict])
async def customer_analytics(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("customers.view_analytics"))):
 count=int(await session.scalar(select(func.count()).select_from(Invoice).where(Invoice.customer_id==id)) or 0); spend=await session.scalar(select(func.coalesce(func.sum(Invoice.grand_total),0)).where(Invoice.customer_id==id)); return APIResponse(data={"customer_id":str(id),"orders":count,"lifetime_value":str(spend),"average_order_value":str(spend/count if count else 0)})
@router.get("/customers/{id}/history",response_model=APIResponse[list[dict]])
async def history(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("customers.read"))): rows=list((await session.scalars(select(AuditLog).where(AuditLog.entity_id==id).order_by(AuditLog.created_at.desc()))).all()); return APIResponse(data=[{"action":x.action,"created_at":x.created_at.isoformat()} for x in rows])
@router.get("/customer-tags",response_model=APIResponse[list[TagResponse]])
async def tags(session:DatabaseSession,actor:User=Depends(require_permission("customers.read"))): return APIResponse(data=list((await session.scalars(select(CustomerTag).where(CustomerTag.deleted_at.is_(None)))).all()))
@router.post("/customer-tags",response_model=APIResponse[TagResponse],status_code=201)
async def create_tag(data:TagRequest,session:DatabaseSession,actor:User=Depends(require_permission("customers.manage_tags"))): x=CustomerTag(**data.model_dump(),created_by_id=actor.id,updated_by_id=actor.id);session.add(x);await session.flush();return APIResponse(data=x)
@router.post("/customers/{id}/tags",response_model=APIResponse[dict])
async def assign_tags(id:UUID,data:TagAssignment,session:DatabaseSession,actor:User=Depends(require_permission("customers.manage_tags"))):
 from sqlalchemy.dialects.postgresql import insert
 for tag in data.tag_ids: await session.execute(insert(customer_tag_assignments).values(customer_id=id,tag_id=tag).on_conflict_do_nothing())
 return APIResponse(data={"assigned":len(data.tag_ids)})
@router.get("/customer-segments",response_model=APIResponse[list[dict]])
async def segments(session:DatabaseSession,actor:User=Depends(require_permission("customers.manage_segments"))):
 rows=list((await session.scalars(select(CustomerSegment).where(CustomerSegment.deleted_at.is_(None)))).all());return APIResponse(data=[{"id":str(x.id),"name":x.name,"code":x.code,"segment_type":x.segment_type,"rules_json":x.rules_json,"is_dynamic":x.is_dynamic,"is_active":x.is_active} for x in rows])
@router.post("/customer-segments",response_model=APIResponse[dict],status_code=201)
async def create_segment(data:SegmentRequest,session:DatabaseSession,actor:User=Depends(require_permission("customers.manage_segments"))):
 allowed={"total_spend","order_count","last_purchase_days","membership_tier","preferred_store","loyalty_balance","birthday_month"}
 if not set(data.rules_json).issubset(allowed):raise ConflictError("Unsupported segment rule","CUSTOMER_SEGMENT_RULE_INVALID")
 x=CustomerSegment(**data.model_dump(),created_by_id=actor.id,updated_by_id=actor.id);session.add(x);await session.flush();return APIResponse(data={"id":str(x.id),"name":x.name,"code":x.code,"rules_json":x.rules_json})
@router.get("/memberships/analytics",response_model=APIResponse[dict])
async def membership_analytics(session:DatabaseSession,actor:User=Depends(require_permission("memberships.analytics"))):
 rows=(await session.execute(select(MembershipTier.code,func.count(CustomerMembership.id)).outerjoin(CustomerMembership,CustomerMembership.membership_tier_id==MembershipTier.id).group_by(MembershipTier.code))).all();return APIResponse(data={"distribution":[{"tier":x[0],"customers":x[1]} for x in rows]})
@router.get("/loyalty/expiring",response_model=APIResponse[list[LoyaltyTransactionResponse]])
async def expiring(session:DatabaseSession,actor:User=Depends(require_permission("loyalty.read"))): return APIResponse(data=list((await session.scalars(select(LoyaltyTransaction).where(LoyaltyTransaction.expires_at.is_not(None),LoyaltyTransaction.expires_at<=utc_now()+__import__('datetime').timedelta(days=30),LoyaltyTransaction.expires_at>utc_now()))).all()))
@router.get("/loyalty/config",response_model=APIResponse[dict])
async def loyalty_config(session:DatabaseSession,actor:User=Depends(require_permission("loyalty.read"))):
 x=await session.scalar(select(LoyaltyConfig).where(LoyaltyConfig.is_active.is_(True),LoyaltyConfig.deleted_at.is_(None))); return APIResponse(data={c.name:getattr(x,c.name) for c in x.__table__.columns if c.name not in {"created_by_id","updated_by_id"}} if x else {})
@router.get("/loyalty/transactions",response_model=APIResponse[list[LoyaltyTransactionResponse]])
async def loyalty_transactions(session:DatabaseSession,actor:User=Depends(require_permission("loyalty.view_transactions"))): return APIResponse(data=list((await session.scalars(select(LoyaltyTransaction).order_by(LoyaltyTransaction.created_at.desc()).limit(500))).all()))
@router.post("/loyalty/manual-adjustment",response_model=APIResponse[LoyaltyTransactionResponse])
async def manual(data:LoyaltyAdjustmentRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("loyalty.adjust"))): return APIResponse(data=await svc(LoyaltyService,session,actor,request).adjust(data.customer_id,data.points,data.description))
@router.post("/loyalty/redeem",response_model=APIResponse[LoyaltyTransactionResponse])
async def redeem(data:LoyaltyRedeemRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("loyalty.redeem"))): return APIResponse(data=await svc(LoyaltyService,session,actor,request).redeem(data))
@router.post("/loyalty/reverse",response_model=APIResponse[LoyaltyTransactionResponse])
async def reverse(data:LoyaltyReverseRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("loyalty.reverse"))): return APIResponse(data=await svc(LoyaltyService,session,actor,request).reverse(data.transaction_id,data.reason))
@router.get("/memberships/tiers",response_model=APIResponse[list[MembershipTierResponse]])
async def tiers(session:DatabaseSession,actor:User=Depends(require_permission("memberships.read"))): return APIResponse(data=list((await session.scalars(select(MembershipTier).where(MembershipTier.deleted_at.is_(None)).order_by(MembershipTier.level))).all()))
@router.post("/memberships/tiers",response_model=APIResponse[MembershipTierResponse],status_code=201)
async def create_tier(data:MembershipTierRequest,session:DatabaseSession,actor:User=Depends(require_permission("memberships.create"))): x=MembershipTier(**data.model_dump(),created_by_id=actor.id,updated_by_id=actor.id);session.add(x);await session.flush();return APIResponse(data=x)
@router.get("/customer-communications",response_model=APIResponse[list[CommunicationResponse]])
async def comms(session:DatabaseSession,actor:User=Depends(require_permission("customer_communications.read"))): return APIResponse(data=list((await session.scalars(select(CustomerCommunication).where(CustomerCommunication.deleted_at.is_(None)).order_by(CustomerCommunication.created_at.desc()))).all()))
@router.get("/customers/{id}/communications",response_model=APIResponse[list[CommunicationResponse]])
async def customer_comms(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("customer_communications.read"))): return APIResponse(data=await CommunicationService(session,actor).for_customer(id))
@router.get("/invoices/{id}/communications",response_model=APIResponse[list[CommunicationResponse]])
async def invoice_comms(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("customer_communications.read"))): return APIResponse(data=await CommunicationService(session,actor).for_invoice(id))
@router.get("/communications/whatsapp/settings",response_model=APIResponse[dict])
async def whatsapp_settings(actor:User=Depends(require_permission("customer_communications.read"))):
 cfg=get_settings();return APIResponse(data={"enabled":cfg.whatsapp_enabled,"provider":cfg.whatsapp_provider,"configured":bool(cfg.whatsapp_access_token and cfg.whatsapp_phone_number_id) if cfg.whatsapp_provider=="meta" else True,"template":cfg.whatsapp_invoice_template_name,"language":cfg.whatsapp_template_language})
@router.post("/communications/whatsapp/send",response_model=APIResponse[CommunicationResponse],status_code=202)
async def send_whatsapp(data:InvoiceCommunicationRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("customer_communications.create"))):
 await rate_limiter.enforce(request);service=CommunicationService(session,actor);comm=await service.create_invoice_job(data.invoice_id,False);return APIResponse(data=await service.process(comm.id),message="WhatsApp invoice processing completed")
@router.post("/communications/{id}/retry",response_model=APIResponse[CommunicationResponse])
async def retry_whatsapp(id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("customer_communications.create"))):
 await rate_limiter.enforce(request);comm=await CommunicationService(session,actor).get(id)
 if not comm:raise NotFoundError("Communication not found","COMMUNICATION_NOT_FOUND")
 service=CommunicationService(session,actor);resend=await service.create_invoice_job(comm.related_invoice_id,False);return APIResponse(data=await service.process(resend.id))
@router.post("/customer-communications",response_model=APIResponse[CommunicationResponse],status_code=201)
async def create_comm(data:CommunicationRequest,session:DatabaseSession,actor:User=Depends(require_permission("customer_communications.create"))):
 p=await session.scalar(select(CustomerProfile).where(CustomerProfile.customer_id==data.customer_id)); allowed=data.transactional or (p and p.communication_opt_in and {Channel.SMS:p.sms_opt_in,Channel.WHATSAPP:p.whatsapp_opt_in,Channel.EMAIL:p.email_opt_in}.get(data.channel,True))
 if not allowed: raise ConflictError("Customer opted out of this channel","CUSTOMER_COMMUNICATION_OPT_OUT")
 x=CustomerCommunication(**data.model_dump(exclude={"transactional"}),purpose=data.communication_type,provider="manual",idempotency_key=f"manual:{uuid4()}",sent_by_id=actor.id,sent_at=utc_now(),created_by_id=actor.id,updated_by_id=actor.id);session.add(x);await session.flush();return APIResponse(data=x)

@router.get("/communications/whatsapp/webhook",include_in_schema=False)
async def verify_whatsapp_webhook(mode:str|None=Query(None,alias="hub.mode"),token:str|None=Query(None,alias="hub.verify_token"),challenge:str|None=Query(None,alias="hub.challenge")):
 cfg=get_settings()
 if mode=="subscribe" and token and cfg.whatsapp_verify_token and token==cfg.whatsapp_verify_token:return Response(content=challenge or "",media_type="text/plain")
 return Response(status_code=403)
@router.post("/communications/whatsapp/webhook",include_in_schema=False)
async def whatsapp_webhook(request:Request,session:DatabaseSession):
 body=await request.body()
 if not valid_meta_signature(body,request.headers.get("x-hub-signature-256")):return Response(status_code=403)
 payload=__import__('json').loads(body);service=CommunicationService(session,None)
 for entry in payload.get("entry",[]):
  for change in entry.get("changes",[]):
   for event in change.get("value",{}).get("statuses",[]):
    errors=event.get("errors") or [{}];await service.apply_provider_status(event.get("id",""),event.get("status",""),str(errors[0].get("code")) if errors[0].get("code") else None,errors[0].get("title") or errors[0].get("message"))
 return Response(status_code=200)
@router.get("/sales-returns",response_model=APIResponse[list[dict]])
async def sales_returns(session:DatabaseSession,actor:User=Depends(require_permission("sales_returns.read"))): rows=list((await session.scalars(select(Return).order_by(Return.created_at.desc()))).all());return APIResponse(data=[{"id":str(x.id),"return_number":x.return_number,"invoice_id":str(x.invoice_id),"amount":str(x.total_amount),"status":x.status.value} for x in rows])
@router.post("/sales-returns",response_model=APIResponse[dict],status_code=201)
async def create_sales_return(data:SalesReturnCreateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("sales_returns.create"))):
 r,f=await svc(ReturnService,session,actor,request).create_return(ReturnCreate(invoice_id=data.invoice_id,reason=data.reason,items=[ReturnItemInput(**x) for x in data.items],refund_method=data.refund_method)); return APIResponse(data={"id":str(r.id),"return_number":r.return_number,"refund_id":str(f.id),"amount":str(r.total_amount),"status":r.status.value})
@router.get("/customer-refunds",response_model=APIResponse[list[dict]])
async def refunds(session:DatabaseSession,actor:User=Depends(require_permission("customer_refunds.read"))): rows=list((await session.scalars(select(Refund).order_by(Refund.created_at.desc()))).all());return APIResponse(data=[{"id":str(x.id),"refund_number":x.refund_number,"return_id":str(x.return_id),"amount":str(x.amount),"status":x.status.value} for x in rows])
@router.get("/customer-refunds/{id}/receipt")
async def refund_receipt(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("customer_refunds.receipt"))):
 x=await session.scalar(select(Refund).where(Refund.id==id));
 if not x: raise NotFoundError("Refund not found","CUSTOMER_REFUND_NOT_FOUND")
 path=ProcurementPDFService().generate(x.refund_number,"CUSTOMER REFUND RECEIPT",x.status.value,[["Return","Amount","Reference"],[str(x.return_id),str(x.amount),x.transaction_reference or "-"]]);return FileResponse(path,media_type="application/pdf",filename=path.name)
@router.get("/crm/dashboard",response_model=APIResponse[dict])
async def dashboard(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("crm.analytics"))): return APIResponse(data=await svc(CRMAnalyticsService,session,actor,request).dashboard())
@router.get("/crm/analytics/{report}",response_model=APIResponse[dict])
async def analytics(report:str,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("crm.analytics"))): data=await svc(CRMAnalyticsService,session,actor,request).dashboard();return APIResponse(data={"report":report,**data})
