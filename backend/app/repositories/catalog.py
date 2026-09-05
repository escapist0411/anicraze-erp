from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import Anime, Brand, CatalogMasterBase, CatalogStatus, Category, Character, Product, ProductImage, ProductStatus, ProductType, ProductVariant


class CatalogRepository:
    def __init__(self, session: AsyncSession): self.session = session

    @staticmethod
    def product_options():
        return (selectinload(Product.category), selectinload(Product.brand), selectinload(Product.anime), selectinload(Product.character), selectinload(Product.images), selectinload(Product.variants))

    async def product(self, product_id: UUID, *, include_deleted: bool = False, lock: bool = False) -> Product | None:
        stmt = select(Product).options(*self.product_options()).where(Product.id == product_id)
        if not include_deleted: stmt = stmt.where(Product.deleted_at.is_(None))
        return await self.session.scalar(stmt.with_for_update() if lock else stmt)

    async def product_by_sku(self, sku: str, include_deleted: bool = False) -> Product | None:
        stmt = select(Product).options(*self.product_options()).where(Product.sku == sku.upper())
        if not include_deleted: stmt = stmt.where(Product.deleted_at.is_(None))
        product = await self.session.scalar(stmt)
        if product: return product
        variant_product_id = await self.session.scalar(select(ProductVariant.product_id).where(ProductVariant.sku == sku.upper(), ProductVariant.deleted_at.is_(None)))
        return await self.product(variant_product_id, include_deleted=include_deleted) if variant_product_id else None

    async def product_by_barcode(self, barcode: str) -> Product | None:
        product = await self.session.scalar(select(Product).options(*self.product_options()).where(Product.barcode == barcode, Product.deleted_at.is_(None)))
        if product: return product
        variant_product_id = await self.session.scalar(select(ProductVariant.product_id).where(ProductVariant.barcode == barcode, ProductVariant.deleted_at.is_(None)))
        return await self.product(variant_product_id) if variant_product_id else None

    async def product_by_slug(self, slug: str) -> Product | None:
        return await self.session.scalar(select(Product).where(Product.slug == slug))

    async def list_products(self, *, page: int, page_size: int, search: str | None = None, category_id: UUID | None = None, brand_id: UUID | None = None, anime_id: UUID | None = None, character_id: UUID | None = None, product_type: ProductType | None = None, status: ProductStatus | None = None, gst_rate: Decimal | None = None, price_min: Decimal | None = None, price_max: Decimal | None = None, created_from: date | None = None, created_to: date | None = None, featured: bool | None = None, has_variants: bool | None = None, missing_barcode: bool | None = None, sort_by: str = "created_at", sort_order: str = "desc", limit_override: int | None = None) -> tuple[list[Product], int]:
        stmt = select(Product).options(*self.product_options()).where(Product.deleted_at.is_(None)); count = select(func.count(Product.id)).where(Product.deleted_at.is_(None)); filters = []
        if search:
            term = f"%{search.strip()}%"; filters.append(or_(Product.name.ilike(term), Product.sku.ilike(term), Product.barcode.ilike(term), Product.description.ilike(term), Product.hsn_code.ilike(term), Product.brand.has(Brand.name.ilike(term)), Product.anime.has(Anime.name.ilike(term)), Product.character.has(Character.name.ilike(term))))
        for column, value in ((Product.category_id, category_id), (Product.brand_id, brand_id), (Product.anime_id, anime_id), (Product.character_id, character_id), (Product.product_type, product_type), (Product.status, status), (Product.gst_rate, gst_rate), (Product.is_featured, featured), (Product.has_variants, has_variants)):
            if value is not None: filters.append(column == value)
        if price_min is not None: filters.append(Product.selling_price >= price_min)
        if price_max is not None: filters.append(Product.selling_price <= price_max)
        if missing_barcode is True: filters.append(or_(Product.barcode.is_(None), Product.barcode == ""))
        elif missing_barcode is False: filters.append(Product.barcode.is_not(None), Product.barcode != "")
        if created_from: filters.append(func.date(Product.created_at) >= created_from)
        if created_to: filters.append(func.date(Product.created_at) <= created_to)
        stmt = stmt.where(*filters); count = count.where(*filters)
        columns = {"name": Product.name, "sku": Product.sku, "selling_price": Product.selling_price, "purchase_price": Product.purchase_price, "created_at": Product.created_at, "updated_at": Product.updated_at, "status": Product.status}
        column = columns.get(sort_by, Product.created_at); stmt = stmt.order_by(column.desc() if sort_order == "desc" else column.asc())
        stmt = stmt.limit(limit_override or page_size)
        if limit_override is None: stmt = stmt.offset((page - 1) * page_size)
        return list((await self.session.scalars(stmt)).unique().all()), int(await self.session.scalar(count) or 0)

    async def master(self, model, entity_id: UUID, *, include_deleted: bool = False):
        stmt = select(model).where(model.id == entity_id)
        if not include_deleted: stmt = stmt.where(model.deleted_at.is_(None))
        return await self.session.scalar(stmt)

    async def master_by_code(self, model, code: str): return await self.session.scalar(select(model).where(model.code == code.upper()))
    async def master_by_slug(self, model, slug: str): return await self.session.scalar(select(model).where(model.slug == slug))
    async def list_masters(self, model, search: str | None = None, **filters):
        stmt = select(model).where(model.deleted_at.is_(None))
        if search: stmt = stmt.where(or_(model.name.ilike(f"%{search}%"), model.code.ilike(f"%{search}%")))
        for key, value in filters.items():
            if value is not None: stmt = stmt.where(getattr(model, key) == value)
        order = [model.sort_order, model.name] if model is Category else [model.name]
        return list((await self.session.scalars(stmt.order_by(*order))).all())

    async def product_count(self, field, entity_id: UUID, active_only: bool = False) -> int:
        stmt = select(func.count(Product.id)).where(field == entity_id, Product.deleted_at.is_(None))
        if active_only: stmt = stmt.where(Product.status == ProductStatus.ACTIVE)
        return int(await self.session.scalar(stmt) or 0)

    async def child_count(self, category_id: UUID) -> int: return int(await self.session.scalar(select(func.count(Category.id)).where(Category.parent_id == category_id, Category.deleted_at.is_(None))) or 0)
    async def descendants(self, category_id: UUID) -> list[UUID]:
        result = []; frontier = [category_id]
        while frontier:
            children = list((await self.session.scalars(select(Category.id).where(Category.parent_id.in_(frontier), Category.deleted_at.is_(None)))).all()); result.extend(children); frontier = children
        return result

    async def set_primary_image_false(self, product_id: UUID): await self.session.execute(update(ProductImage).where(ProductImage.product_id == product_id, ProductImage.deleted_at.is_(None)).values(is_primary=False))
    async def image(self, product_id: UUID, image_id: UUID): return await self.session.scalar(select(ProductImage).where(ProductImage.id == image_id, ProductImage.product_id == product_id, ProductImage.deleted_at.is_(None)))
