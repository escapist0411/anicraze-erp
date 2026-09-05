from math import ceil
from uuid import UUID
import csv
import io
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import select
from app.dependencies.auth import DatabaseSession
from app.exceptions.domain import AuthorizationError, NotFoundError
from app.models.auth import User
from app.models.inventory import AlertStatus, Store, TransactionType, Warehouse
from app.models.catalog import Product
from app.permissions.dependencies import require_permission
from app.schemas.common import APIResponse
from app.schemas.inventory import *
from app.services.inventory import AdjustmentService, AnalyticsService, InventoryService, ReservationService, TransferService

router=APIRouter(tags=["Inventory management"])
def service(cls,session,actor,request): return cls(session,actor,request.client.host if request.client else None,request.headers.get("user-agent"))

@router.get("/stores",response_model=APIResponse[list[LocationResponse]])
async def stores(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.read"))): return APIResponse(data=[LocationResponse.model_validate(x,from_attributes=True) for x in await service(InventoryService,session,actor,request).repo.locations(Store)])
@router.post("/stores",response_model=APIResponse[LocationResponse],status_code=201)
async def create_store(data:StoreCreateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.create"))): return APIResponse(data=LocationResponse.model_validate(await service(InventoryService,session,actor,request).create_location(Store,data),from_attributes=True))
@router.get("/warehouses",response_model=APIResponse[list[LocationResponse]])
async def warehouses(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.read"))): return APIResponse(data=[LocationResponse.model_validate(x,from_attributes=True) for x in await service(InventoryService,session,actor,request).repo.locations(Warehouse)])
@router.post("/warehouses",response_model=APIResponse[LocationResponse],status_code=201)
async def create_warehouse(data:WarehouseCreateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.create"))): return APIResponse(data=LocationResponse.model_validate(await service(InventoryService,session,actor,request).create_location(Warehouse,data),from_attributes=True))

@router.get("/inventory/transactions",response_model=APIResponse[list[InventoryTransactionResponse]])
async def transactions(request:Request,session:DatabaseSession,inventory_id:UUID|None=None,actor:User=Depends(require_permission("inventory.read"))): return APIResponse(data=await service(InventoryService,session,actor,request).repo.transactions(inventory_id))
@router.get("/inventory/ledger",response_model=APIResponse[list[LedgerResponse]])
async def ledger(request:Request,session:DatabaseSession,inventory_id:UUID|None=None,actor:User=Depends(require_permission("inventory.read"))): return APIResponse(data=await service(InventoryService,session,actor,request).repo.ledger(inventory_id))
@router.get("/inventory/analytics/summary",response_model=APIResponse[InventoryAnalyticsResponse])
async def analytics(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.analytics"))): return APIResponse(data=await service(AnalyticsService,session,actor,request).summary())
@router.get("/inventory/reports/stock",response_model=APIResponse[list[InventoryResponse]])
async def report(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.analytics"))):
    s=service(InventoryService,session,actor,request); rows,_=await s.repo.list(page_size=10000); return APIResponse(data=[s.response(x) for x in rows])
@router.get("/inventory/export")
async def export_inventory(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("reports.inventory.export"))):
    s=service(InventoryService,session,actor,request); rows,_=await s.repo.list(page_size=10000); output=io.StringIO(); writer=csv.writer(output); writer.writerow(["Product","SKU","Barcode","Location","Location type","Physical qty","Available qty","Reserved qty","Damaged qty","Reorder level","Average cost","Inventory value","Last movement"])
    for row in rows:
        item=s.response(row); location=item.store or item.warehouse; writer.writerow([item.product_name,item.sku,item.barcode or "",location.name if location else "","STORE" if item.store else "GODOWN",item.total_quantity,item.available_quantity,item.reserved_quantity,item.damaged_quantity,item.reorder_level,item.average_cost,item.inventory_value,item.last_movement_at.isoformat() if item.last_movement_at else ""])
    await s.audit("INVENTORY_EXPORTED","inventory_export",actor.id,{"count":len(rows)}); return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=anicraze-inventory.csv"})
@router.get("/inventory",response_model=APIResponse[InventoryListResponse])
async def inventory(request:Request,session:DatabaseSession,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,store_id:UUID|None=None,warehouse_id:UUID|None=None,category_id:UUID|None=None,brand_id:UUID|None=None,stock_level:str|None=Query(None,pattern="^(out|low|reorder)$"),product_id:UUID|None=None,actor:User=Depends(require_permission("inventory.read"))):
    roles={role.code for role in actor.roles}
    if roles&{"SALES","EMPLOYEE"}:
        if not actor.assigned_store_id:raise AuthorizationError("No shop is assigned to this employee","INVENTORY_STORE_SCOPE_REQUIRED")
        if store_id and store_id!=actor.assigned_store_id:raise AuthorizationError("Cross-shop inventory access is not allowed","INVENTORY_STORE_SCOPE_DENIED")
        store_id=actor.assigned_store_id;warehouse_id=None
    s=service(InventoryService,session,actor,request); rows,total=await s.repo.list(page,page_size,search,store_id,warehouse_id,category_id,brand_id,stock_level,product_id); return APIResponse(data=InventoryListResponse(items=[s.response(x) for x in rows],page=page,page_size=page_size,total=total,pages=ceil(total/page_size) if total else 0))
@router.post("/inventory",response_model=APIResponse[InventoryResponse],status_code=201)
async def create_inventory(data:InventoryCreateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.create"))): s=service(InventoryService,session,actor,request); return APIResponse(data=s.response(await s.create(data)))
@router.get("/inventory/{id}",response_model=APIResponse[InventoryResponse])
async def get_inventory(id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.read"))): s=service(InventoryService,session,actor,request); return APIResponse(data=s.response(await s.get(id)))
@router.patch("/inventory/{id}",response_model=APIResponse[InventoryResponse])
async def update_inventory(id:UUID,data:InventoryUpdateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.update"))): s=service(InventoryService,session,actor,request); return APIResponse(data=s.response(await s.update(id,data)))
@router.delete("/inventory/{id}",status_code=204)
async def delete_inventory(id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.delete"))): await service(InventoryService,session,actor,request).delete(id); return Response(status_code=204)
async def move(id,data,kind,direction,request,session,actor): s=service(InventoryService,session,actor,request); return APIResponse(data=s.response(await s.movement(id,data,kind,direction)))
@router.post("/inventory/{id}/stock-in",response_model=APIResponse[InventoryResponse])
async def stock_in(id:UUID,data:StockMovementRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.create"))): return await move(id,data,TransactionType.PURCHASE,1,request,session,actor)
@router.post("/inventory/{id}/stock-out",response_model=APIResponse[InventoryResponse])
async def stock_out(id:UUID,data:StockMovementRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.adjust"))): return await move(id,data,TransactionType.SALE,-1,request,session,actor)
@router.post("/inventory/{id}/damage",response_model=APIResponse[InventoryResponse])
async def damage(id:UUID,data:StockMovementRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.adjust"))): return await move(id,data,TransactionType.DAMAGE,-1,request,session,actor)
@router.post("/inventory/{id}/return",response_model=APIResponse[InventoryResponse])
async def returned(id:UUID,data:StockMovementRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.update"))): return await move(id,data,TransactionType.RETURN,1,request,session,actor)

@router.get("/stock-transfers",response_model=APIResponse[list[TransferResponse]])
async def transfers(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.read"))): return APIResponse(data=await service(TransferService,session,actor,request).repo.transfers(actor.assigned_store_id))
@router.post("/stock-transfers",response_model=APIResponse[TransferResponse],status_code=201)
async def create_transfer(data:TransferCreateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.transfer"))): return APIResponse(data=await service(TransferService,session,actor,request).create_transfer(data))
@router.get("/stock-transfers/{id}",response_model=APIResponse[TransferResponse])
async def get_transfer(id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.read"))):
    s=service(TransferService,session,actor,request); item=await s.repo.transfer(id)
    if not item: raise NotFoundError("Transfer not found","TRANSFER_NOT_FOUND")
    s.authorize_destination(item); return APIResponse(data=item)
@router.patch("/stock-transfers/{id}/status",response_model=APIResponse[TransferResponse])
async def transfer_status(id:UUID,data:TransferStatusRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.transfer"))): return APIResponse(data=await service(TransferService,session,actor,request).transition(id,data.status,data.reason))
@router.post("/stock-transfers/{id}/pick",response_model=APIResponse[TransferResponse])
async def pick_transfer(id:UUID,data:TransferPickRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.transfer"))): return APIResponse(data=await service(TransferService,session,actor,request).pick(id,data))
@router.post("/stock-transfers/{id}/receive",response_model=APIResponse[TransferResponse])
async def receive_transfer(id:UUID,data:TransferReceiveRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.read"))): return APIResponse(data=await service(TransferService,session,actor,request).receive(id,data))
@router.get("/stock-transfers/{id}/receipt")
async def transfer_receipt(id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.read"))):
    s=service(TransferService,session,actor,request);transfer=await s.repo.transfer(id)
    if not transfer:raise NotFoundError("Transfer not found","TRANSFER_NOT_FOUND")
    s.authorize_destination(transfer)
    source=await session.get(Store,transfer.source_store_id) if transfer.source_store_id else await session.get(Warehouse,transfer.source_warehouse_id)
    target=await session.get(Store,transfer.target_store_id) if transfer.target_store_id else await session.get(Warehouse,transfer.target_warehouse_id)
    products={p.id:p for p in (await session.scalars(select(Product).where(Product.id.in_([x.product_id for x in transfer.items])))).all()}
    out=io.BytesIO();canvas=Canvas(out,pagesize=A4);width,height=A4
    def header():
        canvas.setFont("Helvetica-Bold",16);canvas.drawString(36,height-42,"ANICRAZE STOCK TRANSFER RECEIPT");canvas.setFont("Helvetica",9);canvas.drawRightString(width-36,height-40,transfer.reference_number);canvas.line(36,height-52,width-36,height-52)
    header();y=height-75;canvas.setFont("Helvetica",10);canvas.drawString(36,y,f"From: {source.name if source else 'Unknown location'}");canvas.drawString(310,y,f"To: {target.name if target else 'Unknown location'}");y-=18;canvas.drawString(36,y,f"Created: {transfer.created_at.strftime('%d %b %Y, %I:%M %p')}");canvas.drawString(310,y,f"Status: {transfer.status.value}");y-=28
    canvas.setFont("Helvetica-Bold",9);canvas.drawString(36,y,"#");canvas.drawString(58,y,"Product");canvas.drawString(330,y,"SKU");canvas.drawRightString(470,y,"Quantity");canvas.drawRightString(545,y,"Picked");y-=10;canvas.line(36,y,width-36,y);y-=17;canvas.setFont("Helvetica",9)
    total=0
    for index,item in enumerate(transfer.items,1):
        if y<90:canvas.showPage();header();y=height-78
        product=products.get(item.product_id);canvas.drawString(36,y,str(index));canvas.drawString(58,y,(product.name if product else str(item.product_id))[:48]);canvas.drawString(330,y,(product.sku if product else "-")[:20]);canvas.drawRightString(470,y,str(item.quantity));canvas.drawRightString(545,y,str(item.picked_quantity));total+=item.quantity;y-=18
    y-=6;canvas.line(36,y,width-36,y);y-=20;canvas.setFont("Helvetica-Bold",10);canvas.drawRightString(545,y,f"Total units: {total}");y-=48;canvas.setFont("Helvetica",9);canvas.drawString(36,y,"Prepared by ____________________");canvas.drawString(310,y,"Received by ____________________");y-=35;canvas.drawString(36,y,"Dispatch signature ______________");canvas.drawString(310,y,"Shop signature __________________");canvas.setFont("Helvetica",7);canvas.drawString(36,24,"Generated by ANICRAZE ERP · This receipt covers every product in the transfer.");canvas.save();raw=out.getvalue()
    await s.audit("TRANSFER_RECEIPT_GENERATED","stock_transfer",transfer.id,{"items":len(transfer.items),"units":total});await session.flush()
    return StreamingResponse(io.BytesIO(raw),media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="ANICRAZE_Transfer_{transfer.reference_number}.pdf"'})
@router.get("/stock-adjustments",response_model=APIResponse[list[AdjustmentResponse]])
async def adjustments(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.read"))): return APIResponse(data=await service(AdjustmentService,session,actor,request).repo.adjustments())
@router.post("/stock-adjustments",response_model=APIResponse[AdjustmentResponse],status_code=201)
async def create_adjustment(data:AdjustmentCreateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.adjust"))): return APIResponse(data=await service(AdjustmentService,session,actor,request).create_adjustment(data))
@router.get("/stock-reservations",response_model=APIResponse[list[ReservationResponse]])
async def reservations(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.read"))): return APIResponse(data=await service(ReservationService,session,actor,request).repo.reservations())
@router.post("/stock-reservations",response_model=APIResponse[ReservationResponse],status_code=201)
async def reserve(data:ReservationCreateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.adjust"))): return APIResponse(data=await service(ReservationService,session,actor,request).create_reservation(data))
@router.delete("/stock-reservations/{id}",response_model=APIResponse[ReservationResponse])
async def release(id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("inventory.adjust"))): return APIResponse(data=await service(ReservationService,session,actor,request).release(id))
@router.get("/inventory-alerts",response_model=APIResponse[list[AlertResponse]])
async def alerts(request:Request,session:DatabaseSession,status:AlertStatus|None=None,actor:User=Depends(require_permission("inventory.read"))): return APIResponse(data=await service(InventoryService,session,actor,request).repo.alerts(status))
