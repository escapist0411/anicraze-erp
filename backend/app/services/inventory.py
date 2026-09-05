from datetime import timedelta
from decimal import Decimal
from math import ceil
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.domain import AuthorizationError, ConflictError, NotFoundError
from app.models.auth import AuditLog, User
from app.models.catalog import Product, ProductVariant
from app.models.inventory import *
from app.repositories.inventory import InventoryRepository
from app.repositories.management import ManagementRepository
from app.schemas.inventory import *
from app.utils.time import utc_now


class InventoryService:
    def __init__(self,session:AsyncSession,actor:User,ip=None,user_agent=None): self.session=session; self.actor=actor; self.repo=InventoryRepository(session); self.audit_repo=ManagementRepository(session); self.ip=ip; self.user_agent=user_agent
    async def audit(self,action,kind,id,metadata=None): await self.audit_repo.audit(AuditLog(actor_user_id=self.actor.id,action=action,entity_type=kind,entity_id=id,metadata_json=metadata,ip_address=self.ip,user_agent=self.user_agent,created_at=utc_now()))
    async def location(self,model,id):
        item=await self.repo.location(model,id)
        if not item: raise NotFoundError("Location not found","INVENTORY_LOCATION_NOT_FOUND")
        return item
    async def create_location(self,model,data):
        if await self.session.scalar(select(model).where(func.upper(model.code)==data.code.upper())): raise ConflictError("Location code exists","INVENTORY_LOCATION_CODE_EXISTS")
        item=model(**data.model_dump(),code=data.code.upper(),created_by_id=self.actor.id,updated_by_id=self.actor.id); self.session.add(item); await self.session.flush(); await self.audit("LOCATION_CREATED",model.__tablename__,item.id,{"code":item.code}); return item
    async def get(self,id,lock=False):
        item=await self.repo.get(id,lock)
        if not item: raise NotFoundError("Inventory not found","INVENTORY_NOT_FOUND")
        return item
    def response(self,x):
        p=x.product; available=x.available_quantity
        loc=lambda z: LocationResponse.model_validate(z,from_attributes=True) if z else None
        level="OUT_OF_STOCK" if available==0 else "LOW_STOCK" if available<=x.minimum_stock else "IN_STOCK"
        return InventoryResponse(id=x.id,product_id=x.product_id,variant_id=x.variant_id,sku=x.variant.sku if x.variant else p.sku,barcode=x.variant.barcode if x.variant else p.barcode,product_name=p.name,category=p.category.name,brand=p.brand.name if p.brand else None,anime=p.anime.name if p.anime else None,store=loc(x.store),warehouse=loc(x.warehouse),available_quantity=available,reserved_quantity=x.reserved_quantity,damaged_quantity=x.damaged_quantity,total_quantity=available+x.reserved_quantity+x.damaged_quantity,minimum_stock=x.minimum_stock,maximum_stock=x.maximum_stock,reorder_level=x.reorder_level,average_cost=x.average_cost,last_purchase_cost=x.last_purchase_cost,inventory_value=x.inventory_value,stock_level=level,reorder_recommended=available<=x.reorder_level,last_movement_at=x.last_movement_at,updated_at=x.updated_at)
    async def create(self,data):
        product=await self.session.scalar(select(Product).where(Product.id==data.product_id,Product.deleted_at.is_(None)))
        if not product: raise NotFoundError("Product not found","PRODUCT_NOT_FOUND")
        if data.variant_id and not await self.session.scalar(select(ProductVariant).where(ProductVariant.id==data.variant_id,ProductVariant.product_id==data.product_id,ProductVariant.deleted_at.is_(None))): raise ConflictError("Variant does not belong to product","INVENTORY_VARIANT_MISMATCH")
        if data.store_id: await self.location(Store,data.store_id)
        if data.warehouse_id: await self.location(Warehouse,data.warehouse_id)
        if await self.repo.find(data.product_id,data.variant_id,data.store_id,data.warehouse_id): raise ConflictError("Inventory already exists","INVENTORY_EXISTS")
        values=data.model_dump(exclude={"opening_quantity","reference_number"}); inv=Inventory(**values,available_quantity=0,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.session.add(inv); await self.session.flush()
        self.session.add(StoreInventory(inventory_id=inv.id,store_id=inv.store_id) if inv.store_id else WarehouseInventory(inventory_id=inv.id,warehouse_id=inv.warehouse_id))
        if data.opening_quantity: await self.move(inv,TransactionType.OPENING_STOCK,data.opening_quantity,data.reference_number or f"OPEN-{inv.id}",f"opening:{inv.id}",data.average_cost)
        await self.audit("INVENTORY_CREATED","inventory",inv.id); await self.session.flush(); return await self.get(inv.id)
    async def update(self,id,data):
        x=await self.get(id,True); values=data.model_dump(exclude_unset=True)
        maximum=values.get("maximum_stock",x.maximum_stock); minimum=values.get("minimum_stock",x.minimum_stock)
        if maximum is not None and maximum<minimum: raise ConflictError("maximum_stock cannot be below minimum_stock","INVENTORY_THRESHOLDS_INVALID")
        for k,v in values.items(): setattr(x,k,v)
        x.updated_by_id=self.actor.id; x.inventory_value=Decimal(x.available_quantity+x.reserved_quantity)*x.average_cost; await self.evaluate_alerts(x); await self.audit("INVENTORY_UPDATED","inventory",x.id,{"fields":list(values)}); await self.session.flush(); return await self.get(x.id)
    async def move(self,x,kind,change,reference,key,unit_cost=None,batch=None,remarks=None):
        if await self.repo.transaction_by_key(key): raise ConflictError("Movement already processed","INVENTORY_IDEMPOTENCY_CONFLICT")
        before=x.available_quantity
        if kind==TransactionType.DAMAGE:
            if before<abs(change): raise ConflictError("Insufficient available stock","INVENTORY_INSUFFICIENT_STOCK")
            x.available_quantity-=abs(change); x.damaged_quantity+=abs(change); signed=-abs(change)
        else:
            signed=change
            if before+signed<0: raise ConflictError("Insufficient available stock","INVENTORY_INSUFFICIENT_STOCK")
            if kind==TransactionType.PURCHASE and unit_cost is not None:
                existing=Decimal(before+x.reserved_quantity)*x.average_cost; x.average_cost=(existing+Decimal(change)*unit_cost)/Decimal(before+x.reserved_quantity+change) if before+x.reserved_quantity+change else unit_cost; x.last_purchase_cost=unit_cost
            x.available_quantity+=signed
        x.inventory_value=Decimal(x.available_quantity+x.reserved_quantity)*x.average_cost; x.last_movement_at=utc_now(); x.updated_by_id=self.actor.id
        tx=InventoryTransaction(idempotency_key=key,inventory_id=x.id,product_id=x.product_id,store_id=x.store_id,warehouse_id=x.warehouse_id,transaction_type=kind,quantity=abs(change),unit_cost=unit_cost,reference_number=reference,batch_number=batch,remarks=remarks,created_by_id=self.actor.id); self.session.add(tx); await self.session.flush()
        self.session.add(InventoryLedger(transaction_id=tx.id,inventory_id=x.id,product_id=x.product_id,store_id=x.store_id,warehouse_id=x.warehouse_id,transaction_type=kind,quantity_before=before,quantity_changed=signed,quantity_after=x.available_quantity,reference_number=reference,batch_number=batch,created_by_id=self.actor.id,created_at=utc_now()))
        await self.audit("INVENTORY_MOVEMENT","inventory",x.id,{"type":kind.value,"quantity":signed,"reference":reference}); await self.evaluate_alerts(x); await self.session.flush(); return tx
    async def movement(self,id,data,kind,direction=1):
        x=await self.get(id,True); await self.move(x,kind,direction*data.quantity,data.reference_number,data.idempotency_key,data.unit_cost,data.batch_number,data.remarks); return await self.get(id)
    async def evaluate_alerts(self,x):
        desired={AlertType.OUT_OF_STOCK:(x.available_quantity==0,0),AlertType.LOW_STOCK:(0<x.available_quantity<=x.minimum_stock,x.minimum_stock),AlertType.REORDER:(x.available_quantity<=x.reorder_level,x.reorder_level)}
        for kind,(needed,threshold) in desired.items():
            open_alert=await self.session.scalar(select(InventoryAlert).where(InventoryAlert.inventory_id==x.id,InventoryAlert.alert_type==kind,InventoryAlert.status==AlertStatus.OPEN))
            if needed and not open_alert: self.session.add(InventoryAlert(inventory_id=x.id,alert_type=kind,status=AlertStatus.OPEN,quantity_at_trigger=x.available_quantity,threshold=threshold))
            elif not needed and open_alert: open_alert.status=AlertStatus.RESOLVED; open_alert.resolved_at=utc_now(); open_alert.resolved_by_id=self.actor.id
    async def delete(self,id):
        x=await self.get(id,True)
        if x.available_quantity or x.reserved_quantity or x.damaged_quantity: raise ConflictError("Inventory with stock cannot be deleted","INVENTORY_NOT_EMPTY")
        x.deleted_at=utc_now(); x.updated_by_id=self.actor.id; await self.audit("INVENTORY_DELETED","inventory",x.id)


class TransferService(InventoryService):
    async def create_transfer(self,data):
        reference=data.reference_number
        if reference and await self.session.scalar(select(StockTransfer).where(StockTransfer.reference_number==reference)): raise ConflictError("Transfer reference exists","TRANSFER_EXISTS")
        for model,id in ((Store,data.source_store_id),(Warehouse,data.source_warehouse_id),(Store,data.target_store_id),(Warehouse,data.target_warehouse_id)):
            if id: await self.location(model,id)
        transfer_items=[]
        for i in data.items:
            source=await self.repo.find(i.product_id,i.variant_id,data.source_store_id,data.source_warehouse_id,True)
            if not source or source.available_quantity<i.quantity: raise ConflictError("Insufficient source stock","TRANSFER_INSUFFICIENT_STOCK")
            transfer_items.append(StockTransferItem(**i.model_dump()))
        values=data.model_dump(exclude={"items","reference_number"}); t=StockTransfer(reference_number=reference or f"PENDING-{uuid4().hex}",items=transfer_items,**values,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.session.add(t); await self.session.flush()
        if not reference: t.reference_number=f"ANI-TRF-{utc_now().year}-{str(t.id).replace('-','')[:8].upper()}"
        await self.session.flush(); await self.audit("TRANSFER_CREATED","stock_transfer",t.id); return t
    async def _reserve(self,t):
        for item in sorted(t.items,key=lambda x:str(x.product_id)):
            inv=await self.repo.find(item.product_id,item.variant_id,t.source_store_id,t.source_warehouse_id,True)
            if not inv or inv.available_quantity<item.quantity: raise ConflictError("Insufficient source stock at approval","TRANSFER_INSUFFICIENT_STOCK")
            inv.available_quantity-=item.quantity; inv.reserved_quantity+=item.quantity; inv.inventory_value=Decimal(inv.available_quantity+inv.reserved_quantity)*inv.average_cost
            self.session.add(StockReservation(reference_number=t.reference_number,inventory_id=inv.id,quantity=item.quantity,batch_number=item.batch_number,status=ReservationStatus.ACTIVE,created_by_id=self.actor.id,updated_by_id=self.actor.id)); await self.evaluate_alerts(inv)
    async def _release(self,t):
        reservations=list((await self.session.scalars(select(StockReservation).where(StockReservation.reference_number==t.reference_number,StockReservation.status==ReservationStatus.ACTIVE).with_for_update())).all())
        for reservation in reservations:
            inv=await self.get(reservation.inventory_id,True); inv.available_quantity+=reservation.quantity; inv.reserved_quantity-=reservation.quantity; reservation.status=ReservationStatus.RELEASED; reservation.released_at=utc_now(); reservation.updated_by_id=self.actor.id; await self.evaluate_alerts(inv)
    async def _dispatch(self,t):
        reservations={r.inventory_id:r for r in (await self.session.scalars(select(StockReservation).where(StockReservation.reference_number==t.reference_number,StockReservation.status==ReservationStatus.ACTIVE).with_for_update())).all()}
        for item in sorted(t.items,key=lambda x:str(x.product_id)):
            inv=await self.repo.find(item.product_id,item.variant_id,t.source_store_id,t.source_warehouse_id,True); reservation=reservations.get(inv.id if inv else None)
            if not inv or not reservation or reservation.quantity!=item.quantity or inv.reserved_quantity<item.quantity: raise ConflictError("Reserved stock is unavailable","TRANSFER_RESERVATION_INVALID")
            physical_before=inv.available_quantity+inv.reserved_quantity; inv.reserved_quantity-=item.quantity; inv.inventory_value=Decimal(inv.available_quantity+inv.reserved_quantity)*inv.average_cost; inv.last_movement_at=utc_now(); reservation.status=ReservationStatus.CONSUMED; reservation.updated_by_id=self.actor.id
            tx=InventoryTransaction(idempotency_key=f"transfer:{t.id}:out:{item.id}",inventory_id=inv.id,product_id=inv.product_id,store_id=inv.store_id,warehouse_id=inv.warehouse_id,transaction_type=TransactionType.TRANSFER_OUT,quantity=item.quantity,unit_cost=inv.average_cost,reference_number=t.reference_number,batch_number=item.batch_number,remarks="Dispatched to shop",created_by_id=self.actor.id); self.session.add(tx); await self.session.flush(); self.session.add(InventoryLedger(transaction_id=tx.id,inventory_id=inv.id,product_id=inv.product_id,store_id=inv.store_id,warehouse_id=inv.warehouse_id,transaction_type=TransactionType.TRANSFER_OUT,quantity_before=physical_before,quantity_changed=-item.quantity,quantity_after=physical_before-item.quantity,reference_number=t.reference_number,batch_number=item.batch_number,created_by_id=self.actor.id,created_at=utc_now()))
    async def transition(self,id,status,reason=None):
        t=await self.repo.transfer(id,True)
        if not t: raise NotFoundError("Transfer not found","TRANSFER_NOT_FOUND")
        allowed={TransferStatus.CREATED:{TransferStatus.PENDING_APPROVAL,TransferStatus.CANCELLED},TransferStatus.PENDING_APPROVAL:{TransferStatus.APPROVED,TransferStatus.REJECTED,TransferStatus.CANCELLED},TransferStatus.APPROVED:{TransferStatus.PICKING,TransferStatus.CANCELLED},TransferStatus.PICKED:{TransferStatus.PACKED,TransferStatus.CANCELLED},TransferStatus.PACKED:{TransferStatus.DISPATCHED,TransferStatus.CANCELLED},TransferStatus.DISPATCHED:{TransferStatus.RECEIVING}}
        if status not in allowed.get(t.status,set()): raise ConflictError("Invalid transfer status transition","TRANSFER_STATUS_INVALID")
        now=utc_now()
        if status==TransferStatus.PENDING_APPROVAL: await self.audit("TRANSFER_SUBMITTED","stock_transfer",t.id)
        if status==TransferStatus.APPROVED: await self._reserve(t); t.approved_by_id=self.actor.id; t.approved_at=now; await self.audit("TRANSFER_APPROVED","stock_transfer",t.id)
        if status==TransferStatus.PICKING: t.picking_started_at=now; await self.audit("TRANSFER_PICKING_STARTED","stock_transfer",t.id)
        if status==TransferStatus.PACKED: t.packed_by_id=self.actor.id; t.packed_at=now; await self.audit("TRANSFER_PACKED","stock_transfer",t.id)
        if status==TransferStatus.DISPATCHED:
            if any(i.picked_quantity!=i.quantity for i in t.items): raise ConflictError("All items must be picked before dispatch","TRANSFER_PICKING_INCOMPLETE")
            await self._dispatch(t); t.dispatched_by_id=self.actor.id; t.dispatched_at=now; await self.audit("TRANSFER_DISPATCHED","stock_transfer",t.id)
        if status==TransferStatus.RECEIVING: self.authorize_destination(t); t.receiving_started_at=now; await self.audit("TRANSFER_RECEIVING_STARTED","stock_transfer",t.id)
        if status in {TransferStatus.CANCELLED,TransferStatus.REJECTED}:
            if t.status in {TransferStatus.APPROVED,TransferStatus.PICKING,TransferStatus.PICKED,TransferStatus.PACKED}: await self._release(t)
            t.cancellation_reason=reason or "Not provided"; await self.audit(f"TRANSFER_{status.value}","stock_transfer",t.id,{"reason":reason})
        t.status=status; t.updated_by_id=self.actor.id; await self.session.flush(); return await self.repo.transfer(t.id)
    def authorize_destination(self,t):
        if self.actor.assigned_store_id is not None and self.actor.assigned_store_id!=t.target_store_id: raise AuthorizationError("Transfer is assigned to another store","TRANSFER_STORE_SCOPE_DENIED")
    async def pick(self,id,data):
        t=await self.repo.transfer(id,True)
        if not t or t.status not in {TransferStatus.PICKING,TransferStatus.APPROVED}: raise ConflictError("Transfer is not available for picking","TRANSFER_STATUS_INVALID")
        if t.status==TransferStatus.APPROVED: t.status=TransferStatus.PICKING; t.picking_started_at=utc_now()
        provided={x.item_id:x.picked_quantity for x in data.items}
        if set(provided)!=set(x.id for x in t.items): raise ConflictError("Picking counts must cover every item","TRANSFER_PICKING_ITEMS_INVALID")
        for item in t.items:
            if provided[item.id]>item.quantity: raise ConflictError("Picked quantity exceeds transfer quantity","TRANSFER_PICKING_OVERAGE")
            item.picked_quantity=provided[item.id]
        if all(x.picked_quantity==x.quantity for x in t.items): t.status=TransferStatus.PICKED; t.picked_by_id=self.actor.id; t.picked_at=utc_now(); await self.audit("TRANSFER_PICKING_COMPLETED","stock_transfer",t.id)
        await self.session.flush(); return await self.repo.transfer(t.id)
    async def receive(self,id,data):
        t=await self.repo.transfer(id,True)
        if not t or t.status not in {TransferStatus.DISPATCHED,TransferStatus.RECEIVING}: raise ConflictError("Transfer cannot be received","TRANSFER_STATUS_INVALID")
        self.authorize_destination(t); provided={x.item_id:x for x in data.items}
        if set(provided)!=set(x.id for x in t.items): raise ConflictError("Receipt counts must cover every item","TRANSFER_RECEIPT_ITEMS_INVALID")
        discrepancy=False
        for item in sorted(t.items,key=lambda x:str(x.id)):
            req=provided[item.id]; good=req.received_quantity
            if good+req.damaged_quantity>item.quantity: raise ConflictError("Received good and damaged quantity exceeds dispatched quantity","TRANSFER_RECEIPT_OVERAGE")
            shortage=item.quantity-good-req.damaged_quantity; item.received_quantity=good; item.damaged_quantity=req.damaged_quantity; item.shortage_quantity=shortage; item.excess_quantity=req.excess_quantity; item.discrepancy_note=req.note
            if shortage or req.excess_quantity or req.damaged_quantity: discrepancy=True
            src=await self.repo.find(item.product_id,item.variant_id,t.source_store_id,t.source_warehouse_id); dst=await self.repo.find(item.product_id,item.variant_id,t.target_store_id,t.target_warehouse_id,True)
            if not dst: dst=await self.create(InventoryCreateRequest(product_id=item.product_id,variant_id=item.variant_id,store_id=t.target_store_id,warehouse_id=t.target_warehouse_id,minimum_stock=src.minimum_stock,reorder_level=src.reorder_level,average_cost=src.average_cost))
            if good: await self.move(dst,TransactionType.TRANSFER_IN,good,t.reference_number,f"transfer:{t.id}:in:{item.id}",src.average_cost,item.batch_number,"Shop receipt")
            if req.damaged_quantity:
                await self.move(dst,TransactionType.TRANSFER_IN,req.damaged_quantity,t.reference_number,f"transfer:{t.id}:damaged-in:{item.id}",src.average_cost,item.batch_number,"Damaged on arrival")
                await self.move(dst,TransactionType.DAMAGE,-req.damaged_quantity,t.reference_number,f"transfer:{t.id}:damaged:{item.id}",src.average_cost,item.batch_number,"Damaged on arrival")
        t.received_by_id=self.actor.id; t.received_at=utc_now(); t.discrepancy_notes=data.notes; t.status=TransferStatus.DISCREPANCY if discrepancy else TransferStatus.COMPLETED
        if not discrepancy: t.completed_at=utc_now()
        await self.audit("TRANSFER_DISCREPANCY_RECORDED" if discrepancy else "TRANSFER_RECEIVED","stock_transfer",t.id,{"status":t.status.value}); await self.session.flush(); return await self.repo.transfer(t.id)


class AdjustmentService(InventoryService):
    async def create_adjustment(self,data):
        if await self.session.scalar(select(StockAdjustment).where(StockAdjustment.reference_number==data.reference_number)): raise ConflictError("Adjustment reference exists","ADJUSTMENT_EXISTS")
        a=StockAdjustment(reference_number=data.reference_number,reason=data.reason,created_by_id=self.actor.id,updated_by_id=self.actor.id); self.session.add(a); await self.session.flush()
        for i in data.items:
            inv=await self.get(i.inventory_id,True); item=StockAdjustmentItem(**i.model_dump()); a.items.append(item); await self.move(inv,TransactionType.ADJUSTMENT,i.quantity_change,data.reference_number,f"adjustment:{a.id}:{i.inventory_id}",batch=i.batch_number,remarks=i.remarks)
        await self.session.flush(); await self.audit("ADJUSTMENT_CREATED","stock_adjustment",a.id); return a


class ReservationService(InventoryService):
    async def create_reservation(self,data):
        inv=await self.get(data.inventory_id,True)
        if inv.available_quantity<data.quantity: raise ConflictError("Insufficient available stock","RESERVATION_INSUFFICIENT_STOCK")
        if await self.session.scalar(select(StockReservation).where(StockReservation.reference_number==data.reference_number,StockReservation.inventory_id==data.inventory_id)): raise ConflictError("Reservation exists","RESERVATION_EXISTS")
        inv.available_quantity-=data.quantity; inv.reserved_quantity+=data.quantity; inv.inventory_value=Decimal(inv.available_quantity+inv.reserved_quantity)*inv.average_cost
        r=StockReservation(**data.model_dump(),created_by_id=self.actor.id,updated_by_id=self.actor.id); self.session.add(r); await self.session.flush(); await self.evaluate_alerts(inv); await self.audit("STOCK_RESERVED","stock_reservation",r.id,{"quantity":r.quantity}); return r
    async def release(self,id):
        r=await self.repo.reservation(id,True)
        if not r: raise NotFoundError("Reservation not found","RESERVATION_NOT_FOUND")
        if r.status!=ReservationStatus.ACTIVE: raise ConflictError("Reservation is not active","RESERVATION_INACTIVE")
        inv=await self.get(r.inventory_id,True); inv.available_quantity+=r.quantity; inv.reserved_quantity-=r.quantity; r.status=ReservationStatus.RELEASED; r.released_at=utc_now(); r.updated_by_id=self.actor.id; await self.evaluate_alerts(inv); await self.audit("STOCK_RESERVATION_RELEASED","stock_reservation",r.id); return r


class AnalyticsService(InventoryService):
    async def summary(self):
        inventories,_=await self.repo.list(page=1,page_size=10000); now=utc_now(); dead=sum(1 for x in inventories if not x.last_movement_at or x.last_movement_at<now-timedelta(days=90))
        def compare(attr):
            values={}
            for x in inventories:
                loc=getattr(x,attr)
                if loc: values.setdefault(loc.name,{"location":loc.name,"quantity":0,"value":Decimal(0)}); values[loc.name]["quantity"]+=x.available_quantity; values[loc.name]["value"]+=x.inventory_value
            return list(values.values())
        ranked=sorted(inventories,key=lambda x:x.available_quantity,reverse=True)
        compact=lambda x:{"inventory_id":str(x.id),"sku":x.product.sku,"name":x.product.name,"quantity":x.available_quantity}
        return InventoryAnalyticsResponse(total_inventory_value=sum((x.inventory_value for x in inventories),Decimal(0)),total_available_quantity=sum(x.available_quantity for x in inventories),total_reserved_quantity=sum(x.reserved_quantity for x in inventories),low_stock_count=sum(0<x.available_quantity<=x.minimum_stock for x in inventories),out_of_stock_count=sum(x.available_quantity==0 for x in inventories),reorder_count=sum(x.available_quantity<=x.reorder_level for x in inventories),dead_stock_count=dead,fast_moving=[compact(x) for x in ranked[:10]],slow_moving=[compact(x) for x in ranked[-10:]],top_products=[compact(x) for x in ranked[:10]],store_comparison=compare("store"),warehouse_comparison=compare("warehouse"))
