from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import Anime, Brand, Category, Product
from app.models.inventory import *


class InventoryRepository:
    def __init__(self, session: AsyncSession): self.session = session

    @staticmethod
    def options(): return (selectinload(Inventory.product).selectinload(Product.category), selectinload(Inventory.product).selectinload(Product.brand), selectinload(Inventory.product).selectinload(Product.anime), selectinload(Inventory.variant), selectinload(Inventory.store), selectinload(Inventory.warehouse))

    async def get(self, inventory_id: UUID, lock: bool = False):
        stmt = select(Inventory).options(*self.options()).where(Inventory.id == inventory_id, Inventory.deleted_at.is_(None))
        return await self.session.scalar(stmt.with_for_update() if lock else stmt)

    async def find(self, product_id, variant_id, store_id, warehouse_id, lock=False):
        stmt = select(Inventory).options(*self.options()).where(Inventory.product_id == product_id, Inventory.variant_id.is_not_distinct_from(variant_id), Inventory.store_id.is_not_distinct_from(store_id), Inventory.warehouse_id.is_not_distinct_from(warehouse_id), Inventory.deleted_at.is_(None))
        return await self.session.scalar(stmt.with_for_update() if lock else stmt)

    async def list(self, page=1, page_size=20, search=None, store_id=None, warehouse_id=None, category_id=None, brand_id=None, stock_level=None, product_id=None):
        stmt = select(Inventory).options(*self.options()).join(Product).where(Inventory.deleted_at.is_(None)); filters=[]
        if search:
            term=f"%{search}%"; filters.append(or_(Product.name.ilike(term),Product.sku.ilike(term),Product.barcode.ilike(term),Product.category.has(Category.name.ilike(term)),Product.brand.has(Brand.name.ilike(term)),Product.anime.has(Anime.name.ilike(term))))
        for col,val in ((Inventory.store_id,store_id),(Inventory.warehouse_id,warehouse_id),(Product.category_id,category_id),(Product.brand_id,brand_id),(Inventory.product_id,product_id)):
            if val is not None: filters.append(col==val)
        if stock_level == "out": filters.append(Inventory.available_quantity==0)
        elif stock_level == "low": filters.extend((Inventory.available_quantity>0, Inventory.available_quantity<=Inventory.minimum_stock))
        elif stock_level == "reorder": filters.append(Inventory.available_quantity<=Inventory.reorder_level)
        stmt=stmt.where(*filters); count=select(func.count()).select_from(Inventory).join(Product).where(Inventory.deleted_at.is_(None),*filters)
        rows=(await self.session.scalars(stmt.order_by(Product.name,Inventory.created_at).offset((page-1)*page_size).limit(page_size))).unique().all()
        return list(rows), int(await self.session.scalar(count) or 0)

    async def location(self, model, location_id): return await self.session.scalar(select(model).where(model.id==location_id,model.deleted_at.is_(None)))
    async def locations(self, model): return list((await self.session.scalars(select(model).where(model.deleted_at.is_(None)).order_by(model.name))).all())
    async def transaction_by_key(self,key): return await self.session.scalar(select(InventoryTransaction).where(InventoryTransaction.idempotency_key==key))
    async def transactions(self, inventory_id=None, limit=200):
        stmt=select(InventoryTransaction)
        if inventory_id: stmt=stmt.where(InventoryTransaction.inventory_id==inventory_id)
        return list((await self.session.scalars(stmt.order_by(InventoryTransaction.created_at.desc()).limit(limit))).all())
    async def ledger(self, inventory_id=None, limit=500):
        stmt=select(InventoryLedger)
        if inventory_id: stmt=stmt.where(InventoryLedger.inventory_id==inventory_id)
        return list((await self.session.scalars(stmt.order_by(InventoryLedger.created_at.desc()).limit(limit))).all())
    async def transfers(self,target_store_id=None):
        stmt=select(StockTransfer).options(selectinload(StockTransfer.items).selectinload(StockTransferItem.product),selectinload(StockTransfer.items).selectinload(StockTransferItem.variant)).where(StockTransfer.deleted_at.is_(None))
        if target_store_id is not None: stmt=stmt.where(StockTransfer.target_store_id==target_store_id)
        return list((await self.session.scalars(stmt.order_by(StockTransfer.created_at.desc()))).unique().all())
    async def transfer(self,id,lock=False):
        stmt=select(StockTransfer).options(selectinload(StockTransfer.items).selectinload(StockTransferItem.product),selectinload(StockTransfer.items).selectinload(StockTransferItem.variant)).where(StockTransfer.id==id,StockTransfer.deleted_at.is_(None)); return await self.session.scalar(stmt.with_for_update() if lock else stmt)
    async def adjustments(self): return list((await self.session.scalars(select(StockAdjustment).options(selectinload(StockAdjustment.items)).where(StockAdjustment.deleted_at.is_(None)).order_by(StockAdjustment.created_at.desc()))).unique().all())
    async def adjustment(self,id): return await self.session.scalar(select(StockAdjustment).options(selectinload(StockAdjustment.items)).where(StockAdjustment.id==id,StockAdjustment.deleted_at.is_(None)))
    async def reservations(self): return list((await self.session.scalars(select(StockReservation).where(StockReservation.deleted_at.is_(None)).order_by(StockReservation.created_at.desc()))).all())
    async def reservation(self,id,lock=False):
        stmt=select(StockReservation).where(StockReservation.id==id,StockReservation.deleted_at.is_(None)); return await self.session.scalar(stmt.with_for_update() if lock else stmt)
    async def alerts(self,status=None):
        stmt=select(InventoryAlert)
        if status: stmt=stmt.where(InventoryAlert.status==status)
        return list((await self.session.scalars(stmt.order_by(InventoryAlert.created_at.desc()))).all())
