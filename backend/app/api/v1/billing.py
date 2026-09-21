from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from app.dependencies.auth import DatabaseSession
from app.exceptions.domain import AuthorizationError, ConflictError, NotFoundError
from app.models.auth import User
from app.models.billing import CashRegister, InvoiceTax
from app.models.auth import AuditLog
from app.models.catalog import Anime, Character, Product
from app.models.inventory import Inventory
from app.permissions.dependencies import require_permission
from app.schemas.billing import *
from app.schemas.common import APIResponse
from app.services.billing import BillingAnalyticsService, BillingService, ReturnService
from app.services.communications import dispatch_invoice_background

router=APIRouter(tags=["Billing and POS"])
def svc(cls,s,a,r): return cls(s,a,r.client.host if r.client else None,r.headers.get("user-agent"))
def scoped_store(actor:User,requested:UUID):
    if actor.assigned_store_id is not None and actor.assigned_store_id!=requested: raise AuthorizationError("Billing is restricted to your assigned shop","BILLING_STORE_SCOPE_DENIED")
    return requested

@router.get("/billing/search",response_model=APIResponse[list[BarcodeResult]])
async def product_search(session:DatabaseSession,store_id:UUID,query:str=Query(min_length=1),actor:User=Depends(require_permission("billing.read"))):
    scoped_store(actor,store_id)
    term=f"%{query}%"; q=select(Inventory).options(selectinload(Inventory.product).selectinload(Product.anime),selectinload(Inventory.product).selectinload(Product.character),selectinload(Inventory.variant)).join(Product).where(Inventory.store_id==store_id,Inventory.available_quantity>0,Inventory.deleted_at.is_(None),or_(Product.barcode==query,Product.sku.ilike(term),Product.name.ilike(term),Product.anime.has(Anime.name.ilike(term)),Product.character.has(Character.name.ilike(term))))
    rows=(await session.scalars(q.limit(30))).unique().all(); return APIResponse(data=[BarcodeResult(inventory_id=x.id,product_id=x.product_id,sku=x.variant.sku if x.variant else x.product.sku,barcode=x.variant.barcode if x.variant else x.product.barcode,name=x.product.name,price=x.variant.selling_price if x.variant else x.product.selling_price,available_quantity=x.available_quantity) for x in rows])
@router.get("/billing/barcode/{barcode}",response_model=APIResponse[BarcodeResult])
async def barcode(barcode:str,session:DatabaseSession,store_id:UUID,actor:User=Depends(require_permission("billing.read"))):
    scoped_store(actor,store_id)
    q=select(Inventory).options(selectinload(Inventory.product),selectinload(Inventory.variant)).join(Product).where(Inventory.store_id==store_id,Inventory.deleted_at.is_(None),or_(Product.barcode==barcode,Product.sku==barcode)); x=await session.scalar(q)
    if not x: raise NotFoundError("Product is not stocked at this store","BARCODE_STOCK_NOT_FOUND")
    if x.available_quantity <= 0: raise ConflictError("Out of stock at this shop.","BARCODE_OUT_OF_STOCK")
    return APIResponse(data=BarcodeResult(inventory_id=x.id,product_id=x.product_id,sku=x.variant.sku if x.variant else x.product.sku,barcode=x.variant.barcode if x.variant else x.product.barcode,name=x.product.name,price=x.variant.selling_price if x.variant else x.product.selling_price,available_quantity=x.available_quantity))
@router.get("/billing/products",response_model=APIResponse[list[BarcodeResult]])
async def shop_products(session:DatabaseSession,store_id:UUID|None=None,actor:User=Depends(require_permission("billing.read"))):
    if actor.assigned_store_id is not None and store_id is not None: scoped_store(actor,store_id)
    resolved=actor.assigned_store_id or store_id
    if not resolved: raise AuthorizationError("No shop is assigned to this account","BILLING_STORE_REQUIRED")
    scoped_store(actor,resolved)
    q=select(Inventory).options(selectinload(Inventory.product),selectinload(Inventory.variant)).join(Product).where(Inventory.store_id==resolved,Inventory.available_quantity>0,Inventory.deleted_at.is_(None),Product.deleted_at.is_(None)).order_by(Product.name)
    rows=(await session.scalars(q)).unique().all()
    return APIResponse(data=[BarcodeResult(inventory_id=x.id,product_id=x.product_id,sku=x.variant.sku if x.variant else x.product.sku,barcode=x.variant.barcode if x.variant else x.product.barcode,name=x.product.name,price=x.variant.selling_price if x.variant else x.product.selling_price,available_quantity=x.available_quantity) for x in rows])
@router.post("/billing",response_model=APIResponse[InvoiceResponse],status_code=201)
async def bill(data:BillingCreate,request:Request,background_tasks:BackgroundTasks,session:DatabaseSession,actor:User=Depends(require_permission("billing.create"))):
    invoice=await svc(BillingService,session,actor,request).create(data);background_tasks.add_task(dispatch_invoice_background,str(invoice.id),str(actor.id));return APIResponse(data=invoice,message="Invoice completed")

@router.get("/invoices",response_model=APIResponse[list[InvoiceResponse]])
async def invoices(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("billing.read"))): return APIResponse(data=await svc(BillingService,session,actor,request).invoices.list(store_id=actor.assigned_store_id))
@router.get("/invoices/{id}",response_model=APIResponse[InvoiceResponse])
async def invoice(id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("billing.read"))):
    x=await svc(BillingService,session,actor,request).invoices.get(id)
    if not x: raise NotFoundError("Invoice not found","INVOICE_NOT_FOUND")
    svc(BillingService,session,actor,request).authorize_store(x.store_id)
    return APIResponse(data=x)
@router.post("/invoices/{id}/cancel",response_model=APIResponse[InvoiceResponse])
async def cancel(id:UUID,data:InvoiceCancelRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("billing.cancel"))): return APIResponse(data=await svc(BillingService,session,actor,request).cancel(id,data.reason))
@router.get("/invoices/{id}/pdf")
async def pdf(id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("billing.pdf"))):
    x=await svc(BillingService,session,actor,request).invoices.get(id)
    if not x or not x.pdf_path or not Path(x.pdf_path).exists(): raise NotFoundError("Invoice PDF not found","INVOICE_PDF_NOT_FOUND")
    svc(BillingService,session,actor,request).authorize_store(x.store_id)
    return FileResponse(x.pdf_path,media_type="application/pdf",filename=f"{x.invoice_number}.pdf")

@router.get("/payments",response_model=APIResponse[list[PaymentResponse]])
async def payments(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("payments.read"))): return APIResponse(data=await svc(BillingService,session,actor,request).payments.list())
@router.get("/returns",response_model=APIResponse[list[ReturnResponse]])
async def returns(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("billing.read"))): return APIResponse(data=await svc(ReturnService,session,actor,request).returns.list())
@router.post("/returns",response_model=APIResponse[ReturnResponse],status_code=201)
async def create_return(data:ReturnCreate,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("billing.return"))): returned,_=await svc(ReturnService,session,actor,request).create_return(data); return APIResponse(data=returned)
@router.get("/refunds",response_model=APIResponse[list[RefundResponse]])
async def refunds(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("payments.read"))): return APIResponse(data=await svc(ReturnService,session,actor,request).refunds.list())
@router.get("/billing/analytics",response_model=APIResponse[BillingAnalytics])
async def analytics(session:DatabaseSession,actor:User=Depends(require_permission("billing.read"))): return APIResponse(data=await BillingAnalyticsService(session).summary())
@router.get("/billing/reports/sales",response_model=APIResponse[list[InvoiceResponse]])
async def sales_report(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("billing.read"))): return APIResponse(data=await svc(BillingService,session,actor,request).invoices.list())
@router.get("/billing/reports/payments",response_model=APIResponse[list[PaymentResponse]])
async def payment_report(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("payments.read"))): return APIResponse(data=await svc(BillingService,session,actor,request).payments.list())
@router.get("/billing/reports/returns",response_model=APIResponse[list[ReturnResponse]])
async def returns_report(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("billing.read"))): return APIResponse(data=await svc(ReturnService,session,actor,request).returns.list())
@router.get("/cash-register",response_model=APIResponse[list[dict]])
async def registers(session:DatabaseSession,actor:User=Depends(require_permission("billing.read"))):
    rows=list((await session.scalars(select(CashRegister).where(CashRegister.deleted_at.is_(None)).order_by(CashRegister.created_at.desc()))).all()); return APIResponse(data=[{"id":str(x.id),"store_id":str(x.store_id),"employee_id":str(x.employee_id),"opening_balance":str(x.opening_balance),"cash_sales":str(x.cash_sales),"cash_refunds":str(x.cash_refunds),"closing_balance":str(x.closing_balance) if x.closing_balance is not None else None,"status":x.status.value,"created_at":x.created_at.isoformat()} for x in rows])
@router.get("/invoices/{id}/history",response_model=APIResponse[list[dict]])
async def invoice_history(id:UUID,session:DatabaseSession,actor:User=Depends(require_permission("billing.read"))):
    rows=list((await session.scalars(select(AuditLog).where(AuditLog.entity_id==id,AuditLog.entity_type=="invoice").order_by(AuditLog.created_at.desc()))).all()); return APIResponse(data=[{"action":x.action,"actor_user_id":str(x.actor_user_id) if x.actor_user_id else None,"metadata":x.metadata_json,"created_at":x.created_at.isoformat()} for x in rows])
