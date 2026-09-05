import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.database.session import AsyncSessionFactory
from app.models.auth import User
from app.models.catalog import Product
from app.models.inventory import Inventory, Store, Warehouse
from app.schemas.inventory import InventoryCreateRequest
from app.services.inventory import InventoryService

STORES=[("PHOENIX","Phoenix Marketcity Pune"),("SEAWOODS","Seawoods Grand Central"),("VIVIANA","Viviana Mall Thane"),("PALLADIUM","Palladium Mumbai"),("NEXUS","Nexus Ahmedabad One")]
WAREHOUSES=[("PUNE_CENTRAL","Pune Central Warehouse"),("NASHIK_HUB","Nashik Distribution Hub")]

async def seed():
    async with AsyncSessionFactory() as session:
        owner=await session.scalar(select(User).where(User.email=="owner@anicraze.com"))
        locations=[]
        for model,rows in ((Store,STORES),(Warehouse,WAREHOUSES)):
            for code,name in rows:
                item=await session.scalar(select(model).where(model.code==code))
                if not item:
                    item=model(code=code,name=name,address="Maharashtra, India",created_by_id=owner.id,updated_by_id=owner.id); session.add(item); await session.flush()
                locations.append(item)
        products=list((await session.scalars(select(Product).where(Product.deleted_at.is_(None)).order_by(Product.sku).limit(15))).all())
        service=InventoryService(session,owner)
        for index,product in enumerate(products):
            location=locations[index%len(locations)]; store_id=location.id if isinstance(location,Store) else None; warehouse_id=location.id if isinstance(location,Warehouse) else None
            if await service.repo.find(product.id,None,store_id,warehouse_id): continue
            await service.create(InventoryCreateRequest(product_id=product.id,store_id=store_id,warehouse_id=warehouse_id,opening_quantity=8+(index*7)%43,minimum_stock=5,maximum_stock=100,reorder_level=8,average_cost=product.purchase_price,reference_number=f"DEMO-OPEN-{product.sku}"))
        await session.commit()

if __name__=="__main__": asyncio.run(seed())
