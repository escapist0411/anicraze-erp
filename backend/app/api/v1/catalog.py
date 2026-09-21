import csv
import io
from datetime import date
from decimal import Decimal
from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.dependencies.auth import DatabaseSession
from app.exceptions.domain import NotFoundError
from app.models.auth import AuditLog, User
from app.models.catalog import Anime, Brand, Category, Character, ProductStatus, ProductType
from app.permissions.dependencies import require_permission
from app.schemas.catalog import *
from app.schemas.common import APIResponse
from app.services.catalog import MasterService, ProductImportService, ProductService

router = APIRouter(tags=["Product catalog"])


def product_service(session, actor, request): return ProductService(session, actor, request.client.host if request.client else None, request.headers.get("user-agent"))
def master_service(session, actor, request): return MasterService(session, actor, request.client.host if request.client else None, request.headers.get("user-agent"))


@router.get("/products/search/barcode/{barcode}", response_model=APIResponse[ProductResponse])
async def search_barcode(barcode: str, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("products.read"))):
    svc = product_service(session, actor, request); product = await svc.repo.product_by_barcode(barcode)
    if not product: raise NotFoundError("Product not found", "PRODUCT_NOT_FOUND")
    return APIResponse(data=svc.response(product))


@router.get("/products/search/sku/{sku}", response_model=APIResponse[ProductResponse])
async def search_sku(sku: str, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("products.read"))):
    svc = product_service(session, actor, request); product = await svc.repo.product_by_sku(sku)
    if not product: raise NotFoundError("Product not found", "PRODUCT_NOT_FOUND")
    return APIResponse(data=svc.response(product))


@router.post("/products/import", response_model=APIResponse[ProductImportResultResponse])
async def import_products(request: Request, session: DatabaseSession, file: UploadFile = File(...), dry_run: bool = Query(True), partial: bool = Query(False), actor: User = Depends(require_permission("products.import"))):
    svc = product_service(session, actor, request); result = await ProductImportService(svc).execute(file, dry_run, partial); return APIResponse(data=result)


@router.get("/products/export")
async def export_products(request: Request, session: DatabaseSession, search: str | None = None, category_id: UUID | None = None, status: ProductStatus | None = None, actor: User = Depends(require_permission("products.export"))):
    svc = product_service(session, actor, request); products, _ = await svc.repo.list_products(page=1, page_size=100, search=search, category_id=category_id, status=status, limit_override=10000)
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(["SKU", "Barcode", "Name", "Category", "Brand", "Anime", "Character", "Purchase price", "Landed cost", "Selling price", "MRP", "Reorder level", "Status"])
    for p in products: writer.writerow([p.sku, p.barcode or "", p.name, p.category.name, p.brand.name if p.brand else "", p.anime.name if p.anime else "", p.character.name if p.character else "", p.purchase_price, p.landed_cost or "", p.selling_price, p.mrp or "", p.reorder_level, p.status.value])
    await svc.audit("PRODUCT_EXPORTED", "product_export", actor.id, {"count": len(products)})
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=anicraze-products.csv"})


@router.get("/products", response_model=APIResponse[ProductListResponse])
async def list_products(request: Request, session: DatabaseSession, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), search: str | None = None, category_id: UUID | None = None, brand_id: UUID | None = None, anime_id: UUID | None = None, character_id: UUID | None = None, product_type: ProductType | None = None, status_filter: ProductStatus | None = Query(None, alias="status"), price_min: Decimal | None = None, price_max: Decimal | None = None, created_from: date | None = None, created_to: date | None = None, featured: bool | None = None, has_variants: bool | None = None, missing_barcode: bool | None = None, sort_by: str = Query("created_at", pattern="^(name|sku|selling_price|purchase_price|created_at|updated_at|status)$"), sort_order: str = Query("desc", pattern="^(asc|desc)$"), actor: User = Depends(require_permission("products.read"))):
    svc = product_service(session, actor, request); products, total = await svc.repo.list_products(page=page, page_size=page_size, search=search, category_id=category_id, brand_id=brand_id, anime_id=anime_id, character_id=character_id, product_type=product_type, status=status_filter, price_min=price_min, price_max=price_max, created_from=created_from, created_to=created_to, featured=featured, has_variants=has_variants, missing_barcode=missing_barcode, sort_by=sort_by, sort_order=sort_order)
    return APIResponse(data=ProductListResponse(items=[svc.response(p) for p in products], page=page, page_size=page_size, total=total, pages=ceil(total/page_size) if total else 0))


@router.post("/products", response_model=APIResponse[ProductResponse], status_code=201)
async def create_product(data: ProductCreateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("products.create"))):
    svc = product_service(session, actor, request); return APIResponse(data=svc.response(await svc.create(data)), message="Product created")


@router.get("/products/{product_id}", response_model=APIResponse[ProductResponse])
async def get_product(product_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("products.read"))):
    svc = product_service(session, actor, request); return APIResponse(data=svc.response(await svc.get(product_id)))


@router.patch("/products/{product_id}", response_model=APIResponse[ProductResponse])
async def update_product(product_id: UUID, data: ProductUpdateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("products.update"))):
    svc = product_service(session, actor, request); return APIResponse(data=svc.response(await svc.update(product_id, data)))


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("products.delete"))): await product_service(session, actor, request).delete(product_id); return Response(status_code=204)


@router.patch("/products/{product_id}/status", response_model=APIResponse[ProductResponse])
async def product_status(product_id: UUID, data: ProductStatusUpdateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("products.update_status"))):
    svc = product_service(session, actor, request); return APIResponse(data=svc.response(await svc.set_status(product_id, data.status, data.reason)))


@router.post("/products/{product_id}/images", response_model=APIResponse[ProductImageResponse], status_code=201)
async def add_image(product_id: UUID, request: Request, session: DatabaseSession, file: UploadFile = File(...), alt_text: str | None = Form(None), sort_order: int = Form(0), is_primary: bool = Form(False), actor: User = Depends(require_permission("products.manage_images"))): return APIResponse(data=await product_service(session, actor, request).add_image(product_id, file, alt_text, sort_order, is_primary))


@router.delete("/products/{product_id}/images/{image_id}", status_code=204)
async def remove_image(product_id: UUID, image_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("products.manage_images"))): await product_service(session, actor, request).remove_image(product_id, image_id); return Response(status_code=204)


@router.post("/products/{product_id}/barcode", response_model=APIResponse[BarcodeResponse])
async def generate_barcode(product_id: UUID, data: BarcodeGenerateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("products.manage_barcode"))):
    svc = product_service(session, actor, request); p = await svc.generate_barcode(product_id, data.regenerate, data.format); return APIResponse(data=BarcodeResponse(product_id=p.id, sku=p.sku, barcode=p.barcode, format=data.format, image_url=f"/uploads/barcodes/{__import__('pathlib').Path(p.barcode_image_path).name}" if p.barcode_image_path else None))


@router.get("/products/{product_id}/barcode", response_model=APIResponse[BarcodeResponse])
async def get_barcode(product_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("products.read"))):
    svc = product_service(session, actor, request)
    p = await svc.get(product_id)
    if not p.barcode: raise NotFoundError("Barcode has not been generated", "PRODUCT_BARCODE_NOT_FOUND")
    await svc.ensure_barcode_image(p)
    return APIResponse(data=BarcodeResponse(product_id=p.id, sku=p.sku, barcode=p.barcode, image_url=f"/uploads/barcodes/{__import__('pathlib').Path(p.barcode_image_path).name}" if p.barcode_image_path else None))


@router.get("/products/{product_id}/history", response_model=APIResponse[list[dict]])
async def product_history(product_id: UUID, session: DatabaseSession, actor: User = Depends(require_permission("products.read_history"))):
    logs = list((await session.scalars(select(AuditLog).where(AuditLog.entity_type == "product", AuditLog.entity_id == product_id).order_by(AuditLog.created_at.desc()))).all())
    return APIResponse(data=[{"id": str(x.id), "action": x.action, "actor_user_id": str(x.actor_user_id) if x.actor_user_id else None, "metadata": x.metadata_json, "created_at": x.created_at.isoformat()} for x in logs])


@router.get("/categories/tree", response_model=APIResponse[list[CategoryTreeResponse]])
async def category_tree(request: Request, session: DatabaseSession, actor: User = Depends(require_permission("categories.read"))):
    svc = master_service(session, actor, request); items = await svc.repo.list_masters(Category); responses = {x.id: CategoryTreeResponse(**(await svc.response("category", x)).model_dump(), children=[]) for x in items}; roots=[]
    for item in items:
        if item.parent_id and item.parent_id in responses: responses[item.parent_id].children.append(responses[item.id])
        else: roots.append(responses[item.id])
    return APIResponse(data=roots)


async def master_list(kind, model, request, session, actor, search=None, **filters):
    svc = master_service(session, actor, request); return APIResponse(data=[await svc.response(kind, x) for x in await svc.repo.list_masters(model, search, **filters)])
async def master_get(kind, model, entity_id, request, session, actor):
    svc = master_service(session, actor, request); item = await svc.repo.master(model, entity_id)
    if not item: raise NotFoundError(f"{kind.title()} not found", f"{kind.upper()}_NOT_FOUND")
    return APIResponse(data=await svc.response(kind, item))


@router.get("/categories", response_model=APIResponse[list[CategoryResponse]])
async def categories(request: Request, session: DatabaseSession, actor: User = Depends(require_permission("categories.read"))): return await master_list("category", Category, request, session, actor)
@router.post("/categories", response_model=APIResponse[CategoryResponse], status_code=201)
async def create_category(data: CategoryCreateRequest, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("categories.create"))):
    svc=master_service(session,actor,request); return APIResponse(data=await svc.response("category", await svc.create("category",data)))
@router.get("/categories/{entity_id}", response_model=APIResponse[CategoryResponse])
async def get_category(entity_id: UUID, request: Request, session: DatabaseSession, actor: User = Depends(require_permission("categories.read"))): return await master_get("category",Category,entity_id,request,session,actor)
@router.patch("/categories/{entity_id}", response_model=APIResponse[CategoryResponse])
async def update_category(entity_id: UUID,data:CategoryUpdateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("categories.update"))): svc=master_service(session,actor,request); return APIResponse(data=await svc.response("category",await svc.update("category",entity_id,data)))
@router.delete("/categories/{entity_id}",status_code=204)
async def delete_category(entity_id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("categories.delete"))): await master_service(session,actor,request).delete("category",entity_id); return Response(status_code=204)


@router.get("/brands",response_model=APIResponse[list[BrandResponse]])
async def brands(request:Request,session:DatabaseSession,actor:User=Depends(require_permission("brands.read"))): return await master_list("brand",Brand,request,session,actor)
@router.post("/brands",response_model=APIResponse[BrandResponse],status_code=201)
async def create_brand(data:BrandCreateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("brands.create"))): svc=master_service(session,actor,request); return APIResponse(data=await svc.response("brand",await svc.create("brand",data)))
@router.get("/brands/{entity_id}",response_model=APIResponse[BrandResponse])
async def get_brand(entity_id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("brands.read"))): return await master_get("brand",Brand,entity_id,request,session,actor)
@router.patch("/brands/{entity_id}",response_model=APIResponse[BrandResponse])
async def update_brand(entity_id:UUID,data:BrandUpdateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("brands.update"))): svc=master_service(session,actor,request); return APIResponse(data=await svc.response("brand",await svc.update("brand",entity_id,data)))
@router.delete("/brands/{entity_id}",status_code=204)
async def delete_brand(entity_id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("brands.delete"))): await master_service(session,actor,request).delete("brand",entity_id); return Response(status_code=204)


@router.get("/anime",response_model=APIResponse[list[AnimeResponse]])
async def anime_list(request:Request,session:DatabaseSession,search:str|None=None,actor:User=Depends(require_permission("anime.read"))): return await master_list("anime",Anime,request,session,actor,search)
@router.post("/anime",response_model=APIResponse[AnimeResponse],status_code=201)
async def create_anime(data:AnimeCreateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("anime.create"))): svc=master_service(session,actor,request); return APIResponse(data=await svc.response("anime",await svc.create("anime",data)))
@router.get("/anime/{entity_id}",response_model=APIResponse[AnimeResponse])
async def get_anime(entity_id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("anime.read"))): return await master_get("anime",Anime,entity_id,request,session,actor)
@router.patch("/anime/{entity_id}",response_model=APIResponse[AnimeResponse])
async def update_anime(entity_id:UUID,data:AnimeUpdateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("anime.update"))): svc=master_service(session,actor,request); return APIResponse(data=await svc.response("anime",await svc.update("anime",entity_id,data)))
@router.delete("/anime/{entity_id}",status_code=204)
async def delete_anime(entity_id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("anime.delete"))): await master_service(session,actor,request).delete("anime",entity_id); return Response(status_code=204)


@router.get("/characters",response_model=APIResponse[list[CharacterResponse]])
async def characters(request:Request,session:DatabaseSession,search:str|None=None,anime_id:UUID|None=None,actor:User=Depends(require_permission("characters.read"))): return await master_list("character",Character,request,session,actor,search,anime_id=anime_id)
@router.post("/characters",response_model=APIResponse[CharacterResponse],status_code=201)
async def create_character(data:CharacterCreateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("characters.create"))): svc=master_service(session,actor,request); return APIResponse(data=await svc.response("character",await svc.create("character",data)))
@router.get("/characters/{entity_id}",response_model=APIResponse[CharacterResponse])
async def get_character(entity_id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("characters.read"))): return await master_get("character",Character,entity_id,request,session,actor)
@router.patch("/characters/{entity_id}",response_model=APIResponse[CharacterResponse])
async def update_character(entity_id:UUID,data:CharacterUpdateRequest,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("characters.update"))): svc=master_service(session,actor,request); return APIResponse(data=await svc.response("character",await svc.update("character",entity_id,data)))
@router.delete("/characters/{entity_id}",status_code=204)
async def delete_character(entity_id:UUID,request:Request,session:DatabaseSession,actor:User=Depends(require_permission("characters.delete"))): await master_service(session,actor,request).delete("character",entity_id); return Response(status_code=204)
