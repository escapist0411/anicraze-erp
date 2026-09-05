from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from app.models.procurement import *
class ProcurementRepository:
    def __init__(self,s): self.s=s
    async def next_number(self,key,prefix):
        seq=await self.s.scalar(select(ProcurementSequence).where(ProcurementSequence.key==key).with_for_update())
        if not seq: seq=ProcurementSequence(key=key,current_value=0); self.s.add(seq); await self.s.flush()
        seq.current_value+=1; await self.s.flush(); return f"{prefix}-{seq.current_value:06d}"
    async def supplier(self,id,lock=False):
        q=select(Supplier).where(Supplier.id==id,Supplier.deleted_at.is_(None)); return await self.s.scalar(q.with_for_update() if lock else q)
    async def suppliers(self,search=None,status=None,supplier_type=None):
        q=select(Supplier).where(Supplier.deleted_at.is_(None))
        if search:
            t=f"%{search}%"; q=q.where(or_(Supplier.supplier_code.ilike(t),Supplier.company_name.ilike(t),Supplier.display_name.ilike(t),Supplier.contact_person.ilike(t),Supplier.email.ilike(t),Supplier.phone.ilike(t),Supplier.gst_number.ilike(t),Supplier.import_export_code.ilike(t)))
        if status: q=q.where(Supplier.status==status)
        if supplier_type: q=q.where(Supplier.supplier_type==supplier_type)
        return list((await self.s.scalars(q.order_by(Supplier.company_name))).all())
    async def get(self,model,id,items=None,lock=False):
        q=select(model).where(model.id==id,model.deleted_at.is_(None))
        if items: q=q.options(selectinload(items))
        return await self.s.scalar(q.with_for_update() if lock else q)
    async def list(self,model,items=None,supplier_id=None):
        q=select(model).where(model.deleted_at.is_(None))
        if items: q=q.options(selectinload(items))
        if supplier_id is not None: q=q.where(model.supplier_id==supplier_id)
        return list((await self.s.scalars(q.order_by(model.created_at.desc()).limit(500))).unique().all())
class SupplierRepository(ProcurementRepository): pass
class PurchaseRequestRepository(ProcurementRepository): pass
class PurchaseOrderRepository(ProcurementRepository): pass
class GRNRepository(ProcurementRepository): pass
class SupplierInvoiceRepository(ProcurementRepository): pass
class SupplierPaymentRepository(ProcurementRepository): pass
class PurchaseReturnRepository(ProcurementRepository): pass
class LandedCostRepository(ProcurementRepository): pass
class ProcurementAnalyticsRepository(ProcurementRepository): pass
