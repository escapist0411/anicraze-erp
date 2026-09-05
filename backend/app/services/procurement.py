from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from app.exceptions.domain import ConflictError, NotFoundError
from app.models.auth import AuditLog, User
from app.models.catalog import Product, ProductStatus, ProductVariant
from app.models.inventory import Inventory, InventoryLedger, InventoryTransaction, Store, TransactionType, Warehouse
from app.models.procurement import *
from app.repositories.management import ManagementRepository
from app.repositories.procurement import ProcurementRepository
from app.schemas.inventory import InventoryCreateRequest
from app.schemas.procurement import *
from app.services.billing import GSTService, money
from app.services.inventory import InventoryService
from app.utils.time import utc_now

GST={Decimal("0"),Decimal("5"),Decimal("12"),Decimal("18"),Decimal("28")}
class ProcurementBase:
    def __init__(self,s,actor:User,ip=None,user_agent=None): self.s=s; self.actor=actor; self.repo=ProcurementRepository(s); self.audit_repo=ManagementRepository(s); self.ip=ip; self.user_agent=user_agent
    async def audit(self,action,kind,id,meta=None): await self.audit_repo.audit(AuditLog(actor_user_id=self.actor.id,action=action,entity_type=kind,entity_id=id,metadata_json=meta,ip_address=self.ip,user_agent=self.user_agent,created_at=utc_now()))
    async def supplier(self,id,active=False,lock=False):
        x=await self.repo.supplier(id,lock)
        if not x: raise NotFoundError("Supplier not found","SUPPLIER_NOT_FOUND")
        if active and x.status!=SupplierStatus.ACTIVE: raise ConflictError("Supplier is not active","SUPPLIER_INACTIVE")
        return x
    async def product(self,id,variant=None):
        p=await self.s.scalar(select(Product).where(Product.id==id,Product.deleted_at.is_(None)))
        if not p or p.status!=ProductStatus.ACTIVE: raise ConflictError("Product is inactive or deleted","PROCUREMENT_PRODUCT_INVALID")
        if variant and not await self.s.scalar(select(ProductVariant).where(ProductVariant.id==variant,ProductVariant.product_id==id,ProductVariant.deleted_at.is_(None))): raise ConflictError("Variant does not belong to product","PROCUREMENT_VARIANT_INVALID")
        return p
    async def location(self,store_id,warehouse_id):
        if (store_id is None)==(warehouse_id is None): raise ConflictError("Exactly one destination is required","PROCUREMENT_DESTINATION_INVALID")
        model,id=(Store,store_id) if store_id else (Warehouse,warehouse_id)
        if not await self.s.scalar(select(model).where(model.id==id,model.deleted_at.is_(None))): raise NotFoundError("Destination not found","PROCUREMENT_DESTINATION_NOT_FOUND")

class SupplierService(ProcurementBase):
    async def create(self,data):
        if data.gst_number and await self.s.scalar(select(Supplier).where(Supplier.gst_number==data.gst_number)): raise ConflictError("Supplier GST number already exists","SUPPLIER_GST_EXISTS")
        x=Supplier(supplier_code=await self.repo.next_number("supplier","ANI-SUP"),**data.model_dump(),outstanding_balance=data.opening_balance,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(x); await self.s.flush(); await self.audit("SUPPLIER_CREATED","supplier",x.id,{"code":x.supplier_code}); return x
    async def update(self,id,data):
        x=await self.supplier(id,lock=True); values=data.model_dump(exclude_unset=True); [setattr(x,k,v) for k,v in values.items()]; x.updated_by_id=self.actor.id; await self.audit("SUPPLIER_UPDATED","supplier",x.id,{"fields":list(values)}); return x
    async def status(self,id,status,reason=None): x=await self.supplier(id,lock=True); old=x.status; x.status=status; x.updated_by_id=self.actor.id; await self.audit("SUPPLIER_STATUS_CHANGED","supplier",x.id,{"from":old.value,"to":status.value,"reason":reason}); return x
    async def delete(self,id): x=await self.supplier(id,lock=True); x.deleted_at=utc_now(); x.status=SupplierStatus.ARCHIVED; await self.audit("SUPPLIER_DELETED","supplier",x.id)

class PurchaseRequestService(ProcurementBase):
    async def create(self,data):
        await self.location(data.requested_for_store_id,data.requested_for_warehouse_id)
        if data.preferred_supplier_id: await self.supplier(data.preferred_supplier_id,active=True)
        pr=PurchaseRequest(request_number=await self.repo.next_number("purchase_request","ANI-PR"),requested_by_id=self.actor.id,**data.model_dump(exclude={"items"}),status=PRStatus.DRAFT,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(pr); await self.s.flush()
        for item in data.items: await self.product(item.product_id,item.product_variant_id); self.s.add(PurchaseRequestItem(purchase_request_id=pr.id,**item.model_dump(),approved_quantity=0,estimated_total=money(item.requested_quantity*item.estimated_unit_cost)))
        await self.s.flush(); await self.s.refresh(pr,attribute_names=["items"]); await self.audit("PURCHASE_REQUEST_CREATED","purchase_request",pr.id); return pr
    async def update(self,id,data):
        pr=await self.repo.get(PurchaseRequest,id,PurchaseRequest.items,True)
        if not pr: raise NotFoundError("Purchase request not found","PURCHASE_REQUEST_NOT_FOUND")
        if pr.status!=PRStatus.DRAFT: raise ConflictError("Only draft requests can be edited","PURCHASE_REQUEST_EDIT_PROTECTED")
        values=data.model_dump(exclude_unset=True); [setattr(pr,k,v) for k,v in values.items()]; pr.updated_by_id=self.actor.id; await self.audit("PURCHASE_REQUEST_UPDATED","purchase_request",pr.id,{"fields":list(values)}); return pr
    async def transition(self,id,target,reason=None,quantities=None):
        pr=await self.repo.get(PurchaseRequest,id,PurchaseRequest.items,True)
        if not pr: raise NotFoundError("Purchase request not found","PURCHASE_REQUEST_NOT_FOUND")
        allowed={PRStatus.DRAFT:{PRStatus.SUBMITTED,PRStatus.CANCELLED},PRStatus.SUBMITTED:{PRStatus.APPROVED,PRStatus.PARTIALLY_APPROVED,PRStatus.REJECTED}}
        if target not in allowed.get(pr.status,set()): raise ConflictError("Invalid purchase request transition","PURCHASE_REQUEST_STATUS_INVALID")
        old=pr.status; pr.status=target; now=utc_now()
        if target==PRStatus.SUBMITTED: pr.submitted_at=now
        if target in {PRStatus.APPROVED,PRStatus.PARTIALLY_APPROVED}:
            pr.approved_by_id=self.actor.id; pr.approved_at=now
            for item in pr.items: item.approved_quantity=(quantities or {}).get(item.id,item.requested_quantity)
            if any(i.approved_quantity<=0 for i in pr.items): pr.status=PRStatus.PARTIALLY_APPROVED
        if target==PRStatus.REJECTED: pr.rejected_by_id=self.actor.id; pr.rejected_at=now; pr.rejection_reason=reason
        await self.audit(f"PURCHASE_REQUEST_{pr.status.value}","purchase_request",pr.id,{"from":old.value,"reason":reason}); return pr

class PurchaseOrderService(ProcurementBase):
    async def create(self,data):
        supplier=await self.supplier(data.supplier_id,active=True); await self.location(data.destination_store_id,data.destination_warehouse_id)
        po=PurchaseOrder(po_number=await self.repo.next_number(f"po:{date.today().year}",f"ANI-PO-{date.today().year}"),supplier_id=supplier.id,purchase_request_id=data.purchase_request_id,destination_store_id=data.destination_store_id,destination_warehouse_id=data.destination_warehouse_id,order_date=date.today(),expected_delivery_date=data.expected_delivery_date,currency_code=data.currency_code,exchange_rate=data.exchange_rate,subtotal=0,discount_total=0,taxable_amount=0,cgst=0,sgst=0,igst=0,tax_total=0,shipping_cost=data.shipping_cost,customs_duty=data.customs_duty,insurance_cost=data.insurance_cost,handling_cost=data.handling_cost,miscellaneous_cost=data.miscellaneous_cost,grand_total=0,amount_paid=0,outstanding_amount=0,payment_terms_days=supplier.payment_terms_days,payment_due_date=date.today()+timedelta(days=supplier.payment_terms_days),status=POStatus.DRAFT,payment_status=POPaymentStatus.UNPAID,supplier_reference=data.supplier_reference,notes=data.notes,terms_and_conditions=data.terms_and_conditions,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(po); await self.s.flush(); subtotal=discount=taxable=cgst=sgst=igst=Decimal(0); interstate=supplier.country!="India" or (supplier.state or "").casefold() not in {"maharashtra","mh"}
        for req in data.items:
            await self.product(req.product_id,req.product_variant_id)
            if req.gst_rate not in GST: raise ConflictError("Invalid GST rate","PURCHASE_ORDER_GST_INVALID")
            gross=money(req.quantity*req.unit_cost); disc=money(gross*req.discount_percentage/100); base=money(gross-disc); c,s,i=GSTService.calculate(base,req.gst_rate,interstate); tax=c+s+i
            self.s.add(PurchaseOrderItem(purchase_order_id=po.id,product_id=req.product_id,product_variant_id=req.product_variant_id,ordered_quantity=req.quantity,received_quantity=0,rejected_quantity=0,returned_quantity=0,pending_quantity=req.quantity,unit_cost=req.unit_cost,discount_percentage=req.discount_percentage,discount_amount=disc,taxable_amount=base,gst_rate=req.gst_rate,cgst=c,sgst=s,igst=i,tax_amount=tax,line_total=money(base+tax),remarks=req.remarks)); subtotal+=gross; discount+=disc; taxable+=base; cgst+=c; sgst+=s; igst+=i
        additional=data.shipping_cost+data.customs_duty+data.insurance_cost+data.handling_cost+data.miscellaneous_cost; grand=money(taxable+cgst+sgst+igst+additional); po.subtotal=money(subtotal); po.discount_total=money(discount); po.taxable_amount=money(taxable); po.cgst=money(cgst); po.sgst=money(sgst); po.igst=money(igst); po.tax_total=money(cgst+sgst+igst); po.grand_total=grand; po.outstanding_amount=grand; await self.s.flush(); await self.s.refresh(po,attribute_names=["items"]); await self.audit("PURCHASE_ORDER_CREATED","purchase_order",po.id,{"number":po.po_number}); return po
    async def update(self,id,data):
        po=await self.repo.get(PurchaseOrder,id,PurchaseOrder.items,True)
        if not po: raise NotFoundError("Purchase order not found","PURCHASE_ORDER_NOT_FOUND")
        if po.status!=POStatus.DRAFT: raise ConflictError("Only draft orders can be edited","PURCHASE_ORDER_EDIT_PROTECTED")
        values=data.model_dump(exclude_unset=True); [setattr(po,k,v) for k,v in values.items()]; po.updated_by_id=self.actor.id; await self.audit("PURCHASE_ORDER_UPDATED","purchase_order",po.id,{"fields":list(values)}); return po
    async def transition(self,id,target,reason=None):
        po=await self.repo.get(PurchaseOrder,id,PurchaseOrder.items,True)
        if not po: raise NotFoundError("Purchase order not found","PURCHASE_ORDER_NOT_FOUND")
        allowed={POStatus.DRAFT:{POStatus.SUBMITTED,POStatus.CANCELLED},POStatus.SUBMITTED:{POStatus.APPROVED,POStatus.REJECTED},POStatus.APPROVED:{POStatus.SENT,POStatus.CANCELLED},POStatus.SENT:{POStatus.CONFIRMED,POStatus.CANCELLED},POStatus.CONFIRMED:{POStatus.CANCELLED},POStatus.RECEIVED:{POStatus.CLOSED}}
        if target not in allowed.get(po.status,set()): raise ConflictError("Invalid purchase order transition","PURCHASE_ORDER_STATUS_INVALID")
        old=po.status; po.status=target; now=utc_now()
        if target==POStatus.APPROVED: po.approved_by_id=self.actor.id; po.approved_at=now
        if target==POStatus.SENT: po.sent_at=now
        if target==POStatus.CONFIRMED: po.confirmed_at=now
        if target==POStatus.CANCELLED: po.cancelled_at=now; po.notes=((po.notes or "")+f"\nCancellation: {reason or 'not provided'}").strip()
        if target==POStatus.CLOSED: po.closed_at=now
        await self.audit(f"PURCHASE_ORDER_{target.value}","purchase_order",po.id,{"from":old.value,"reason":reason}); return po
    async def from_request(self,pr_id,supplier_id=None):
        prs=PurchaseRequestService(self.s,self.actor,self.ip,self.user_agent); pr=await prs.repo.get(PurchaseRequest,pr_id,PurchaseRequest.items,True)
        if not pr or pr.status not in {PRStatus.APPROVED,PRStatus.PARTIALLY_APPROVED}: raise ConflictError("Purchase request is not approved","PURCHASE_REQUEST_CONVERSION_INVALID")
        data=PurchaseOrderCreateRequest(supplier_id=supplier_id or pr.preferred_supplier_id,destination_store_id=pr.requested_for_store_id,destination_warehouse_id=pr.requested_for_warehouse_id,purchase_request_id=pr.id,items=[POItemRequest(product_id=i.product_id,product_variant_id=i.product_variant_id,quantity=i.approved_quantity,unit_cost=i.estimated_unit_cost,gst_rate=Decimal("18")) for i in pr.items if i.approved_quantity>0]); po=await self.create(data); pr.status=PRStatus.CONVERTED_TO_PO; await self.audit("PURCHASE_REQUEST_CONVERTED","purchase_request",pr.id,{"po_id":str(po.id)}); return po

class GRNService(ProcurementBase):
    async def create(self,data):
        po=await self.repo.get(PurchaseOrder,data.purchase_order_id,PurchaseOrder.items,True)
        if not po or po.status not in {POStatus.CONFIRMED,POStatus.PARTIALLY_RECEIVED}: raise ConflictError("Purchase order cannot be received","GRN_PO_STATUS_INVALID")
        by_id={x.id:x for x in po.items}; grn=GoodsReceivedNote(grn_number=await self.repo.next_number(f"grn:{date.today().year}",f"ANI-GRN-{date.today().year}"),purchase_order_id=po.id,supplier_id=po.supplier_id,store_id=po.destination_store_id,warehouse_id=po.destination_warehouse_id,received_date=data.received_date,received_by_id=self.actor.id,supplier_invoice_number=data.supplier_invoice_number,supplier_challan_number=data.supplier_challan_number,status=GRNStatus.DRAFT,total_received_quantity=0,total_accepted_quantity=0,total_rejected_quantity=0,total_damaged_quantity=0,notes=data.notes,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(grn); await self.s.flush()
        totals=[0,0,0,0]
        for req in data.items:
            item=by_id.get(req.purchase_order_item_id)
            if not item: raise ConflictError("GRN item is not on purchase order","GRN_ITEM_INVALID")
            if req.accepted_quantity+req.rejected_quantity+req.damaged_quantity!=req.received_quantity: raise ConflictError("Accepted, rejected and damaged must equal received","GRN_QUANTITY_BREAKDOWN_INVALID")
            if req.received_quantity>item.pending_quantity: raise ConflictError("Receipt exceeds pending quantity","GRN_OVER_RECEIPT")
            self.s.add(GRNItem(grn_id=grn.id,purchase_order_item_id=item.id,product_id=item.product_id,product_variant_id=item.product_variant_id,ordered_quantity=item.ordered_quantity,previously_received_quantity=item.received_quantity,received_quantity=req.received_quantity,accepted_quantity=req.accepted_quantity,rejected_quantity=req.rejected_quantity,damaged_quantity=req.damaged_quantity,pending_quantity=item.pending_quantity-req.received_quantity,unit_cost=item.unit_cost,batch_number=req.batch_number,rejection_reason=req.rejection_reason,damage_reason=req.damage_reason,storage_location=req.storage_location,notes=req.notes)); totals=[totals[i]+v for i,v in enumerate((req.received_quantity,req.accepted_quantity,req.rejected_quantity,req.damaged_quantity))]
        grn.total_received_quantity,grn.total_accepted_quantity,grn.total_rejected_quantity,grn.total_damaged_quantity=totals; await self.s.flush(); await self.s.refresh(grn,attribute_names=["items"]); await self.audit("GRN_CREATED","grn",grn.id); return grn
    async def update(self,id,data):
        grn=await self.repo.get(GoodsReceivedNote,id,GoodsReceivedNote.items,True)
        if not grn: raise NotFoundError("GRN not found","GRN_NOT_FOUND")
        if grn.status!=GRNStatus.DRAFT: raise ConflictError("Only draft GRNs can be edited","GRN_EDIT_PROTECTED")
        values=data.model_dump(exclude_unset=True); [setattr(grn,k,v) for k,v in values.items()]; await self.audit("GRN_UPDATED","grn",grn.id,{"fields":list(values)}); return grn
    async def transition(self,id,target):
        grn=await self.repo.get(GoodsReceivedNote,id,GoodsReceivedNote.items,True)
        if not grn: raise NotFoundError("GRN not found","GRN_NOT_FOUND")
        if target==GRNStatus.SUBMITTED and grn.status==GRNStatus.DRAFT: grn.status=target; await self.audit("GRN_SUBMITTED","grn",grn.id); return grn
        if target==GRNStatus.CANCELLED and grn.status in {GRNStatus.DRAFT,GRNStatus.SUBMITTED}: grn.status=target; await self.audit("GRN_CANCELLED","grn",grn.id); return grn
        if target!=GRNStatus.COMPLETED or grn.status!=GRNStatus.SUBMITTED: raise ConflictError("Invalid GRN transition","GRN_STATUS_INVALID")
        po=await self.repo.get(PurchaseOrder,grn.purchase_order_id,PurchaseOrder.items,True); po_items={x.id:x for x in po.items}; inv_service=InventoryService(self.s,self.actor,self.ip,self.user_agent)
        for item in sorted(grn.items,key=lambda x:str(x.purchase_order_item_id)):
            poi=po_items[item.purchase_order_item_id]
            if item.received_quantity>poi.pending_quantity: raise ConflictError("Concurrent receipt exceeded pending quantity","GRN_OVER_RECEIPT")
            inv=await inv_service.repo.find(item.product_id,item.product_variant_id,grn.store_id,grn.warehouse_id,True)
            if not inv: inv=await inv_service.create(InventoryCreateRequest(product_id=item.product_id,variant_id=item.product_variant_id,store_id=grn.store_id,warehouse_id=grn.warehouse_id,average_cost=item.unit_cost))
            if item.accepted_quantity: await inv_service.move(inv,TransactionType.PURCHASE,item.accepted_quantity,grn.grn_number,f"grn:{grn.id}:accepted:{item.id}",item.unit_cost,item.batch_number,"GRN accepted stock")
            if item.damaged_quantity:
                await inv_service.move(inv,TransactionType.PURCHASE,item.damaged_quantity,grn.grn_number,f"grn:{grn.id}:damaged-in:{item.id}",item.unit_cost,item.batch_number,"GRN damaged receipt")
                await inv_service.move(inv,TransactionType.DAMAGE,-item.damaged_quantity,grn.grn_number,f"grn:{grn.id}:damaged:{item.id}",item.unit_cost,item.batch_number,"GRN damaged stock")
            poi.received_quantity+=item.received_quantity; poi.rejected_quantity+=item.rejected_quantity; poi.pending_quantity-=item.received_quantity
        grn.status=GRNStatus.COMPLETED; grn.completed_at=utc_now(); po.status=POStatus.RECEIVED if all(x.pending_quantity==0 for x in po.items) else POStatus.PARTIALLY_RECEIVED; await self.audit("GRN_COMPLETED","grn",grn.id,{"po_status":po.status.value}); return grn

class SupplierInvoiceService(ProcurementBase):
    async def create(self,data):
        if data.due_date<data.invoice_date: raise ConflictError("Due date cannot precede invoice date","SUPPLIER_INVOICE_DUE_DATE_INVALID")
        supplier=await self.supplier(data.supplier_id,active=True)
        if await self.s.scalar(select(SupplierInvoice).where(SupplierInvoice.supplier_id==supplier.id,SupplierInvoice.supplier_invoice_number==data.supplier_invoice_number)): raise ConflictError("Duplicate supplier invoice","SUPPLIER_INVOICE_EXISTS")
        subtotal=tax=Decimal(0)
        for item in data.items:
            await self.product(item.product_id); 
            if item.gst_rate not in GST: raise ConflictError("Invalid GST rate","SUPPLIER_INVOICE_GST_INVALID")
            subtotal+=money(item.quantity*item.unit_cost); tax+=money(item.quantity*item.unit_cost*item.gst_rate/100)
        interstate=supplier.country!="India" or (supplier.state or "").casefold() not in {"maharashtra","mh"}; cgst=Decimal(0) if interstate else money(tax/2); sgst=Decimal(0) if interstate else tax-cgst; igst=tax if interstate else Decimal(0); grand=money(subtotal+tax+data.shipping_cost+data.customs_duty+data.other_charges)
        inv=SupplierInvoice(supplier_invoice_number=data.supplier_invoice_number,internal_invoice_number=await self.repo.next_number(f"supplier_invoice:{date.today().year}",f"ANI-SINV-{date.today().year}"),supplier_id=supplier.id,purchase_order_id=data.purchase_order_id,grn_id=data.grn_id,invoice_date=data.invoice_date,due_date=data.due_date,currency_code=data.currency_code,subtotal=subtotal,discount_total=0,taxable_amount=subtotal,cgst=cgst,sgst=sgst,igst=igst,tax_total=tax,shipping_cost=data.shipping_cost,customs_duty=data.customs_duty,other_charges=data.other_charges,grand_total=grand,amount_paid=0,outstanding_amount=grand,status=SupplierInvoiceStatus.DRAFT,payment_status=POPaymentStatus.UNPAID,notes=data.notes,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(inv); await self.s.flush()
        for item in data.items:
            base=money(item.quantity*item.unit_cost); t=money(base*item.gst_rate/100); self.s.add(SupplierInvoiceItem(supplier_invoice_id=inv.id,product_id=item.product_id,quantity=item.quantity,unit_cost=item.unit_cost,gst_rate=item.gst_rate,taxable_amount=base,tax_amount=t,line_total=base+t))
        await self.s.flush(); await self.s.refresh(inv,attribute_names=["items"]); await self.audit("SUPPLIER_INVOICE_CREATED","supplier_invoice",inv.id); return inv
    async def update(self,id,data):
        inv=await self.repo.get(SupplierInvoice,id,SupplierInvoice.items,True)
        if not inv: raise NotFoundError("Supplier invoice not found","SUPPLIER_INVOICE_NOT_FOUND")
        if inv.status!=SupplierInvoiceStatus.DRAFT: raise ConflictError("Only draft invoices can be edited","SUPPLIER_INVOICE_EDIT_PROTECTED")
        values=data.model_dump(exclude_unset=True)
        if values.get("due_date") and values["due_date"]<inv.invoice_date: raise ConflictError("Due date cannot precede invoice date","SUPPLIER_INVOICE_DUE_DATE_INVALID")
        [setattr(inv,k,v) for k,v in values.items()]; await self.audit("SUPPLIER_INVOICE_UPDATED","supplier_invoice",inv.id,{"fields":list(values)}); return inv
    async def action(self,id,target):
        inv=await self.repo.get(SupplierInvoice,id,SupplierInvoice.items,True)
        if not inv: raise NotFoundError("Supplier invoice not found","SUPPLIER_INVOICE_NOT_FOUND")
        if target==SupplierInvoiceStatus.APPROVED and inv.status in {SupplierInvoiceStatus.DRAFT,SupplierInvoiceStatus.SUBMITTED}: inv.status=target; inv.approved_by_id=self.actor.id; inv.approved_at=utc_now(); supplier=await self.supplier(inv.supplier_id,lock=True); supplier.outstanding_balance+=inv.outstanding_amount
        elif target==SupplierInvoiceStatus.CANCELLED and inv.status==SupplierInvoiceStatus.DRAFT: inv.status=target
        else: raise ConflictError("Invalid supplier invoice transition","SUPPLIER_INVOICE_STATUS_INVALID")
        await self.audit(f"SUPPLIER_INVOICE_{target.value}","supplier_invoice",inv.id); return inv

class SupplierPaymentService(ProcurementBase):
    async def create(self,data):
        supplier=await self.supplier(data.supplier_id,active=True,lock=True); invoice=None
        if data.supplier_invoice_id:
            invoice=await self.repo.get(SupplierInvoice,data.supplier_invoice_id,SupplierInvoice.items,True)
            if not invoice or invoice.supplier_id!=supplier.id or invoice.status!=SupplierInvoiceStatus.APPROVED: raise ConflictError("Supplier invoice is not payable","SUPPLIER_PAYMENT_INVOICE_INVALID")
            if data.amount>invoice.outstanding_amount: raise ConflictError("Payment exceeds outstanding amount","SUPPLIER_PAYMENT_OVERPAYMENT")
        payment=SupplierPayment(payment_number=await self.repo.next_number(f"supplier_payment:{date.today().year}",f"ANI-SPAY-{date.today().year}"),**data.model_dump(),status=SupplierPaymentStatus.COMPLETED,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(payment)
        if invoice:
            invoice.amount_paid+=data.amount; invoice.outstanding_amount-=data.amount; invoice.payment_status=POPaymentStatus.PAID if invoice.outstanding_amount==0 else POPaymentStatus.PARTIAL
        supplier.outstanding_balance-=data.amount
        if supplier.outstanding_balance<0: raise ConflictError("Payment exceeds supplier outstanding balance","SUPPLIER_PAYMENT_OVERPAYMENT")
        await self.s.flush(); await self.audit("SUPPLIER_PAYMENT_CREATED","supplier_payment",payment.id,{"amount":str(data.amount)}); return payment
    async def reverse(self,id,reason):
        p=await self.repo.get(SupplierPayment,id,lock=True)
        if not p: raise NotFoundError("Supplier payment not found","SUPPLIER_PAYMENT_NOT_FOUND")
        if p.status!=SupplierPaymentStatus.COMPLETED: raise ConflictError("Payment is already reversed or cancelled","SUPPLIER_PAYMENT_REVERSAL_INVALID")
        supplier=await self.supplier(p.supplier_id,lock=True); supplier.outstanding_balance+=p.amount
        if p.supplier_invoice_id:
            inv=await self.repo.get(SupplierInvoice,p.supplier_invoice_id,SupplierInvoice.items,True); inv.amount_paid-=p.amount; inv.outstanding_amount+=p.amount; inv.payment_status=POPaymentStatus.UNPAID if inv.amount_paid==0 else POPaymentStatus.PARTIAL
        p.status=SupplierPaymentStatus.REVERSED; p.reversed_by_id=self.actor.id; p.reversed_at=utc_now(); p.reversal_reason=reason; await self.audit("SUPPLIER_PAYMENT_REVERSED","supplier_payment",p.id,{"reason":reason}); return p

class PurchaseReturnService(ProcurementBase):
    async def create(self,data):
        await self.supplier(data.supplier_id,active=True); await self.location(data.source_store_id,data.source_warehouse_id); subtotal=tax=Decimal(0); ret=PurchaseReturn(return_number=await self.repo.next_number(f"purchase_return:{date.today().year}",f"ANI-PRET-{date.today().year}"),supplier_id=data.supplier_id,purchase_order_id=data.purchase_order_id,grn_id=data.grn_id,supplier_invoice_id=data.supplier_invoice_id,source_store_id=data.source_store_id,source_warehouse_id=data.source_warehouse_id,return_date=data.return_date,reason=data.reason,status=PurchaseReturnStatus.DRAFT,subtotal=0,tax_reversal=0,total_amount=0,refund_status=PurchaseRefundStatus.PENDING,notes=data.notes,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.s.add(ret); await self.s.flush()
        for req in data.items:
            inv=await self.s.scalar(select(Inventory).where(Inventory.id==req.inventory_id,Inventory.deleted_at.is_(None)))
            if not inv or inv.store_id!=data.source_store_id or inv.warehouse_id!=data.source_warehouse_id: raise ConflictError("Return inventory location mismatch","PURCHASE_RETURN_INVENTORY_INVALID")
            base=money(req.quantity*req.unit_cost); t=money(base*req.gst_rate/100); self.s.add(PurchaseReturnItem(purchase_return_id=ret.id,product_id=inv.product_id,product_variant_id=inv.variant_id,inventory_id=inv.id,quantity=req.quantity,unit_cost=req.unit_cost,tax_amount=t,line_total=base+t,condition=req.condition,reason=req.reason,batch_number=req.batch_number)); subtotal+=base; tax+=t
        ret.subtotal=subtotal; ret.tax_reversal=tax; ret.total_amount=money(subtotal+tax); await self.s.flush(); await self.s.refresh(ret,attribute_names=["items"]); await self.audit("PURCHASE_RETURN_CREATED","purchase_return",ret.id); return ret
    async def update(self,id,data):
        ret=await self.repo.get(PurchaseReturn,id,PurchaseReturn.items,True)
        if not ret: raise NotFoundError("Purchase return not found","PURCHASE_RETURN_NOT_FOUND")
        if ret.status!=PurchaseReturnStatus.DRAFT: raise ConflictError("Only draft returns can be edited","PURCHASE_RETURN_EDIT_PROTECTED")
        values=data.model_dump(exclude_unset=True); [setattr(ret,k,v) for k,v in values.items()]; await self.audit("PURCHASE_RETURN_UPDATED","purchase_return",ret.id,{"fields":list(values)}); return ret
    async def transition(self,id,target):
        ret=await self.repo.get(PurchaseReturn,id,PurchaseReturn.items,True)
        if not ret: raise NotFoundError("Purchase return not found","PURCHASE_RETURN_NOT_FOUND")
        allowed={PurchaseReturnStatus.DRAFT:{PurchaseReturnStatus.SUBMITTED,PurchaseReturnStatus.APPROVED,PurchaseReturnStatus.CANCELLED},PurchaseReturnStatus.SUBMITTED:{PurchaseReturnStatus.APPROVED,PurchaseReturnStatus.CANCELLED},PurchaseReturnStatus.APPROVED:{PurchaseReturnStatus.DISPATCHED},PurchaseReturnStatus.DISPATCHED:{PurchaseReturnStatus.COMPLETED}}
        if target not in allowed.get(ret.status,set()): raise ConflictError("Invalid purchase return transition","PURCHASE_RETURN_STATUS_INVALID")
        ret.status=target; now=utc_now()
        if target==PurchaseReturnStatus.APPROVED: ret.approved_by_id=self.actor.id; ret.approved_at=now
        if target==PurchaseReturnStatus.DISPATCHED: ret.dispatched_at=now
        if target==PurchaseReturnStatus.COMPLETED:
            inv_service=InventoryService(self.s,self.actor,self.ip,self.user_agent)
            for item in sorted(ret.items,key=lambda x:str(x.inventory_id)):
                inv=await inv_service.get(item.inventory_id,True)
                if item.condition.upper()=="DAMAGED":
                    if inv.damaged_quantity<item.quantity: raise ConflictError("Insufficient damaged stock","PURCHASE_RETURN_INSUFFICIENT_STOCK")
                    before=inv.available_quantity; inv.damaged_quantity-=item.quantity; tx=InventoryTransaction(idempotency_key=f"purchase-return:{ret.id}:{item.id}",inventory_id=inv.id,product_id=inv.product_id,store_id=inv.store_id,warehouse_id=inv.warehouse_id,transaction_type=TransactionType.TRANSFER_OUT,quantity=item.quantity,unit_cost=item.unit_cost,reference_number=ret.return_number,batch_number=item.batch_number,remarks="Damaged purchase return",created_by_id=self.actor.id); self.s.add(tx); await self.s.flush(); self.s.add(InventoryLedger(transaction_id=tx.id,inventory_id=inv.id,product_id=inv.product_id,store_id=inv.store_id,warehouse_id=inv.warehouse_id,transaction_type=TransactionType.TRANSFER_OUT,quantity_before=before,quantity_changed=0,quantity_after=before,reference_number=ret.return_number,batch_number=item.batch_number,created_by_id=self.actor.id,created_at=now))
                else: await inv_service.move(inv,TransactionType.TRANSFER_OUT,-item.quantity,ret.return_number,f"purchase-return:{ret.id}:{item.id}",item.unit_cost,item.batch_number,"Purchase return")
            supplier=await self.supplier(ret.supplier_id,lock=True); supplier.outstanding_balance=max(Decimal(0),supplier.outstanding_balance-ret.total_amount); ret.completed_at=now; ret.refund_status=PurchaseRefundStatus.ADJUSTED_AGAINST_BALANCE
        await self.audit(f"PURCHASE_RETURN_{target.value}","purchase_return",ret.id); return ret

class SupplierStatementService(ProcurementBase):
    async def statement(self,id):
        supplier=await self.supplier(id); invoices=await self.repo.list(SupplierInvoice,supplier_id=id); payments=await self.repo.list(SupplierPayment,supplier_id=id); returns=await self.repo.list(PurchaseReturn,supplier_id=id); entries=[]; balance=supplier.opening_balance
        for x in invoices: entries.append((x.created_at,"INVOICE",x.internal_invoice_number,x.grand_total))
        for x in payments:
            if x.status==SupplierPaymentStatus.COMPLETED: entries.append((x.created_at,"PAYMENT",x.payment_number,-x.amount))
        for x in returns:
            if x.status==PurchaseReturnStatus.COMPLETED: entries.append((x.created_at,"RETURN",x.return_number,-x.total_amount))
        output=[]
        for dt,kind,ref,amount in sorted(entries): balance+=amount; output.append({"date":dt.isoformat(),"type":kind,"reference":ref,"amount":str(amount),"running_balance":str(balance)})
        return {"supplier_id":str(id),"opening_balance":str(supplier.opening_balance),"entries":output,"closing_balance":str(balance)}
class SupplierPerformanceService(ProcurementBase):
    async def performance(self,id):
        supplier=await self.supplier(id); orders=await self.repo.list(PurchaseOrder,PurchaseOrder.items,id); received=[x for x in orders if x.status in {POStatus.RECEIVED,POStatus.CLOSED}]; ontime=sum(bool(x.expected_delivery_date and x.updated_at.date()<=x.expected_delivery_date) for x in received); ordered=sum(i.ordered_quantity for x in orders for i in x.items); rejected=sum(i.rejected_quantity for x in orders for i in x.items); returned=sum(i.returned_quantity for x in orders for i in x.items); delivery=100*ontime/len(received) if received else 100; quality=100*(1-(rejected+returned)/ordered) if ordered else 100; score=round(.45*delivery+.35*quality+.20*float(supplier.rating/5*100),2); return {"supplier_id":str(id),"total_purchase_value":str(sum((x.grand_total for x in orders),Decimal(0))),"purchase_order_count":len(orders),"on_time_delivery_rate":round(delivery,2),"rejection_rate":round(100*rejected/ordered,2) if ordered else 0,"return_rate":round(100*returned/ordered,2) if ordered else 0,"open_orders":sum(x.status not in {POStatus.CLOSED,POStatus.CANCELLED,POStatus.RECEIVED} for x in orders),"outstanding_balance":str(supplier.outstanding_balance),"performance_score":score,"weights":{"delivery":.45,"quality":.35,"rating":.20}}
class ProcurementAnalyticsService(ProcurementBase):
    async def dashboard(self):
        now=utc_now(); month=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0); po_value=Decimal(await self.s.scalar(select(func.coalesce(func.sum(PurchaseOrder.grand_total),0)).where(PurchaseOrder.created_at>=month,PurchaseOrder.status.notin_([POStatus.DRAFT,POStatus.CANCELLED]))) or 0); return {"purchase_value_this_month":str(po_value),"purchase_orders_this_month":int(await self.s.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.created_at>=month)) or 0),"pending_requests":int(await self.s.scalar(select(func.count()).select_from(PurchaseRequest).where(PurchaseRequest.status==PRStatus.SUBMITTED)) or 0),"pending_deliveries":int(await self.s.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.status.in_([POStatus.CONFIRMED,POStatus.PARTIALLY_RECEIVED]))) or 0),"partially_received_orders":int(await self.s.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.status==POStatus.PARTIALLY_RECEIVED)) or 0),"outstanding_supplier_payments":str(await self.s.scalar(select(func.coalesce(func.sum(Supplier.outstanding_balance),0))) or 0),"overdue_supplier_invoices":int(await self.s.scalar(select(func.count()).select_from(SupplierInvoice).where(SupplierInvoice.due_date<date.today(),SupplierInvoice.outstanding_amount>0)) or 0),"purchase_returns":int(await self.s.scalar(select(func.count()).select_from(PurchaseReturn)) or 0)}
class ProcurementPDFService:
    root=Path(__file__).resolve().parents[2]/"generated"/"procurement"
    def generate(self,number,title,status,rows,totals=None):
        self.root.mkdir(parents=True,exist_ok=True); path=self.root/f"{number}.pdf"; styles=getSampleStyleSheet(); story=[Paragraph("<b>ANICRAZE</b>",styles["Title"]),Paragraph(title,styles["Heading2"]),Paragraph(f"Document: {number}<br/>Status: {status}<br/>Generated: {utc_now():%d %b %Y %H:%M UTC}",styles["BodyText"]),Spacer(1,5*mm),Table(rows,repeatRows=1)]
        if totals: story += [Spacer(1,4*mm),Paragraph(totals,styles["Heading3"])]
        story += [Spacer(1,6*mm),Paragraph("Computer-generated procurement document. Subject to ANICRAZE purchasing terms.",styles["BodyText"])]; SimpleDocTemplate(str(path),pagesize=A4,leftMargin=14*mm,rightMargin=14*mm).build(story); return path
