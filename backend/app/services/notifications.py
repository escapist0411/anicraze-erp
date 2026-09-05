from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.domain import NotFoundError
from app.models.auth import User
from app.models.billing import Invoice
from app.models.catalog import Product
from app.models.crm import CustomerCommunication
from app.models.inventory import AlertStatus, AlertType, Inventory, InventoryAlert, StockTransfer, TransferStatus
from app.models.inventory import InventoryTransaction, TransactionType
from app.models.notifications import Notification, NotificationCategory, NotificationSeverity
from app.models.procurement import POStatus, PurchaseOrder
from app.config.settings import get_settings


class NotificationService:
    def __init__(self,session:AsyncSession,actor:User):self.session=session;self.actor=actor

    async def upsert(self,key,category,severity,title,message,entity_type=None,entity_id=None,action_path=None):
        row=await self.session.scalar(select(Notification).where(Notification.user_id==self.actor.id,Notification.dedupe_key==key))
        if row:
            row.category=category;row.severity=severity;row.title=title;row.message=message;row.entity_type=entity_type;row.entity_id=entity_id;row.action_path=action_path
            if row.is_resolved:row.is_resolved=False;row.resolved_at=None;row.is_read=False;row.read_at=None
        else:
            row=Notification(user_id=self.actor.id,dedupe_key=key,category=category,severity=severity,title=title,message=message,entity_type=entity_type,entity_id=entity_id,action_path=action_path,created_by_id=self.actor.id,updated_by_id=self.actor.id);self.session.add(row)
        return row

    async def resolve_missing(self,prefixes:set[str],active:set[str]):
        rows=list((await self.session.scalars(select(Notification).where(Notification.user_id==self.actor.id,Notification.is_resolved.is_(False)))).all())
        now=datetime.now(timezone.utc)
        for row in rows:
            if any(row.dedupe_key.startswith(p) for p in prefixes) and row.dedupe_key not in active:
                row.is_resolved=True;row.resolved_at=now;row.resolution_reason="Source condition resolved"

    async def reconcile(self):
        active=set();prefixes={"inventory:","transfer:","transfer_pending:","communication:","procurement:"}
        rows=(await self.session.execute(select(InventoryAlert,Inventory,Product).join(Inventory,Inventory.id==InventoryAlert.inventory_id).join(Product,Product.id==Inventory.product_id).where(InventoryAlert.status==AlertStatus.OPEN,InventoryAlert.alert_type.in_([AlertType.LOW_STOCK,AlertType.OUT_OF_STOCK])))).all()
        for alert,inv,product in rows:
            key=f"inventory:{alert.alert_type.value}:{inv.id}";active.add(key);out=alert.alert_type==AlertType.OUT_OF_STOCK
            location="assigned location" if inv.store_id or inv.warehouse_id else "inventory"
            await self.upsert(key,NotificationCategory.INVENTORY,NotificationSeverity.CRITICAL if out else NotificationSeverity.WARNING,"Out of stock" if out else "Low stock",f"{product.name} {'is out of stock' if out else f'has only {inv.available_quantity} units remaining'} at {location}.","INVENTORY",inv.id,"inventory")
        discrepancies=list((await self.session.scalars(select(StockTransfer).where(StockTransfer.status==TransferStatus.DISCREPANCY,StockTransfer.deleted_at.is_(None)))).all())
        for transfer in discrepancies:
            shortage=sum(x.shortage_quantity for x in transfer.items);excess=sum(x.excess_quantity for x in transfer.items);key=f"transfer:discrepancy:{transfer.id}";active.add(key)
            await self.upsert(key,NotificationCategory.TRANSFER,NotificationSeverity.HIGH,"Transfer discrepancy",f"{transfer.reference_number} requires review: {shortage} short and {excess} excess units.","STOCK_TRANSFER",transfer.id,"inventory")
        pending=await self.session.scalar(select(func.count(StockTransfer.id)).where(StockTransfer.status==TransferStatus.PENDING_APPROVAL,StockTransfer.deleted_at.is_(None))) or 0
        if pending:
            key="transfer_pending:approval";active.add(key);await self.upsert(key,NotificationCategory.TRANSFER,NotificationSeverity.WARNING,"Transfers awaiting approval",f"{pending} stock transfer{'s' if pending!=1 else ''} require approval.",action_path="inventory")
        failed=(await self.session.execute(select(CustomerCommunication,Invoice).join(Invoice,Invoice.id==CustomerCommunication.related_invoice_id).where(CustomerCommunication.status=="FAILED",CustomerCommunication.deleted_at.is_(None)))).all()
        for communication,invoice in failed:
            key=f"communication:failed:{communication.id}";active.add(key);await self.upsert(key,NotificationCategory.COMMUNICATION,NotificationSeverity.HIGH,"Invoice delivery failed",f"Invoice {invoice.invoice_number} could not be delivered through WhatsApp.","INVOICE",invoice.id,"invoices")
        po_count=await self.session.scalar(select(func.count(PurchaseOrder.id)).where(PurchaseOrder.status==POStatus.SUBMITTED,PurchaseOrder.deleted_at.is_(None))) or 0
        if po_count:
            key="procurement:po_attention";active.add(key);await self.upsert(key,NotificationCategory.PROCUREMENT,NotificationSeverity.WARNING,"Purchase orders require attention",f"{po_count} purchase order{'s' if po_count!=1 else ''} await approval.",action_path="suppliers")
        threshold=get_settings().large_stock_adjustment_threshold
        adjustments=(await self.session.execute(select(InventoryTransaction,Product).join(Product,Product.id==InventoryTransaction.product_id).where(InventoryTransaction.transaction_type.in_([TransactionType.ADJUSTMENT,TransactionType.DAMAGE]),func.abs(InventoryTransaction.quantity)>=threshold))).all()
        for transaction,product in adjustments:
            await self.upsert(f"stock_adjustment:{transaction.id}",NotificationCategory.INVENTORY,NotificationSeverity.HIGH,"Sensitive stock adjustment",f"{abs(transaction.quantity)} units of {product.name} were manually adjusted. Reference: {transaction.reference_number}.","INVENTORY_TRANSACTION",transaction.id,"inventory")
        await self.resolve_missing(prefixes,active);await self.session.flush()

    async def list(self,category=None,unread=False,limit=100):
        await self.reconcile();q=select(Notification).where(Notification.user_id==self.actor.id,Notification.deleted_at.is_(None),Notification.is_resolved.is_(False))
        if category:q=q.where(Notification.category==category)
        if unread:q=q.where(Notification.is_read.is_(False))
        return list((await self.session.scalars(q.order_by(Notification.created_at.desc()).limit(limit))).all())
    async def mark_read(self,id:UUID):
        row=await self.session.scalar(select(Notification).where(Notification.id==id,Notification.user_id==self.actor.id))
        if not row:raise NotFoundError("Notification not found","NOTIFICATION_NOT_FOUND")
        row.is_read=True;row.read_at=datetime.now(timezone.utc);await self.session.flush();return row
    async def mark_all_read(self):
        rows=await self.list();now=datetime.now(timezone.utc)
        for row in rows:row.is_read=True;row.read_at=now
        await self.session.flush();return len(rows)

def notification_dict(x:Notification):
    return {"id":x.id,"category":x.category,"severity":x.severity,"title":x.title,"message":x.message,"entity_type":x.entity_type,"entity_id":x.entity_id,"action_path":x.action_path,"is_read":x.is_read,"is_resolved":x.is_resolved,"created_at":x.created_at,"read_at":x.read_at}
