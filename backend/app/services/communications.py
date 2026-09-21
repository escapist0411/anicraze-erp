import hashlib
import hmac
import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID,uuid4
import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.config.settings import get_settings
from app.database.session import AsyncSessionFactory
from app.exceptions.domain import ConflictError,NotFoundError
from app.models.auth import AuditLog,User
from app.models.billing import Customer,Invoice
from app.models.crm import Channel,CustomerCommunication,CustomerProfile
from app.repositories.management import ManagementRepository
from app.utils.phone import normalize_indian_phone
from app.utils.time import utc_now

@dataclass
class ProviderResult: status:str;message_id:str|None=None;reference:str|None=None

class WhatsAppProvider:
    async def send_invoice(self,invoice:Invoice,customer:Customer,recipient:str,pdf:Path)->ProviderResult: raise NotImplementedError

class DevelopmentWhatsAppProvider(WhatsAppProvider):
    async def send_invoice(self,invoice,customer,recipient,pdf):
        reference=f"development:{uuid4()}";logging.getLogger(__name__).info("Development WhatsApp invoice logged invoice=%s recipient=***%s",invoice.invoice_number,recipient[-4:]);return ProviderResult("SIMULATED",reference=reference)

class MetaWhatsAppProvider(WhatsAppProvider):
    def __init__(self):
        self.cfg=get_settings()
        if not self.cfg.whatsapp_access_token or not self.cfg.whatsapp_phone_number_id:raise RuntimeError("Meta WhatsApp credentials are incomplete")
        self.base=f"https://graph.facebook.com/{self.cfg.whatsapp_api_version}/{self.cfg.whatsapp_phone_number_id}"
        self.headers={"Authorization":f"Bearer {self.cfg.whatsapp_access_token}"}
    async def send_invoice(self,invoice,customer,recipient,pdf):
        async with httpx.AsyncClient(timeout=30) as client:
            with pdf.open("rb") as handle:
                media=await client.post(f"{self.base}/media",headers=self.headers,data={"messaging_product":"whatsapp","type":"application/pdf"},files={"file":(pdf.name,handle,"application/pdf")})
            media.raise_for_status();media_id=media.json()["id"]
            payload={"messaging_product":"whatsapp","to":recipient,"type":"template","template":{"name":self.cfg.whatsapp_invoice_template_name,"language":{"code":self.cfg.whatsapp_template_language},"components":[{"type":"header","parameters":[{"type":"document","document":{"id":media_id,"filename":pdf.name}}]},{"type":"body","parameters":[{"type":"text","text":customer.name},{"type":"text","text":invoice.invoice_number},{"type":"text","text":str(invoice.grand_total)}]}]}}
            sent=await client.post(f"{self.base}/messages",headers={**self.headers,"Content-Type":"application/json"},json=payload);sent.raise_for_status();message_id=sent.json()["messages"][0]["id"]
            return ProviderResult("SENT",message_id=message_id,reference=media_id)

def provider()->WhatsAppProvider:
    return MetaWhatsAppProvider() if get_settings().whatsapp_provider=="meta" else DevelopmentWhatsAppProvider()

class CommunicationService:
    def __init__(self,s,actor):self.s=s;self.actor=actor;self.audit_repo=ManagementRepository(s)
    async def audit(self,action,comm,meta=None):await self.audit_repo.audit(AuditLog(actor_user_id=self.actor.id if self.actor else None,action=action,entity_type="customer_communication",entity_id=comm.id,metadata_json=meta,created_at=utc_now()))
    async def get(self,id,lock=False):
        q=select(CustomerCommunication).where(CustomerCommunication.id==id,CustomerCommunication.deleted_at.is_(None));return await self.s.scalar(q.with_for_update() if lock else q)
    async def for_invoice(self,invoice_id):return list((await self.s.scalars(select(CustomerCommunication).where(CustomerCommunication.related_invoice_id==invoice_id,CustomerCommunication.deleted_at.is_(None)).order_by(CustomerCommunication.created_at.desc()))).all())
    async def for_customer(self,customer_id):return list((await self.s.scalars(select(CustomerCommunication).where(CustomerCommunication.customer_id==customer_id,CustomerCommunication.deleted_at.is_(None)).order_by(CustomerCommunication.created_at.desc()))).all())
    async def list(self):return list((await self.s.scalars(select(CustomerCommunication).where(CustomerCommunication.deleted_at.is_(None)).order_by(CustomerCommunication.created_at.desc()).limit(500))).all())
    async def create_invoice_job(self,invoice_id,automatic=True):
        invoice=await self.s.scalar(select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id==invoice_id,Invoice.deleted_at.is_(None)))
        if not invoice:raise NotFoundError("Invoice not found","INVOICE_NOT_FOUND")
        customer=await self.s.scalar(select(Customer).where(Customer.id==invoice.customer_id,Customer.deleted_at.is_(None)));profile=await self.s.scalar(select(CustomerProfile).where(CustomerProfile.customer_id==invoice.customer_id,CustomerProfile.deleted_at.is_(None)))
        recipient=normalize_indian_phone(customer.phone if customer else None)
        if not recipient:raise ConflictError("Customer has no valid mobile number","WHATSAPP_RECIPIENT_UNAVAILABLE")
        if profile and (not profile.communication_opt_in or not profile.whatsapp_opt_in):raise ConflictError("Customer opted out of WhatsApp","CUSTOMER_COMMUNICATION_OPT_OUT")
        key=f"invoice:{invoice.id}:whatsapp:invoice" if automatic else f"invoice:{invoice.id}:whatsapp:resend:{uuid4()}"
        existing=await self.s.scalar(select(CustomerCommunication).where(CustomerCommunication.idempotency_key==key))
        if existing:return existing
        cfg=get_settings();status="QUEUED" if cfg.whatsapp_enabled else "DISABLED"
        comm=CustomerCommunication(customer_id=invoice.customer_id,communication_type="INVOICE",purpose="INVOICE",direction="OUTBOUND",channel=Channel.WHATSAPP,recipient=recipient,subject=f"Invoice {invoice.invoice_number}",message_summary=f"Invoice {invoice.invoice_number}",status=status,provider=cfg.whatsapp_provider,idempotency_key=key,related_invoice_id=invoice.id,sent_by_id=None if automatic else self.actor.id,created_by_id=self.actor.id if self.actor else None,updated_by_id=self.actor.id if self.actor else None);self.s.add(comm);await self.s.flush();await self.audit("WHATSAPP_SEND_REQUESTED" if automatic else "WHATSAPP_RESEND_REQUESTED",comm,{"invoice_id":str(invoice.id),"automatic":automatic});return comm
    async def process(self,id):
        comm=await self.get(id,True)
        if not comm:raise NotFoundError("Communication not found","COMMUNICATION_NOT_FOUND")
        if comm.status in {"SENT","DELIVERED","READ","SIMULATED","DISABLED"}:return comm
        cfg=get_settings()
        if comm.attempt_count>=cfg.whatsapp_max_attempts:raise ConflictError("Maximum communication attempts reached","COMMUNICATION_RETRY_EXHAUSTED")
        invoice=await self.s.scalar(select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id==comm.related_invoice_id));customer=await self.s.scalar(select(Customer).where(Customer.id==comm.customer_id));comm.status="PROCESSING";comm.attempt_count+=1;comm.last_attempt_at=utc_now();await self.s.flush()
        try:
            if not invoice.pdf_path or not Path(invoice.pdf_path).exists():raise FileNotFoundError("Invoice PDF is unavailable")
            result=await provider().send_invoice(invoice,customer,comm.recipient,Path(invoice.pdf_path));comm.status=result.status;comm.provider_message_id=result.message_id;comm.provider_reference=result.reference;comm.sent_at=utc_now() if result.status=="SENT" else None;comm.failure_code=None;comm.failure_message=None;comm.failed_at=None;await self.audit("WHATSAPP_PROVIDER_ACCEPTED" if result.status=="SENT" else "WHATSAPP_DEVELOPMENT_SIMULATED",comm,{"status":result.status})
        except Exception as exc:
            comm.status="WAITING_FOR_DOCUMENT" if isinstance(exc,FileNotFoundError) else "FAILED";comm.failed_at=utc_now();comm.failure_code="DOCUMENT_UNAVAILABLE" if isinstance(exc,FileNotFoundError) else "PROVIDER_ERROR";comm.failure_message=str(exc)[:500];await self.audit("COMMUNICATION_FAILED",comm,{"code":comm.failure_code});logging.getLogger(__name__).warning("WhatsApp communication failed id=%s code=%s",comm.id,comm.failure_code)
        return comm
    async def apply_provider_status(self,message_id,status,failure_code=None,failure_message=None):
        comm=await self.s.scalar(select(CustomerCommunication).where(CustomerCommunication.provider_message_id==message_id).with_for_update())
        if not comm:return None
        rank={"QUEUED":0,"PROCESSING":1,"SENT":2,"DELIVERED":3,"READ":4,"FAILED":5};incoming=status.upper()
        if incoming=="FAILED" and comm.status in {"DELIVERED","READ"}:return comm
        if incoming!="FAILED" and rank.get(incoming,-1)<rank.get(comm.status,-1):return comm
        now=utc_now();comm.status=incoming
        if incoming=="SENT":comm.sent_at=comm.sent_at or now
        elif incoming=="DELIVERED":comm.delivered_at=comm.delivered_at or now
        elif incoming=="READ":comm.read_at=comm.read_at or now
        elif incoming=="FAILED":comm.failed_at=now;comm.failure_code=failure_code;comm.failure_message=(failure_message or "Provider reported failure")[:500]
        await self.audit("COMMUNICATION_STATUS_UPDATED",comm,{"status":incoming});return comm

async def dispatch_invoice_background(invoice_id:str,actor_id:str):
    async with AsyncSessionFactory() as s:
        try:
            actor=await s.scalar(select(User).where(User.id==UUID(actor_id)));service=CommunicationService(s,actor);comm=await service.create_invoice_job(UUID(invoice_id),True);await service.process(comm.id);await s.commit()
        except (ConflictError,NotFoundError):await s.rollback()
        except Exception:await s.rollback();logging.getLogger(__name__).exception("Post-commit invoice communication failed invoice=%s",invoice_id)

def valid_meta_signature(body:bytes,signature:str|None)->bool:
    secret=get_settings().whatsapp_app_secret
    if not secret or not signature or not signature.startswith("sha256="):return False
    expected=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest();return hmac.compare_digest(signature[7:],expected)
