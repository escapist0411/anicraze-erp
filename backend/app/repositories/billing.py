from datetime import datetime
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.billing import *

class InvoiceRepository:
    def __init__(self,s:AsyncSession): self.s=s
    def opts(self): return (selectinload(Invoice.items),selectinload(Invoice.payments).selectinload(Payment.method),selectinload(Invoice.customer),selectinload(Invoice.store),selectinload(Invoice.employee))
    async def get(self,id,lock=False):
        q=select(Invoice).options(*self.opts()).where(Invoice.id==id,Invoice.deleted_at.is_(None)); return await self.s.scalar(q.with_for_update() if lock else q)
    async def by_idempotency_key(self,key): return await self.s.scalar(select(Invoice).options(*self.opts()).where(Invoice.idempotency_key==key,Invoice.deleted_at.is_(None)))
    async def list(self,limit=200,store_id=None):
        q=select(Invoice).options(*self.opts()).where(Invoice.deleted_at.is_(None))
        if store_id: q=q.where(Invoice.store_id==store_id)
        return list((await self.s.scalars(q.order_by(Invoice.created_at.desc()).limit(limit))).unique().all())
    async def next_number(self,key="invoice",prefix="ANI-INV"):
        seq=await self.s.scalar(select(InvoiceSequence).where(InvoiceSequence.key==key).with_for_update())
        if not seq: seq=InvoiceSequence(key=key,current_value=0); self.s.add(seq); await self.s.flush()
        seq.current_value+=1; await self.s.flush(); return f"{prefix}-{seq.current_value:06d}"
class PaymentRepository:
    def __init__(self,s): self.s=s
    async def list(self): return list((await self.s.scalars(select(Payment).order_by(Payment.created_at.desc()).limit(500))).all())
    async def method(self,code):
        """Resolve an intrinsic POS method without external provider configuration."""
        name={PaymentMethodCode.CASH:"Cash",PaymentMethodCode.UPI:"UPI",PaymentMethodCode.CARD:"Card",PaymentMethodCode.OTHER:"Other"}.get(code,code.value.replace("_"," ").title())
        method_id=await self.s.scalar(
            insert(PaymentMethod).values(code=code,name=name,is_active=True)
            .on_conflict_do_update(index_elements=[PaymentMethod.code],set_={"name":name,"is_active":True,"deleted_at":None})
            .returning(PaymentMethod.id)
        )
        return await self.s.get(PaymentMethod,method_id)
class ReturnRepository:
    def __init__(self,s): self.s=s
    async def list(self): return list((await self.s.scalars(select(Return).options(selectinload(Return.items)).where(Return.deleted_at.is_(None)).order_by(Return.created_at.desc()))).unique().all())
    async def returned_quantity(self,item_id): return int(await self.s.scalar(select(func.coalesce(func.sum(ReturnItem.quantity),0)).join(Return).where(ReturnItem.invoice_item_id==item_id,Return.status==ReturnStatus.COMPLETED)) or 0)
class RefundRepository:
    def __init__(self,s): self.s=s
    async def list(self): return list((await self.s.scalars(select(Refund).where(Refund.deleted_at.is_(None)).order_by(Refund.created_at.desc()))).all())
