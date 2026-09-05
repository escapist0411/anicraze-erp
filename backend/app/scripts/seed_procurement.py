import asyncio
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from app.database.session import AsyncSessionFactory
from app.models.auth import User
from app.models.catalog import Product, ProductStatus
from app.models.inventory import Inventory, Warehouse
from app.models.procurement import *
from app.schemas.procurement import *
from app.services.procurement import *

SUPPLIERS=[("Tokyo Collectibles Imports",SupplierType.IMPORT,"Japan",None,"IEC-TCI-2026",Decimal("4.8")),("Otaku Distribution India",SupplierType.DISTRIBUTOR,"India","Maharashtra",None,Decimal("4.5")),("Bandai Authorized Distributor",SupplierType.DISTRIBUTOR,"India","Delhi",None,Decimal("4.7")),("Good Smile Trading",SupplierType.IMPORT,"Japan",None,"IEC-GST-2026",Decimal("4.9")),("Anime Merch Wholesale",SupplierType.WHOLESALER,"India","Maharashtra",None,Decimal("4.2"))]
async def seed():
    async with AsyncSessionFactory() as s:
        owner=await s.scalar(select(User).where(User.email=="owner@anicraze.com")); ss=SupplierService(s,owner); suppliers=[]
        for idx,(name,kind,country,state,iec,rating) in enumerate(SUPPLIERS):
            x=await s.scalar(select(Supplier).where(Supplier.company_name==name))
            if not x: x=await ss.create(SupplierCreateRequest(company_name=name,display_name=name,supplier_type=kind,contact_person=f"Demo Contact {idx+1}",email=f"procurement{idx+1}@example.com",phone=f"90000000{idx+10}",gst_number=f"27ABCDE{idx:04d}F1Z{idx}" if country=="India" else None,import_export_code=iec,country=country,state=state,city="Mumbai" if country=="India" else "Tokyo",billing_address=f"{name} demo address",shipping_address=f"{name} dispatch address",payment_terms_days=30,credit_limit=Decimal("1000000"),currency_code="INR" if country=="India" else "JPY",rating=rating))
            suppliers.append(x)
        warehouse=await s.scalar(select(Warehouse).order_by(Warehouse.code)); products=list((await s.scalars(select(Product).where(Product.deleted_at.is_(None),Product.status==ProductStatus.ACTIVE).order_by(Product.sku).limit(8))).all())
        prs=[]; prs_service=PurchaseRequestService(s,owner)
        if int(await s.scalar(select(func.count()).select_from(PurchaseRequest)) or 0)==0:
            for idx in range(3):
                pr=await prs_service.create(PurchaseRequestCreateRequest(requested_for_warehouse_id=warehouse.id,preferred_supplier_id=suppliers[idx].id,priority=[Priority.NORMAL,Priority.HIGH,Priority.URGENT][idx],required_by_date=date.today()+timedelta(days=14+idx),reason=f"Demo procurement request {idx+1}",items=[PRItemRequest(product_id=products[idx].id,requested_quantity=10+idx*5,estimated_unit_cost=products[idx].purchase_price)])); await prs_service.transition(pr.id,PRStatus.SUBMITTED); await prs_service.transition(pr.id,PRStatus.APPROVED); prs.append(pr)
        pos=[]; po_service=PurchaseOrderService(s,owner)
        if int(await s.scalar(select(func.count()).select_from(PurchaseOrder)) or 0)==0:
            for idx in range(4):
                po=await po_service.create(PurchaseOrderCreateRequest(supplier_id=suppliers[idx].id,purchase_request_id=prs[idx].id if idx<3 else None,destination_warehouse_id=warehouse.id,expected_delivery_date=date.today()+timedelta(days=10+idx),shipping_cost=Decimal("1000") if idx==0 else 0,customs_duty=Decimal("500") if idx==0 else 0,insurance_cost=Decimal("200") if idx==0 else 0,items=[POItemRequest(product_id=products[idx].id,quantity=10,unit_cost=products[idx].purchase_price,discount_percentage=Decimal("2"),gst_rate=products[idx].gst_rate)])); await po_service.transition(po.id,POStatus.SUBMITTED); await po_service.transition(po.id,POStatus.APPROVED); await po_service.transition(po.id,POStatus.SENT); await po_service.transition(po.id,POStatus.CONFIRMED); pos.append(po)
        else: pos=await po_service.repo.list(PurchaseOrder,PurchaseOrder.items)
        grn_service=GRNService(s,owner); completed_grns=[]
        if int(await s.scalar(select(func.count()).select_from(GoodsReceivedNote)) or 0)==0:
            p0=await po_service.repo.get(PurchaseOrder,pos[0].id,PurchaseOrder.items); item=p0.items[0]
            for qty in (4,6):
                g=await grn_service.create(GRNCreateRequest(purchase_order_id=p0.id,items=[GRNItemRequest(purchase_order_item_id=item.id,received_quantity=qty,accepted_quantity=qty-1 if qty==4 else qty,rejected_quantity=0,damaged_quantity=1 if qty==4 else 0,batch_number=f"DEMO-{qty}")])); await grn_service.transition(g.id,GRNStatus.SUBMITTED); await grn_service.transition(g.id,GRNStatus.COMPLETED); completed_grns.append(g)
            p1=await po_service.repo.get(PurchaseOrder,pos[1].id,PurchaseOrder.items); item=p1.items[0]; g=await grn_service.create(GRNCreateRequest(purchase_order_id=p1.id,items=[GRNItemRequest(purchase_order_item_id=item.id,received_quantity=10,accepted_quantity=10)])); await grn_service.transition(g.id,GRNStatus.SUBMITTED); await grn_service.transition(g.id,GRNStatus.COMPLETED); completed_grns.append(g)
        else: completed_grns=await grn_service.repo.list(GoodsReceivedNote,GoodsReceivedNote.items)
        invoice_service=SupplierInvoiceService(s,owner); invoices=[]
        if int(await s.scalar(select(func.count()).select_from(SupplierInvoice)) or 0)==0:
            for idx in range(3):
                po=await po_service.repo.get(PurchaseOrder,pos[idx].id,PurchaseOrder.items); pi=po.items[0]; inv=await invoice_service.create(SupplierInvoiceCreateRequest(supplier_invoice_number=f"DEMO-SUPINV-{idx+1}",supplier_id=po.supplier_id,purchase_order_id=po.id,grn_id=completed_grns[min(idx,len(completed_grns)-1)].id,invoice_date=date.today(),due_date=date.today()+timedelta(days=30),items=[SupplierInvoiceItemRequest(product_id=pi.product_id,quantity=pi.ordered_quantity,unit_cost=pi.unit_cost,gst_rate=pi.gst_rate)])); await invoice_service.action(inv.id,SupplierInvoiceStatus.APPROVED); invoices.append(inv)
        else: invoices=await invoice_service.repo.list(SupplierInvoice,SupplierInvoice.items)
        pay_service=SupplierPaymentService(s,owner)
        if int(await s.scalar(select(func.count()).select_from(SupplierPayment)) or 0)==0:
            for idx in range(2):
                inv=invoices[idx]; await pay_service.create(SupplierPaymentCreateRequest(supplier_id=inv.supplier_id,supplier_invoice_id=inv.id,purchase_order_id=inv.purchase_order_id,payment_method=SupplierPaymentMethod.BANK_TRANSFER,amount=money(inv.outstanding_amount/2),reference_number=f"DEMO-NEFT-{idx+1}"))
        if not await s.scalar(select(LandedCostDocument)):
            doc=LandedCostDocument(document_number="ANI-LC-DEMO-001",purchase_order_id=pos[0].id,grn_id=completed_grns[0].id,allocation_method=AllocationMethod.BY_QUANTITY,total_cost=Decimal("1700"),status="ALLOCATED",created_by_id=owner.id,updated_by_id=owner.id); s.add(doc); await s.flush()
            for kind,amount in (("SHIPPING",1000),("CUSTOMS_DUTY",500),("INSURANCE",200)): s.add(LandedCostComponent(document_id=doc.id,component_type=kind,amount=amount,currency_code="INR"))
        if not await s.scalar(select(PurchaseReturn)):
            stock=await s.scalar(select(Inventory).where(Inventory.warehouse_id==warehouse.id,Inventory.available_quantity>0,Inventory.deleted_at.is_(None)).order_by(Inventory.last_movement_at.desc()))
            ret_service=PurchaseReturnService(s,owner); ret=await ret_service.create(PurchaseReturnCreateRequest(supplier_id=pos[0].supplier_id,purchase_order_id=pos[0].id,grn_id=completed_grns[0].id,supplier_invoice_id=invoices[0].id,source_warehouse_id=warehouse.id,reason="Demo supplier quality return",items=[PurchaseReturnItemRequest(inventory_id=stock.id,quantity=1,unit_cost=stock.average_cost,gst_rate=Decimal("18"),condition="GOOD",reason="Packaging defect")]))
            await ret_service.transition(ret.id,PurchaseReturnStatus.APPROVED); await ret_service.transition(ret.id,PurchaseReturnStatus.DISPATCHED); await ret_service.transition(ret.id,PurchaseReturnStatus.COMPLETED)
        await s.commit()
if __name__=="__main__": asyncio.run(seed())
