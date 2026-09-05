import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
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

MONEY=Decimal("0.01"); GST_RATES={Decimal("0"),Decimal("5"),Decimal("12"),Decimal("18"),Decimal("28")}
def money(v): return Decimal(v).quantize(MONEY,rounding=ROUND_HALF_UP)

class GSTService:
    @staticmethod
    def calculate(taxable:Decimal,rate:Decimal,interstate:bool):
        if rate not in GST_RATES: raise ConflictError("GST rate must be 0, 5, 12, 18 or 28 percent","BILLING_GST_INVALID")
        total=money(taxable*rate/100)
        if interstate: return Decimal("0.00"),Decimal("0.00"),total
        cgst=money(total/2); return cgst,total-cgst,Decimal("0.00")

class InvoicePDFService:
    root=Path(__file__).resolve().parents[2]/"generated"/"invoices"
    def generate(self,invoice:Invoice,customer:Customer,store:Store):
        self.root.mkdir(parents=True,exist_ok=True); path=self.root/f"{invoice.invoice_number}.pdf"; styles=getSampleStyleSheet()
        doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=14*mm,leftMargin=14*mm,topMargin=12*mm,bottomMargin=12*mm,title=f"GST Invoice {invoice.invoice_number}")
        story=[Paragraph("<b>ANICRAZE</b>",styles["Title"]),Paragraph("TAX INVOICE",styles["Heading2"]),Paragraph(f"Invoice: {invoice.invoice_number}<br/>Date: {invoice.created_at:%d %b %Y %H:%M}<br/>Store: {store.name}",styles["BodyText"]),Spacer(1,5*mm),Paragraph(f"Bill To: <b>{customer.name}</b><br/>{customer.address or ''}<br/>GSTIN: {customer.gstin or 'Unregistered'}",styles["BodyText"]),Spacer(1,5*mm)]
        rows=[["SKU / Product","HSN","Qty","Rate","Discount","GST","Amount"]]+[[f"{x.sku}\n{x.product_name}",x.hsn_code or "-",str(x.quantity),f"{x.unit_price:.2f}",f"{x.discount:.2f}",f"{x.gst_rate}%",f"{x.line_total:.2f}"] for x in invoice.items]
        table=Table(rows,colWidths=[65*mm,18*mm,12*mm,22*mm,22*mm,15*mm,25*mm],repeatRows=1); table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#111827")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.grey),("FONTSIZE",(0,0),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(2,1),(-1,-1),"RIGHT")]))
        story += [table,Spacer(1,5*mm),Table([["Taxable",f"INR {invoice.taxable_amount:.2f}"],["CGST",f"INR {invoice.cgst:.2f}"],["SGST",f"INR {invoice.sgst:.2f}"],["IGST",f"INR {invoice.igst:.2f}"],["Round off",f"INR {invoice.round_off:.2f}"],["Grand Total",f"INR {invoice.grand_total:.2f}"]],colWidths=[40*mm,35*mm],hAlign="RIGHT",style=[("GRID",(0,0),(-1,-1),.4,colors.grey),("ALIGN",(1,0),(1,-1),"RIGHT"),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold")]),Spacer(1,7*mm),Paragraph("[ QR PAYMENT / VERIFICATION ]",styles["Heading3"]),Paragraph("Terms: Goods once sold may be returned only under the ANICRAZE return policy. This is a computer-generated GST invoice.",styles["BodyText"]),Spacer(1,4*mm),Paragraph("Thank you for shopping with ANICRAZE.",styles["Heading3"])]
        doc.build(story); return path

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
        if self.actor.assigned_store_id is not None and self.actor.assigned_store_id!=store_id: raise AuthorizationError("Billing is restricted to your assigned shop","BILLING_STORE_SCOPE_DENIED")
    async def create(self,data:BillingCreate):
        existing=await self.invoices.by_idempotency_key(data.idempotency_key)
        if existing: self.authorize_store(existing.store_id); return existing
        self.authorize_store(data.store_id)
        customer=await self.customer(data.customer_id); store=await self.s.scalar(select(Store).where(Store.id==data.store_id,Store.deleted_at.is_(None)))
        if not store: raise NotFoundError("Store not found","STORE_NOT_FOUND")
        locked={}
        for requested in sorted(data.items,key=lambda i:str(i.inventory_id)):
            if requested.inventory_id in locked: raise ConflictError("Duplicate inventory line; combine quantities","BILLING_DUPLICATE_ITEM")
            inv=await self.inventory.get(requested.inventory_id,True)
            if not inv or inv.store_id!=data.store_id: raise ConflictError("Inventory is not available at selected store","BILLING_STORE_INVENTORY_INVALID")
            if inv.product.status!=ProductStatus.ACTIVE: raise ConflictError("Inactive product cannot be billed","BILLING_PRODUCT_INACTIVE")
            if inv.available_quantity<requested.quantity: raise ConflictError("Insufficient stock","BILLING_INSUFFICIENT_STOCK")
            locked[requested.inventory_id]=inv
        for requested in data.items:
            authoritative=money(locked[requested.inventory_id].variant.selling_price if locked[requested.inventory_id].variant else locked[requested.inventory_id].product.selling_price)
            if requested.unit_price is not None and money(requested.unit_price)!=authoritative: raise ConflictError("Product pricing has changed; review the updated bill","BILLING_PRICE_CHANGED")
        raw_subtotal=sum((money((locked[i.inventory_id].variant.selling_price if locked[i.inventory_id].variant else locked[i.inventory_id].product.selling_price)*i.quantity) for i in data.items),Decimal(0))
        if data.invoice_discount>raw_subtotal: raise ConflictError("Invoice discount exceeds subtotal","BILLING_DISCOUNT_INVALID")
        invoice=Invoice(invoice_number=await self.invoices.next_number(),idempotency_key=data.idempotency_key,customer_id=customer.id,store_id=store.id,employee_id=self.actor.id,subtotal=raw_subtotal,discount=Decimal(0),taxable_amount=0,cgst=0,sgst=0,igst=0,gst_total=0,grand_total=0,round_off=0,payment_status=PaymentStatus.PENDING,invoice_status=InvoiceStatus.DRAFT,notes=data.notes,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(invoice); await self.s.flush()
        subtotal=discount=taxable=cgst=sgst=igst=Decimal(0); interstate=data.customer_state_code!="27"; created_items=[]
        tax_buckets={}
        for index,requested in enumerate(data.items):
            inv=locked[requested.inventory_id]; product=inv.product; price=money(inv.variant.selling_price if inv.variant else product.selling_price)
            minimum=product.minimum_selling_price
            if minimum is not None and price<minimum: raise ConflictError("Price is below allowed minimum","BILLING_PRICE_INVALID")
            gross=money(price*requested.quantity)
            allocated=money(data.invoice_discount*gross/raw_subtotal) if raw_subtotal else Decimal(0)
            if index==len(data.items)-1: allocated=data.invoice_discount-discount
            line_discount=money(requested.discount+allocated)
            if line_discount>gross: raise ConflictError("Line discount exceeds line value","BILLING_DISCOUNT_INVALID")
            base=money(gross-line_discount); rate=Decimal(product.gst_rate); c,s,i=GSTService.calculate(base,rate,interstate); tax=c+s+i; total=money(base+tax)
            item=InvoiceItem(invoice_id=invoice.id,inventory_id=inv.id,product_id=product.id,variant_id=inv.variant_id,sku=inv.variant.sku if inv.variant else product.sku,product_name=product.name,hsn_code=product.hsn_code,quantity=requested.quantity,unit_price=price,discount=line_discount,gst_rate=rate,taxable_amount=base,tax_amount=tax,line_total=total); self.s.add(item); created_items.append(item)
            subtotal+=gross; discount+=line_discount; taxable+=base; cgst+=c; sgst+=s; igst+=i
            bucket=tax_buckets.setdefault(rate,[Decimal(0)]*5); bucket[0]+=base; bucket[1]+=c; bucket[2]+=s; bucket[3]+=i; bucket[4]+=tax
        exact=money(taxable+cgst+sgst+igst); grand=exact.quantize(Decimal("1"),rounding=ROUND_HALF_UP); invoice.subtotal=money(subtotal); invoice.discount=money(discount); invoice.taxable_amount=money(taxable); invoice.cgst=money(cgst); invoice.sgst=money(sgst); invoice.igst=money(igst); invoice.gst_total=money(cgst+sgst+igst); invoice.round_off=money(grand-exact); invoice.grand_total=grand
        paid=sum((p.amount for p in data.payments),Decimal(0))
        if paid!=grand: raise ConflictError("Payment total must equal invoice total","BILLING_PAYMENT_TOTAL_MISMATCH")
        for rate,values in tax_buckets.items(): self.s.add(InvoiceTax(invoice_id=invoice.id,gst_rate=rate,taxable_amount=money(values[0]),cgst=money(values[1]),sgst=money(values[2]),igst=money(values[3]),total_tax=money(values[4])))
        if data.invoice_discount: self.s.add(InvoiceDiscount(invoice_id=invoice.id,description="Invoice discount",amount=data.invoice_discount))
        for p in data.payments:
            method=await self.payments.method(p.method)
            if not method: raise ConflictError("Payment method is unavailable","PAYMENT_METHOD_INVALID")
            change=money((p.tendered_amount or p.amount)-p.amount) if p.method==PaymentMethodCode.CASH else Decimal(0)
            payment=Payment(invoice_id=invoice.id,payment_method_id=method.id,amount=money(p.amount),tendered_amount=p.tendered_amount,change_amount=change,transaction_reference=p.transaction_reference,status=PaymentStatus.PAID,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(payment); await self.s.flush(); invoice.payment_id=invoice.payment_id or payment.id
            if p.method==PaymentMethodCode.CASH:
                register=await self.s.scalar(select(CashRegister).where(CashRegister.store_id==store.id,CashRegister.status==RegisterStatus.OPEN,CashRegister.deleted_at.is_(None)).with_for_update())
                if register: register.cash_sales=money(register.cash_sales+p.amount)
        invoice.payment_status=PaymentStatus.PAID if paid==grand else PaymentStatus.PARTIAL; invoice.invoice_status=InvoiceStatus.COMPLETED
        inventory_service=InventoryService(self.s,self.actor,self.ip,self.user_agent)
        for item in created_items: await inventory_service.move(locked[item.inventory_id],TransactionType.SALE,-item.quantity,invoice.invoice_number,f"invoice:{invoice.id}:{item.id}",remarks="POS invoice")
        await self.s.flush(); await self.s.refresh(invoice,attribute_names=["items","payments","created_at"])
        from app.services.crm import CustomerCRMIntegration
        await CustomerCRMIntegration(self.s,self.actor,self.ip,self.user_agent).invoice_completed(invoice)
        try: invoice.pdf_path=str(InvoicePDFService().generate(invoice,customer,store))
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
    async def summary(self):
        now=utc_now(); start_day=now.replace(hour=0,minute=0,second=0,microsecond=0); completed=(Invoice.invoice_status.in_([InvoiceStatus.COMPLETED,InvoiceStatus.RETURNED]),)
        async def sales(since): return Decimal(await self.s.scalar(select(func.coalesce(func.sum(Invoice.grand_total),0)).where(*completed,Invoice.created_at>=since)) or 0)
        monthly=await sales(now-timedelta(days=30)); count=int(await self.s.scalar(select(func.count()).select_from(Invoice).where(*completed)) or 0); total=Decimal(await self.s.scalar(select(func.coalesce(func.sum(Invoice.grand_total),0)).where(*completed)) or 0); gst=Decimal(await self.s.scalar(select(func.coalesce(func.sum(Invoice.gst_total),0)).where(*completed)) or 0)
        products=(await self.s.execute(select(InvoiceItem.product_name,func.sum(InvoiceItem.quantity).label("qty")).join(Invoice).where(*completed).group_by(InvoiceItem.product_name).order_by(func.sum(InvoiceItem.quantity).desc()).limit(10))).all()
        methods=(await self.s.execute(select(PaymentMethod.name,func.sum(Payment.amount)).join(Payment).group_by(PaymentMethod.name))).all()
        return BillingAnalytics(today_sales=await sales(start_day),weekly_sales=await sales(now-timedelta(days=7)),monthly_sales=monthly,average_bill=money(total/count) if count else Decimal(0),gst_collected=gst,invoice_count=count,top_products=[{"product":x[0],"quantity":int(x[1])} for x in products],payment_methods=[{"method":x[0],"amount":str(x[1])} for x in methods])
