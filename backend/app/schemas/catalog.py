from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.catalog import CatalogStatus, ProductStatus, ProductType

MONEY = Decimal
APPROVED_GST_RATES = {Decimal("0"), Decimal("5"), Decimal("12"), Decimal("18"), Decimal("28")}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductPricingMixin(StrictModel):
    purchase_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    landed_cost: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    selling_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    mrp: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    minimum_selling_price: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    discount_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    gst_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)

    @model_validator(mode="after")
    def validate_pricing(self):
        if self.landed_cost is not None and self.landed_cost < self.purchase_price: raise ValueError("landed_cost cannot be below purchase_price")
        if self.mrp is not None and self.mrp < self.selling_price: raise ValueError("mrp cannot be below selling_price")
        if self.minimum_selling_price is not None and self.minimum_selling_price > self.selling_price: raise ValueError("minimum_selling_price cannot exceed selling_price")
        if self.gst_rate not in APPROVED_GST_RATES: raise ValueError("gst_rate is not an approved configured rate")
        return self


class ProductVariantCreateRequest(StrictModel):
    name: str = Field(min_length=1, max_length=180)
    sku: str | None = Field(None, pattern=r"^[A-Z0-9][A-Z0-9_-]{2,63}$")
    barcode: str | None = Field(None, pattern=r"^[A-Za-z0-9_-]{4,64}$")
    purchase_price: Decimal = Field(ge=0); landed_cost: Decimal | None = Field(None, ge=0); selling_price: Decimal = Field(ge=0); mrp: Decimal | None = Field(None, ge=0)
    status: ProductStatus = ProductStatus.ACTIVE

    @model_validator(mode="after")
    def validate_prices(self):
        if self.landed_cost is not None and self.landed_cost < self.purchase_price: raise ValueError("landed_cost cannot be below purchase_price")
        if self.mrp is not None and self.mrp < self.selling_price: raise ValueError("mrp cannot be below selling_price")
        return self


class ProductCreateRequest(ProductPricingMixin):
    name: str = Field(min_length=2, max_length=220)
    sku: str | None = Field(None, pattern=r"^[A-Z0-9][A-Z0-9_-]{2,63}$")
    barcode: str | None = Field(None, pattern=r"^[A-Za-z0-9_-]{4,64}$")
    generate_barcode: bool = False
    category_id: UUID
    brand_id: UUID | None = None
    anime_id: UUID | None = None
    character_id: UUID | None = None
    product_type: ProductType
    short_description: str | None = Field(None, max_length=500)
    description: str | None = None
    material: str | None = Field(None, max_length=120)
    edition: str | None = Field(None, max_length=120)
    manufacturer: str | None = Field(None, max_length=160)
    country_of_origin: str | None = Field(None, max_length=100)
    import_reference: str | None = Field(None, max_length=120)
    hsn_code: str | None = Field(None, pattern=r"^\d{4,8}$")
    reorder_level: int = Field(default=0, ge=0)
    unit_of_measure: str = Field(default="piece", min_length=1, max_length=30)
    weight: Decimal | None = Field(None, ge=0)
    length: Decimal | None = Field(None, ge=0)
    width: Decimal | None = Field(None, ge=0)
    height: Decimal | None = Field(None, ge=0)
    is_serialized: bool = False
    has_variants: bool = False
    variants: list[ProductVariantCreateRequest] = Field(default_factory=list)
    status: ProductStatus = ProductStatus.DRAFT
    is_featured: bool = False

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value): return value.strip().upper() if value else value

    @model_validator(mode="after")
    def validate_variant_mode(self):
        if self.has_variants and not self.variants: raise ValueError("variants are required when has_variants is true")
        if not self.has_variants and self.variants: raise ValueError("variants require has_variants=true")
        if self.barcode and self.generate_barcode: raise ValueError("Supply barcode or request generation, not both")
        return self


class ProductUpdateRequest(StrictModel):
    name: str | None = Field(None, min_length=2, max_length=220)
    sku: str | None = Field(None, pattern=r"^[A-Z0-9][A-Z0-9_-]{2,63}$")
    barcode: str | None = Field(None, pattern=r"^[A-Za-z0-9_-]{4,64}$")
    category_id: UUID | None = None; brand_id: UUID | None = None; anime_id: UUID | None = None; character_id: UUID | None = None
    product_type: ProductType | None = None; short_description: str | None = None; description: str | None = None
    material: str | None = None; edition: str | None = None; manufacturer: str | None = None; country_of_origin: str | None = None; import_reference: str | None = None
    hsn_code: str | None = Field(None, pattern=r"^\d{4,8}$")
    gst_rate: Decimal | None = Field(None, ge=0, le=100); purchase_price: Decimal | None = Field(None, ge=0); landed_cost: Decimal | None = Field(None, ge=0); selling_price: Decimal | None = Field(None, ge=0); mrp: Decimal | None = Field(None, ge=0); discount_percentage: Decimal | None = Field(None, ge=0, le=100); minimum_selling_price: Decimal | None = Field(None, ge=0)
    reorder_level: int | None = Field(None, ge=0); unit_of_measure: str | None = None; weight: Decimal | None = Field(None, ge=0); length: Decimal | None = Field(None, ge=0); width: Decimal | None = Field(None, ge=0); height: Decimal | None = Field(None, ge=0)
    is_serialized: bool | None = None; has_variants: bool | None = None; status: ProductStatus | None = None; is_featured: bool | None = None


class ProductStatusUpdateRequest(StrictModel):
    status: ProductStatus
    reason: str | None = Field(None, max_length=500)


class BarcodeGenerateRequest(StrictModel):
    regenerate: bool = False
    format: Literal["CODE128", "EAN13"] = "CODE128"


class BarcodeResponse(BaseModel):
    product_id: UUID; sku: str; barcode: str; format: str = "CODE128"; image_url: str | None = None


class ProductImageCreateRequest(StrictModel):
    file_url: str = Field(max_length=2048)
    alt_text: str | None = Field(None, max_length=255)
    sort_order: int = Field(default=0, ge=0)
    is_primary: bool = False

    @field_validator("file_url")
    @classmethod
    def validate_image(cls, value: str):
        clean = value.split("?", 1)[0].lower()
        if not clean.endswith((".jpg", ".jpeg", ".png", ".webp")): raise ValueError("Only JPEG, PNG and WEBP images are supported")
        if ".." in value: raise ValueError("Invalid image path")
        return value


class ProductImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; file_url: str; alt_text: str | None; sort_order: int; is_primary: bool; created_at: datetime


class ProductVariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; sku: str; barcode: str | None; name: str; purchase_price: Decimal; landed_cost: Decimal | None; selling_price: Decimal; mrp: Decimal | None; status: ProductStatus


class NamedReference(BaseModel):
    id: UUID; name: str; code: str


class ProductResponse(BaseModel):
    id: UUID; sku: str; barcode: str | None; name: str; slug: str; short_description: str | None; description: str | None
    category: NamedReference; brand: NamedReference | None; anime: NamedReference | None; character: NamedReference | None
    product_type: ProductType; material: str | None; edition: str | None; manufacturer: str | None; country_of_origin: str | None; import_reference: str | None
    hsn_code: str | None; gst_rate: Decimal; purchase_price: Decimal; landed_cost: Decimal | None; selling_price: Decimal; mrp: Decimal | None; discount_percentage: Decimal; minimum_selling_price: Decimal | None
    reorder_level: int; unit_of_measure: str; weight: Decimal | None; length: Decimal | None; width: Decimal | None; height: Decimal | None
    is_serialized: bool; has_variants: bool; status: ProductStatus; is_featured: bool; primary_image: str | None; images: list[ProductImageResponse] = []; variants: list[ProductVariantResponse] = []
    created_by_id: UUID | None; updated_by_id: UUID | None; created_at: datetime; updated_at: datetime


class ProductListResponse(BaseModel):
    items: list[ProductResponse]; page: int; page_size: int; total: int; pages: int


class MasterCreateRequest(StrictModel):
    name: str = Field(min_length=2, max_length=160); code: str = Field(min_length=2, max_length=40); description: str | None = None; status: CatalogStatus = CatalogStatus.ACTIVE
    @field_validator("code")
    @classmethod
    def normalize_code(cls, value): return value.strip().upper().replace(" ", "_")


class CategoryCreateRequest(MasterCreateRequest):
    parent_id: UUID | None = None; image_url: str | None = None; sort_order: int = 0
class CategoryUpdateRequest(StrictModel):
    name: str | None = None; code: str | None = None; description: str | None = None; status: CatalogStatus | None = None; parent_id: UUID | None = None; image_url: str | None = None; sort_order: int | None = None
class BrandCreateRequest(MasterCreateRequest):
    country: str | None = None; website: str | None = None; logo_url: str | None = None
class BrandUpdateRequest(StrictModel):
    name: str | None = None; code: str | None = None; description: str | None = None; status: CatalogStatus | None = None; country: str | None = None; website: str | None = None; logo_url: str | None = None
class AnimeCreateRequest(MasterCreateRequest):
    studio: str | None = None; release_year: int | None = Field(None, ge=1900, le=2200); image_url: str | None = None
class AnimeUpdateRequest(StrictModel):
    name: str | None = None; code: str | None = None; description: str | None = None; status: CatalogStatus | None = None; studio: str | None = None; release_year: int | None = Field(None, ge=1900, le=2200); image_url: str | None = None
class CharacterCreateRequest(MasterCreateRequest):
    anime_id: UUID; image_url: str | None = None
class CharacterUpdateRequest(StrictModel):
    name: str | None = None; code: str | None = None; description: str | None = None; status: CatalogStatus | None = None; anime_id: UUID | None = None; image_url: str | None = None


class MasterResponse(BaseModel):
    id: UUID; name: str; code: str; slug: str; description: str | None; status: CatalogStatus; product_count: int = 0; created_at: datetime; updated_at: datetime
class CategoryResponse(MasterResponse):
    parent_id: UUID | None; image_url: str | None; sort_order: int; child_count: int = 0
class CategoryTreeResponse(CategoryResponse):
    children: list["CategoryTreeResponse"] = []
class BrandResponse(MasterResponse):
    country: str | None; website: str | None; logo_url: str | None
class AnimeResponse(MasterResponse):
    studio: str | None; release_year: int | None; image_url: str | None
class CharacterResponse(MasterResponse):
    anime_id: UUID; image_url: str | None


class ImportRowError(BaseModel): row: int; field: str | None; message: str
class ProductImportPreviewResponse(BaseModel): total_rows: int; valid_rows: int; invalid_rows: int; errors: list[ImportRowError]
class ProductImportResultResponse(ProductImportPreviewResponse): created_rows: int; dry_run: bool
