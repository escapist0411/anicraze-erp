import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import UUID
from types import SimpleNamespace
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.pdf.documents import invoice_pdf
from app.exceptions.domain import AuthorizationError, ConflictError, NotFoundError
from app.models.auth import AuditLog, User
from app.models.billing import *
from app.models.catalog import ProductStatus
from app.models.inventory import Inventory, Store, TransactionType
from app.repositories.billing import InvoiceRepository, PaymentRepository, RefundRepository, ReturnRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.management import ManagementRepository
from app.schemas.billing import *
from app.services.inventory import InventoryService
from app.utils.time import utc_now
from app.config.business import BUSINESS_NAME, BUSINESS_PHONE_DISPLAY
from app.permissions.store_scope import require_shop_access
from app.utils.phone import normalize_indian_phone
from app.storage import DocumentStorage

MONEY=Decimal("0.01")
def money(v): return Decimal(v).quantize(MONEY,rounding=ROUND_HALF_UP)

class InvoicePDFService:
    def generate(self,invoice:Invoice,customer:Customer,store:Store,employee:User,payment_methods:list[str]|None=None, *, preview=False):
        return DocumentStorage().save("invoices",f"{invoice.invoice_number}.pdf",invoice_pdf(invoice,customer,store,employee,payment_methods,preview=preview))

class WhatsAppService:
    async def send_invoice(self,invoice,recipient): logging.getLogger(__name__).info("WhatsApp invoice %s queued for %s",invoice.invoice_number,recipient)
    async def send_payment_receipt(self,payment,recipient): logging.getLogger(__name__).info("WhatsApp receipt %s queued for %s",payment.id,recipient)
class SMSService:
    async def send(self,recipient,message): logging.getLogger(__name__).info("SMS queued for %s: %s",recipient,message)
class EmailService:
    async def send_invoice(self,invoice,recipient): logging.getLogger(__name__).info("Invoice %s email queued for %s",invoice.invoice_number,recipient)
    async def send_receipt(self,payment,recipient): logging.getLogger(__name__).info("Receipt %s email queued for %s",payment.id,recipient)
    async def send_payment_confirmation(self,invoice,recipient): logging.getLogger(__name__).info("Payment confirmation %s queued for %s",invoice.invoice_number,recipient)

class BillingService:
    def __init__(self,s:AsyncSession,actor:User,ip=None,user_agent=None): self.s=s; self.actor=actor; self.invoices=InvoiceRepository(s); self.payments=PaymentRepository(s); self.returns=ReturnRepository(s); self.refunds=RefundRepository(s); self.inventory=InventoryRepository(s); self.audit_repo=ManagementRepository(s); self.ip=ip; self.user_agent=user_agent
    async def audit(self,action,kind,id,meta=None): await self.audit_repo.audit(AuditLog(actor_user_id=self.actor.id,action=action,entity_type=kind,entity_id=id,metadata_json=meta,ip_address=self.ip,user_agent=self.user_agent,created_at=utc_now()))
    async def customer(self,id):
        x=await self.s.scalar(select(Customer).where(Customer.id==id,Customer.deleted_at.is_(None)))
        if not x: raise NotFoundError("Customer not found","CUSTOMER_NOT_FOUND")
        return x
    async def create_customer(self,data): x=Customer(**data.model_dump(),created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(x); await self.s.flush(); await self.audit("CUSTOMER_CREATED","customer",x.id); return x
    def authorize_store(self,store_id):
        require_shop_access(self.actor,store_id)
    async def create(self,data:BillingCreate):
        existing=await self.invoices.by_idempotency_key(data.idempotency_key)
        if existing: self.authorize_store(existing.store_id); return existing
        if data.store_id is not None: self.authorize_store(data.store_id)
        store_id=self.actor.assigned_store_id or data.store_id
        if not store_id: raise AuthorizationError("No shop is assigned for billing","BILLING_STORE_REQUIRED")
        self.authorize_store(store_id)
        customer_phone=normalize_indian_phone(data.customer_phone)
        if data.customer_phone and not customer_phone: raise ConflictError("Enter a valid Indian WhatsApp number","BILLING_CUSTOMER_PHONE_INVALID")
        customer=SimpleNamespace(name=data.customer_name.strip(),phone=customer_phone,address=None); store=await self.s.scalar(select(Store).where(Store.id==store_id,Store.deleted_at.is_(None)))
        if not store: raise NotFoundError("Store not found","STORE_NOT_FOUND")
        locked={}
        for requested in sorted(data.items,key=lambda i:str(i.inventory_id)):
            if requested.inventory_id in locked: raise ConflictError("Duplicate inventory line; combine quantities","BILLING_DUPLICATE_ITEM")
            inv=await self.inventory.get(requested.inventory_id,True)
            if not inv or inv.store_id!=store_id: raise ConflictError("Product is not available at this shop.","BILLING_STORE_INVENTORY_INVALID")
            if inv.product.status!=ProductStatus.ACTIVE: raise ConflictError("Inactive product cannot be billed","BILLING_PRODUCT_INACTIVE")
            if inv.available_quantity<requested.quantity: raise ConflictError("Insufficient stock","BILLING_INSUFFICIENT_STOCK")
            locked[requested.inventory_id]=inv
        for requested in data.items:
            authoritative=money(locked[requested.inventory_id].variant.selling_price if locked[requested.inventory_id].variant else locked[requested.inventory_id].product.selling_price)
            if requested.unit_price is not None and money(requested.unit_price)!=authoritative: raise ConflictError("Product pricing has changed; review the updated bill","BILLING_PRICE_CHANGED")
        raw_subtotal=sum((money((locked[i.inventory_id].variant.selling_price if locked[i.inventory_id].variant else locked[i.inventory_id].product.selling_price)*i.quantity) for i in data.items),Decimal(0))
        if data.invoice_discount>raw_subtotal: raise ConflictError("Invoice discount exceeds subtotal","BILLING_DISCOUNT_INVALID")
        invoice=Invoice(invoice_number=await self.invoices.next_number(),idempotency_key=data.idempotency_key,customer_id=None,customer_name_snapshot=customer.name,customer_phone_snapshot=customer.phone,store_id=store.id,employee_id=self.actor.id,subtotal=raw_subtotal,discount=Decimal(0),taxable_amount=0,cgst=0,sgst=0,igst=0,gst_total=0,grand_total=0,round_off=0,payment_status=PaymentStatus.PENDING,invoice_status=InvoiceStatus.DRAFT,notes=data.notes,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(invoice); await self.s.flush()
        subtotal=discount=Decimal(0); created_items=[]
        for index,requested in enumerate(data.items):
            inv=locked[requested.inventory_id]; product=inv.product; price=money(inv.variant.selling_price if inv.variant else product.selling_price)
            minimum=product.minimum_selling_price
            if minimum is not None and price<minimum: raise ConflictError("Price is below allowed minimum","BILLING_PRICE_INVALID")
            gross=money(price*requested.quantity)
            allocated=money(data.invoice_discount*gross/raw_subtotal) if raw_subtotal else Decimal(0)
            if index==len(data.items)-1: allocated=data.invoice_discount-discount
            line_discount=money(requested.discount+allocated)
            if line_discount>gross: raise ConflictError("Line discount exceeds line value","BILLING_DISCOUNT_INVALID")
            base=money(gross-line_discount)
            item=InvoiceItem(invoice_id=invoice.id,inventory_id=inv.id,product_id=product.id,variant_id=inv.variant_id,sku=inv.variant.sku if inv.variant else product.sku,product_name=product.name,hsn_code=None,quantity=requested.quantity,unit_price=price,unit_cost=money(inv.average_cost),discount=line_discount,gst_rate=0,taxable_amount=base,tax_amount=0,line_total=base); self.s.add(item); created_items.append(item)
            subtotal+=gross; discount+=line_discount
        grand=money(subtotal-discount); invoice.subtotal=money(subtotal); invoice.discount=money(discount); invoice.taxable_amount=grand; invoice.cgst=0; invoice.sgst=0; invoice.igst=0; invoice.gst_total=0; invoice.round_off=0; invoice.grand_total=grand
        paid=sum((p.amount for p in data.payments),Decimal(0)); payment_labels=[]
        if paid!=grand: raise ConflictError("Payment total must equal invoice total","BILLING_PAYMENT_TOTAL_MISMATCH")
        if data.invoice_discount: self.s.add(InvoiceDiscount(invoice_id=invoice.id,description="Invoice discount",amount=data.invoice_discount))
        for p in data.payments:
            method=await self.payments.method(p.method)
            if not method: raise ConflictError("Payment method is unavailable","PAYMENT_METHOD_INVALID")
            payment_labels.append(method.name)
            change=money((p.tendered_amount or p.amount)-p.amount) if p.method==PaymentMethodCode.CASH else Decimal(0)
            payment=Payment(invoice_id=invoice.id,payment_method_id=method.id,amount=money(p.amount),tendered_amount=p.tendered_amount,change_amount=change,transaction_reference=p.transaction_reference,status=PaymentStatus.PAID,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(payment); await self.s.flush(); invoice.payment_id=invoice.payment_id or payment.id
            if p.method==PaymentMethodCode.CASH:
                register=await self.s.scalar(select(CashRegister).where(CashRegister.store_id==store.id,CashRegister.status==RegisterStatus.OPEN,CashRegister.deleted_at.is_(None)).with_for_update())
                if register: register.cash_sales=money(register.cash_sales+p.amount)
        invoice.payment_status=PaymentStatus.PAID if paid==grand else PaymentStatus.PARTIAL; invoice.invoice_status=InvoiceStatus.COMPLETED
        inventory_service=InventoryService(self.s,self.actor,self.ip,self.user_agent)
        for item in created_items: await inventory_service.move(locked[item.inventory_id],TransactionType.SALE,-item.quantity,invoice.invoice_number,f"invoice:{invoice.id}:{item.id}",remarks="POS invoice")
        await self.s.flush(); await self.s.refresh(invoice,attribute_names=["items","payments","created_at"])
        try: invoice.pdf_path=str(InvoicePDFService().generate(invoice,customer,store,self.actor,payment_labels))
        except Exception: logging.getLogger(__name__).exception("Invoice PDF generation failed for %s",invoice.invoice_number)
        await self.audit("INVOICE_COMPLETED","invoice",invoice.id,{"number":invoice.invoice_number,"total":str(invoice.grand_total),"store_id":str(store.id)}); await self.s.flush(); return await self.invoices.get(invoice.id)
    async def cancel(self,id,reason):
        invoice=await self.invoices.get(id,True)
        if not invoice: raise NotFoundError("Invoice not found","INVOICE_NOT_FOUND")
        self.authorize_store(invoice.store_id)
        if invoice.invoice_status!=InvoiceStatus.COMPLETED: raise ConflictError("Only completed invoices can be cancelled","INVOICE_CANCEL_INVALID")
        inv_service=InventoryService(self.s,self.actor,self.ip,self.user_agent)
        for item in invoice.items:
            inv=await self.inventory.get(item.inventory_id,True); await inv_service.move(inv,TransactionType.RETURN,item.quantity,invoice.invoice_number,f"invoice-cancel:{invoice.id}:{item.id}",remarks="Invoice cancelled")
        invoice.invoice_status=InvoiceStatus.CANCELLED; invoice.payment_status=PaymentStatus.CANCELLED
        for payment in invoice.payments: payment.status=PaymentStatus.CANCELLED
        await self.audit("INVOICE_CANCELLED","invoice",invoice.id,{"reason":reason,"store_id":str(invoice.store_id)}); await self.s.flush(); return invoice

class ReturnService(BillingService):
    async def create_return(self,data:ReturnCreate):
        invoice=await self.invoices.get(data.invoice_id,True)
        if not invoice or invoice.invoice_status not in {InvoiceStatus.COMPLETED,InvoiceStatus.RETURNED}: raise ConflictError("Invoice is not returnable","RETURN_INVOICE_INVALID")
        self.authorize_store(invoice.store_id)
        returned=Return(return_number=await self.invoices.next_number("return","ANI-RET"),invoice_id=invoice.id,reason=data.reason,total_amount=0,status=ReturnStatus.COMPLETED,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(returned); await self.s.flush(); total=Decimal(0); inv_service=InventoryService(self.s,self.actor,self.ip,self.user_agent)
        item_map={x.id:x for x in invoice.items}
        for req in data.items:
            item=item_map.get(req.invoice_item_id)
            if not item: raise ConflictError("Return item does not belong to invoice","RETURN_ITEM_INVALID")
            already=await ReturnRepository(self.s).returned_quantity(item.id)
            if already+req.quantity>item.quantity: raise ConflictError("Return quantity exceeds sold quantity","RETURN_QUANTITY_INVALID")
            amount=money(item.line_total*req.quantity/item.quantity); self.s.add(ReturnItem(return_id=returned.id,invoice_item_id=item.id,quantity=req.quantity,amount=amount)); total+=amount
            inv=await self.inventory.get(item.inventory_id,True); await inv_service.move(inv,TransactionType.RETURN,req.quantity,returned.return_number,f"return:{returned.id}:{item.id}",remarks=data.reason)
        returned.total_amount=money(total); method=await self.payments.method(data.refund_method)
        if not method: raise ConflictError("Refund method unavailable","REFUND_METHOD_INVALID")
        refund=Refund(refund_number=await self.invoices.next_number("refund","ANI-REF"),return_id=returned.id,payment_method_id=method.id,amount=returned.total_amount,transaction_reference=data.transaction_reference,status=RefundStatus.COMPLETED,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(refund); invoice.invoice_status=InvoiceStatus.RETURNED; invoice.payment_status=PaymentStatus.REFUNDED if returned.total_amount>=invoice.grand_total else PaymentStatus.PARTIAL
        if data.refund_method==PaymentMethodCode.CASH:
            register=await self.s.scalar(select(CashRegister).where(CashRegister.store_id==invoice.store_id,CashRegister.status==RegisterStatus.OPEN,CashRegister.deleted_at.is_(None)).with_for_update())
            if register: register.cash_refunds=money(register.cash_refunds+returned.total_amount)
        await self.s.flush(); await self.audit("INVOICE_RETURNED","return",returned.id,{"refund":str(total)}); await self.s.refresh(returned,attribute_names=["items","created_at"]); return returned,refund

class BillingAnalyticsService:
    def __init__(self,s): self.s=s
    async def summary(self,store_id=None):
        now=utc_now(); start_day=now.replace(hour=0,minute=0,second=0,microsecond=0); completed=(Invoice.invoice_status.in_([InvoiceStatus.COMPLETED,InvoiceStatus.RETURNED]),)
        shop_filter=(Invoice.store_id==store_id,) if store_id is not None else ()
        async def sales(since): return Decimal(await self.s.scalar(select(func.coalesce(func.sum(Invoice.grand_total),0)).where(*completed,*shop_filter,Invoice.created_at>=since)) or 0)
        monthly=await sales(now-timedelta(days=30)); count=int(await self.s.scalar(select(func.count()).select_from(Invoice).where(*completed,*shop_filter)) or 0); total=Decimal(await self.s.scalar(select(func.coalesce(func.sum(Invoice.grand_total),0)).where(*completed,*shop_filter)) or 0)
        products=(await self.s.execute(select(InvoiceItem.product_name,func.sum(InvoiceItem.quantity).label("qty")).join(Invoice).where(*completed,*shop_filter).group_by(InvoiceItem.product_name).order_by(func.sum(InvoiceItem.quantity).desc()).limit(10))).all()
        methods_query=select(PaymentMethod.name,func.sum(Payment.amount)).join(Payment)
        if store_id is not None: methods_query=methods_query.join(Invoice).where(Invoice.store_id==store_id)
        methods=(await self.s.execute(methods_query.group_by(PaymentMethod.name))).all()
        return BillingAnalytics(today_sales=await sales(start_day),weekly_sales=await sales(now-timedelta(days=7)),monthly_sales=monthly,average_bill=money(total/count) if count else Decimal(0),invoice_count=count,top_products=[{"product":x[0],"quantity":int(x[1])} for x in products],payment_methods=[{"method":x[0],"amount":str(x[1])} for x in methods])
