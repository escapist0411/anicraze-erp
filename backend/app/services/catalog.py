import csv
import io
import re
from pathlib import Path
from uuid import UUID, uuid4

import barcode
from barcode.writer import SVGWriter
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.paths import UPLOAD_DIR
from app.exceptions.domain import ConflictError, NotFoundError
from app.models.auth import AuditLog, User
from app.models.catalog import Anime, Brand, CatalogStatus, Category, Character, Product, ProductImage, ProductStatus, ProductVariant
from app.repositories.catalog import CatalogRepository
from app.repositories.management import ManagementRepository
from app.schemas.catalog import *
from app.utils.time import utc_now

UPLOAD_ROOT = UPLOAD_DIR


def slug_part(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "item"


class LocalStorageService:
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    max_size = 5 * 1024 * 1024

    async def save_product_image(self, product_id: UUID, upload: UploadFile) -> tuple[str, str]:
        extension = self.allowed.get(upload.content_type or "")
        if not extension: raise ConflictError("Only JPEG, PNG and WEBP images are supported", "PRODUCT_IMAGE_TYPE_INVALID")
        content = await upload.read(self.max_size + 1)
        if len(content) > self.max_size: raise ConflictError("Image exceeds 5 MB", "PRODUCT_IMAGE_TOO_LARGE")
        signatures = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",), "image/webp": (b"RIFF",)}
        if not any(content.startswith(signature) for signature in signatures[upload.content_type or ""]): raise ConflictError("Image content does not match its declared format", "PRODUCT_IMAGE_CONTENT_INVALID")
        if upload.content_type == "image/webp" and (len(content) < 12 or content[8:12] != b"WEBP"): raise ConflictError("Invalid WEBP image", "PRODUCT_IMAGE_CONTENT_INVALID")
        folder = UPLOAD_ROOT / "products" / str(product_id); folder.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex}{extension}"; path = folder / filename; path.write_bytes(content)
        return str(path), f"/uploads/products/{product_id}/{filename}"

    def remove(self, path: str) -> None:
        target = Path(path).resolve()
        if UPLOAD_ROOT.resolve() in target.parents and target.exists(): target.unlink()


class SKUService:
    async def generate(self, session: AsyncSession, category_code: str) -> str:
        sequence = int(await session.scalar(select(func.next_value(__import__('sqlalchemy').Sequence("product_sku_sequence")))))
        prefix = re.sub(r"[^A-Z0-9]", "", category_code.upper())[:3].ljust(3, "X")
        return f"ANI-{prefix}-{sequence:06d}"


class BarcodeService:
    def generate_svg(self, product: Product, format: str = "CODE128") -> tuple[str, str]:
        value = product.sku
        folder = UPLOAD_ROOT / "barcodes"; folder.mkdir(parents=True, exist_ok=True)
        base = folder / f"{product.id}-{uuid4().hex[:8]}"
        if format == "EAN13":
            value = f"890{product.id.int % 1_000_000_000:09d}"
            code = barcode.get("ean13", value, writer=SVGWriter()); value = code.get_fullcode()
        else: code = barcode.get("code128", value, writer=SVGWriter())
        generated = code.save(str(base), options={"write_text": True})
        return value, generated


class CatalogServiceBase:
    def __init__(self, session: AsyncSession, actor: User, ip: str | None = None, user_agent: str | None = None):
        self.session, self.actor = session, actor
        self.repo = CatalogRepository(session); self.audit_repo = ManagementRepository(session)
        self.ip, self.user_agent = ip, user_agent

    async def audit(self, action: str, entity_type: str, entity_id: UUID, metadata: dict[str, object] | None = None):
        await self.audit_repo.audit(AuditLog(actor_user_id=self.actor.id, target_user_id=None, action=action, entity_type=entity_type, entity_id=entity_id, metadata_json=metadata, ip_address=self.ip, user_agent=self.user_agent, created_at=utc_now()))

    async def unique_slug(self, model, name: str, exclude: UUID | None = None) -> str:
        base = slug_part(name); candidate = base; suffix = 2
        while (found := await self.repo.master_by_slug(model, candidate)) and found.id != exclude:
            candidate = f"{base}-{suffix}"; suffix += 1
        return candidate


class MasterService(CatalogServiceBase):
    configs = {
        "category": (Category, Product.category_id, "CATEGORY"), "brand": (Brand, Product.brand_id, "BRAND"),
        "anime": (Anime, Product.anime_id, "ANIME"), "character": (Character, Product.character_id, "CHARACTER"),
    }

    async def create(self, kind: str, data):
        model, _, event = self.configs[kind]
        if await self.repo.master_by_code(model, data.code): raise ConflictError(f"{kind.title()} code already exists", f"{event}_CODE_EXISTS")
        values = data.model_dump(); values["slug"] = await self.unique_slug(model, values["name"]); values.update(created_by_id=self.actor.id, updated_by_id=self.actor.id)
        if kind == "category" and values.get("parent_id") and not await self.repo.master(Category, values["parent_id"]): raise NotFoundError("Parent category not found", "CATEGORY_PARENT_NOT_FOUND")
        if kind == "character" and not await self.repo.master(Anime, values["anime_id"]): raise NotFoundError("Anime franchise not found", "ANIME_NOT_FOUND")
        item = model(**values); self.session.add(item); await self.session.flush(); await self.audit(f"{event}_CREATED", kind, item.id, {"code": item.code}); return item

    async def update(self, kind: str, entity_id: UUID, data):
        model, _, event = self.configs[kind]; item = await self.repo.master(model, entity_id)
        if not item: raise NotFoundError(f"{kind.title()} not found", f"{event}_NOT_FOUND")
        values = data.model_dump(exclude_unset=True)
        if "code" in values and values["code"]:
            values["code"] = values["code"].strip().upper().replace(" ", "_"); duplicate = await self.repo.master_by_code(model, values["code"])
            if duplicate and duplicate.id != item.id: raise ConflictError(f"{kind.title()} code already exists", f"{event}_CODE_EXISTS")
        if "name" in values and values["name"]: values["slug"] = await self.unique_slug(model, values["name"], item.id)
        if kind == "category" and "parent_id" in values and values["parent_id"]:
            if values["parent_id"] == item.id or values["parent_id"] in await self.repo.descendants(item.id): raise ConflictError("Circular category hierarchy is not allowed", "CATEGORY_CIRCULAR_PARENT")
        if kind == "character" and values.get("anime_id") and not await self.repo.master(Anime, values["anime_id"]): raise NotFoundError("Anime franchise not found", "ANIME_NOT_FOUND")
        before = {k: str(getattr(item, k)) for k in values}; [setattr(item, k, v) for k, v in values.items()]; item.updated_by_id = self.actor.id
        await self.session.flush(); await self.audit(f"{event}_UPDATED", kind, item.id, {"before": before, "changed_fields": list(values)}); await self.session.refresh(item, attribute_names=["updated_at"]); return item

    async def delete(self, kind: str, entity_id: UUID):
        model, field, event = self.configs[kind]; item = await self.repo.master(model, entity_id)
        if not item: raise NotFoundError(f"{kind.title()} not found", f"{event}_NOT_FOUND")
        if await self.repo.product_count(field, item.id, active_only=True): raise ConflictError(f"{kind.title()} is used by active products", f"{event}_IN_USE")
        if kind == "category" and await self.repo.child_count(item.id): raise ConflictError("Category contains active child categories", "CATEGORY_HAS_CHILDREN")
        if kind == "anime" and await self.repo.list_masters(Character, anime_id=item.id): raise ConflictError("Anime franchise has active characters", "ANIME_HAS_CHARACTERS")
        item.deleted_at = utc_now(); item.status = CatalogStatus.INACTIVE; item.updated_by_id = self.actor.id; await self.audit(f"{event}_DELETED", kind, item.id)

    async def response(self, kind: str, item):
        _, field, _ = self.configs[kind]; common = dict(id=item.id, name=item.name, code=item.code, slug=item.slug, description=item.description, status=item.status, product_count=await self.repo.product_count(field, item.id), created_at=item.created_at, updated_at=item.updated_at)
        if kind == "category": return CategoryResponse(**common, parent_id=item.parent_id, image_url=item.image_url, sort_order=item.sort_order, child_count=await self.repo.child_count(item.id))
        if kind == "brand": return BrandResponse(**common, country=item.country, website=item.website, logo_url=item.logo_url)
        if kind == "anime": return AnimeResponse(**common, studio=item.studio, release_year=item.release_year, image_url=item.image_url)
        return CharacterResponse(**common, anime_id=item.anime_id, image_url=item.image_url)


class ProductService(CatalogServiceBase):
    def __init__(self, *args, **kwargs): super().__init__(*args, **kwargs); self.skus = SKUService(); self.barcodes = BarcodeService(); self.storage = LocalStorageService()

    async def validate_refs(self, category_id, brand_id, anime_id, character_id):
        category = await self.repo.master(Category, category_id) if category_id else None
        if not category or category.status != CatalogStatus.ACTIVE: raise NotFoundError("Category not found or inactive", "CATEGORY_NOT_FOUND")
        for model, value, code in ((Brand, brand_id, "BRAND"), (Anime, anime_id, "ANIME"), (Character, character_id, "CHARACTER")):
            if value and not await self.repo.master(model, value): raise NotFoundError(f"{code.title()} not found", f"{code}_NOT_FOUND")
        if character_id:
            character = await self.repo.master(Character, character_id)
            if anime_id and character.anime_id != anime_id: raise ConflictError("Character does not belong to the selected anime", "PRODUCT_CHARACTER_ANIME_MISMATCH")
            if not anime_id: anime_id = character.anime_id
        return category, anime_id

    def validate_pricing_values(self, values: dict, current: Product | None = None):
        get = lambda key, default=None: values.get(key, getattr(current, key, default) if current else default)
        purchase, landed, selling, mrp, minimum = get("purchase_price", 0), get("landed_cost"), get("selling_price", 0), get("mrp"), get("minimum_selling_price")
        if any(v is not None and v < 0 for v in (purchase, landed, selling, mrp, minimum)): raise ConflictError("Prices cannot be negative", "PRODUCT_PRICING_INVALID")
        if landed is not None and landed < purchase: raise ConflictError("Landed cost cannot be below purchase price", "PRODUCT_PRICING_INVALID")
        if mrp is not None and mrp < selling: raise ConflictError("MRP cannot be below selling price", "PRODUCT_PRICING_INVALID")
        if minimum is not None and minimum > selling: raise ConflictError("Minimum selling price cannot exceed selling price", "PRODUCT_PRICING_INVALID")

    async def create(self, data: ProductCreateRequest, *, audit_event: str = "PRODUCT_CREATED") -> Product:
        category, anime_id = await self.validate_refs(data.category_id, data.brand_id, data.anime_id, data.character_id)
        sku = data.sku.upper() if data.sku else await self.skus.generate(self.session, category.code)
        if data.sku and await self.repo.product_by_sku(sku, True): raise ConflictError("SKU already exists", "PRODUCT_SKU_EXISTS")
        while not data.sku and await self.repo.product_by_sku(sku, True): sku = await self.skus.generate(self.session, category.code)
        if data.barcode and await self.repo.product_by_barcode(data.barcode): raise ConflictError("Barcode already exists", "PRODUCT_BARCODE_EXISTS")
        values = data.model_dump(exclude={"generate_barcode", "variants"}); values.update(sku=sku, anime_id=anime_id, hsn_code=None, gst_rate=Decimal("0"), slug=await self.unique_slug(Product, data.name), created_by_id=self.actor.id, updated_by_id=self.actor.id)
        product = Product(**values); self.session.add(product); await self.session.flush(); await self.session.refresh(product, attribute_names=["category", "brand", "anime", "character", "images", "variants"])
        for variant_data in data.variants:
            variant_sku = variant_data.sku.upper() if variant_data.sku else await self.skus.generate(self.session, category.code)
            while not variant_data.sku and (await self.repo.product_by_sku(variant_sku, True) or await self.session.scalar(select(ProductVariant).where(ProductVariant.sku == variant_sku))): variant_sku = await self.skus.generate(self.session, category.code)
            if variant_data.sku and (await self.repo.product_by_sku(variant_sku, True) or await self.session.scalar(select(ProductVariant).where(ProductVariant.sku == variant_sku))): raise ConflictError("Variant SKU already exists", "PRODUCT_SKU_EXISTS")
            if variant_data.barcode and (await self.repo.product_by_barcode(variant_data.barcode) or await self.session.scalar(select(ProductVariant).where(ProductVariant.barcode == variant_data.barcode))): raise ConflictError("Variant barcode already exists", "PRODUCT_BARCODE_EXISTS")
            variant = ProductVariant(product_id=product.id, sku=variant_sku, created_by_id=self.actor.id, updated_by_id=self.actor.id, **variant_data.model_dump(exclude={"sku"})); self.session.add(variant)
        if data.variants: await self.session.flush(); await self.session.refresh(product, attribute_names=["variants"])
        if data.generate_barcode: await self.generate_barcode(product.id, False, "CODE128")
        await self.audit(audit_event, "product", product.id, {"sku": product.sku}); await self.session.refresh(product, attribute_names=["category", "brand", "anime", "character", "images", "variants", "updated_at"]); return product

    async def get(self, product_id: UUID, lock=False):
        product = await self.repo.product(product_id, lock=lock)
        if not product: raise NotFoundError("Product not found", "PRODUCT_NOT_FOUND")
        return product

    async def update(self, product_id: UUID, data: ProductUpdateRequest):
        product = await self.get(product_id, True); values = data.model_dump(exclude_unset=True); values.pop("hsn_code",None); values.pop("gst_rate",None); self.validate_pricing_values(values, product)
        category_id = values.get("category_id", product.category_id); brand_id = values.get("brand_id", product.brand_id); anime_id = values.get("anime_id", product.anime_id); character_id = values.get("character_id", product.character_id)
        _, anime_id = await self.validate_refs(category_id, brand_id, anime_id, character_id); values["anime_id"] = anime_id
        if values.get("sku"):
            values["sku"] = values["sku"].upper(); duplicate = await self.repo.product_by_sku(values["sku"], True)
            if duplicate and duplicate.id != product.id: raise ConflictError("SKU already exists", "PRODUCT_SKU_EXISTS")
        if values.get("barcode"):
            duplicate = await self.repo.product_by_barcode(values["barcode"])
            if duplicate and duplicate.id != product.id: raise ConflictError("Barcode already exists", "PRODUCT_BARCODE_EXISTS")
        if values.get("name"): values["slug"] = await self.unique_slug(Product, values["name"], product.id)
        before = {k: str(getattr(product, k)) for k in values}; price_changed = any(k in values for k in ("purchase_price", "landed_cost", "selling_price", "mrp", "minimum_selling_price")); sku_changed = "sku" in values and values["sku"] != product.sku
        [setattr(product, k, v) for k, v in values.items()]; product.updated_by_id = self.actor.id; await self.session.flush(); await self.session.refresh(product, attribute_names=["category", "brand", "anime", "character", "images", "variants", "updated_at"])
        await self.audit("PRODUCT_UPDATED", "product", product.id, {"before": before, "changed_fields": list(values)})
        if price_changed: await self.audit("PRODUCT_PRICE_CHANGED", "product", product.id, {"before": before})
        if sku_changed: await self.audit("PRODUCT_SKU_CHANGED", "product", product.id, {"before": before.get("sku"), "after": product.sku})
        return product

    async def set_status(self, product_id: UUID, status: ProductStatus, reason: str | None):
        product = await self.get(product_id, True); previous = product.status; product.status = status; product.updated_by_id = self.actor.id; await self.audit("PRODUCT_STATUS_CHANGED", "product", product.id, {"previous": previous.value, "new": status.value, "reason": reason}); await self.session.refresh(product, attribute_names=["category", "brand", "anime", "character", "images", "variants", "updated_at"]); return product

    async def delete(self, product_id: UUID):
        product = await self.get(product_id, True); product.deleted_at = utc_now(); product.status = ProductStatus.ARCHIVED; product.updated_by_id = self.actor.id; await self.audit("PRODUCT_DELETED", "product", product.id)

    async def generate_barcode(self, product_id: UUID, regenerate: bool, format: str = "CODE128"):
        product = await self.get(product_id, True)
        if product.barcode and not regenerate: raise ConflictError("Barcode exists; explicit regeneration required", "PRODUCT_BARCODE_EXISTS")
        previous = product.barcode; value, path = self.barcodes.generate_svg(product, format)
        duplicate = await self.repo.product_by_barcode(value)
        if duplicate and duplicate.id != product.id:
            Path(path).unlink(missing_ok=True)
            raise ConflictError("Generated barcode already exists", "PRODUCT_BARCODE_EXISTS")
        product.barcode, product.barcode_image_path = value, path
        await self.audit("PRODUCT_BARCODE_CHANGED" if previous else "PRODUCT_BARCODE_GENERATED", "product", product.id, {"previous": previous, "barcode": value}); return product

    async def add_image(self, product_id: UUID, upload: UploadFile, alt_text: str | None, sort_order: int, primary: bool):
        product = await self.get(product_id); path, url = await self.storage.save_product_image(product.id, upload)
        if primary or not any(not i.deleted_at for i in product.images): await self.repo.set_primary_image_false(product.id); primary = True
        image = ProductImage(product_id=product.id, file_path=path, file_url=url, alt_text=alt_text, sort_order=sort_order, is_primary=primary); self.session.add(image); await self.session.flush(); await self.audit("PRODUCT_IMAGE_ADDED", "product", product.id, {"image_id": str(image.id)}); return image

    async def remove_image(self, product_id: UUID, image_id: UUID):
        image = await self.repo.image(product_id, image_id)
        if not image: raise NotFoundError("Product image not found", "PRODUCT_IMAGE_NOT_FOUND")
        image.deleted_at = utc_now(); self.storage.remove(image.file_path); await self.audit("PRODUCT_IMAGE_REMOVED", "product", product_id, {"image_id": str(image_id)})

    def response(self, p: Product):
        active_images = sorted((i for i in p.images if i.deleted_at is None), key=lambda i: (not i.is_primary, i.sort_order)); primary = next((i.file_url for i in active_images if i.is_primary), active_images[0].file_url if active_images else None)
        ref = lambda x: NamedReference(id=x.id, name=x.name, code=x.code) if x else None
        return ProductResponse(id=p.id, sku=p.sku, barcode=p.barcode, name=p.name, slug=p.slug, short_description=p.short_description, description=p.description, category=ref(p.category), brand=ref(p.brand), anime=ref(p.anime), character=ref(p.character), product_type=p.product_type, material=p.material, edition=p.edition, manufacturer=p.manufacturer, country_of_origin=p.country_of_origin, import_reference=p.import_reference, purchase_price=p.purchase_price, landed_cost=p.landed_cost, selling_price=p.selling_price, mrp=p.mrp, discount_percentage=p.discount_percentage, minimum_selling_price=p.minimum_selling_price, reorder_level=p.reorder_level, unit_of_measure=p.unit_of_measure, weight=p.weight, length=p.length, width=p.width, height=p.height, is_serialized=p.is_serialized, has_variants=p.has_variants, status=p.status, is_featured=p.is_featured, primary_image=primary, images=active_images, variants=[v for v in p.variants if v.deleted_at is None], created_by_id=p.created_by_id, updated_by_id=p.updated_by_id, created_at=p.created_at, updated_at=p.updated_at)


class ProductImportService:
    max_size = 5 * 1024 * 1024
    def __init__(self, products: ProductService): self.products = products
    async def execute(self, upload: UploadFile, dry_run: bool, partial: bool):
        if not (upload.filename or "").lower().endswith(".csv"): raise ConflictError("Only CSV import is supported", "PRODUCT_IMPORT_TYPE_INVALID")
        raw = await upload.read(self.max_size + 1)
        if len(raw) > self.max_size: raise ConflictError("Import exceeds 5 MB", "PRODUCT_IMPORT_TOO_LARGE")
        try: rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        except UnicodeDecodeError as error: raise ConflictError("CSV must be UTF-8", "PRODUCT_IMPORT_ENCODING_INVALID") from error
        valid = []; errors = []; seen_skus: set[str] = set(); seen_barcodes: set[str] = set()
        for index, row in enumerate(rows, 2):
            try:
                payload = ProductCreateRequest.model_validate({k: v for k, v in row.items() if v not in (None, "")});
                if payload.sku and (payload.sku in seen_skus or await self.products.repo.product_by_sku(payload.sku, True)): raise ValueError("duplicate SKU")
                if payload.barcode and (payload.barcode in seen_barcodes or await self.products.repo.product_by_barcode(payload.barcode)): raise ValueError("duplicate barcode")
                if payload.sku: seen_skus.add(payload.sku)
                if payload.barcode: seen_barcodes.add(payload.barcode)
                valid.append(payload)
            except Exception as error: errors.append(ImportRowError(row=index, field=None, message=str(error)[:500]))
        created = 0
        if not dry_run and (partial or not errors):
            for payload in valid: await self.products.create(payload, audit_event="PRODUCT_IMPORTED"); created += 1
        return ProductImportResultResponse(total_rows=len(rows), valid_rows=len(valid), invalid_rows=len(errors), errors=errors, created_rows=created, dry_run=dry_run)
