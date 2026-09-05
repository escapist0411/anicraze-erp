from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import EntityBase, SoftDeleteMixin, TimestampMixin, UUIDMixin, Base


class CatalogStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ProductStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DISCONTINUED = "DISCONTINUED"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    ARCHIVED = "ARCHIVED"


class ProductType(StrEnum):
    FIGURE = "FIGURE"
    MODEL = "MODEL"
    COLLECTIBLE = "COLLECTIBLE"
    PLUSHIE = "PLUSHIE"
    KEYCHAIN = "KEYCHAIN"
    POSTER = "POSTER"
    MANGA = "MANGA"
    APPAREL = "APPAREL"
    ACCESSORY = "ACCESSORY"
    TOY = "TOY"
    OTHER = "OTHER"


class CatalogMasterBase(EntityBase):
    __abstract__ = True
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CatalogStatus] = mapped_column(Enum(CatalogStatus, native_enum=False, length=20), default=CatalogStatus.ACTIVE, nullable=False, index=True)


class Category(CatalogMasterBase):
    __tablename__ = "categories"
    parent_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True, index=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parent: Mapped["Category | None"] = relationship(remote_side="Category.id", back_populates="children")
    children: Mapped[list["Category"]] = relationship(back_populates="parent")


class Brand(CatalogMasterBase):
    __tablename__ = "brands"
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)


class Anime(CatalogMasterBase):
    __tablename__ = "anime_franchises"
    studio: Mapped[str | None] = mapped_column(String(160), nullable=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)


class Character(CatalogMasterBase):
    __tablename__ = "characters"
    anime_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("anime_franchises.id", ondelete="RESTRICT"), nullable=False, index=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    anime: Mapped[Anime] = relationship()


class Product(EntityBase):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("purchase_price >= 0 AND selling_price >= 0", name="ck_products_nonnegative_prices"),
        CheckConstraint("mrp IS NULL OR mrp >= selling_price", name="ck_products_mrp_gte_selling"),
        CheckConstraint("minimum_selling_price IS NULL OR minimum_selling_price <= selling_price", name="ck_products_min_price_lte_selling"),
        CheckConstraint("gst_rate >= 0 AND gst_rate <= 100", name="ck_products_gst_rate"),
        Index("ix_products_created_at", "created_at"),
    )
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    barcode: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(220), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(240), unique=True, nullable=False, index=True)
    short_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    brand_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), nullable=True, index=True)
    anime_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("anime_franchises.id", ondelete="RESTRICT"), nullable=True, index=True)
    character_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("characters.id", ondelete="RESTRICT"), nullable=True, index=True)
    product_type: Mapped[ProductType] = mapped_column(Enum(ProductType, native_enum=False, length=30), nullable=False, index=True)
    material: Mapped[str | None] = mapped_column(String(120), nullable=True)
    edition: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    country_of_origin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    import_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hsn_code: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    landed_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    discount_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    minimum_selling_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(30), default="piece", nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    length: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    width: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    height: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    is_serialized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_variants: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[ProductStatus] = mapped_column(Enum(ProductStatus, native_enum=False, length=30), default=ProductStatus.DRAFT, nullable=False, index=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    barcode_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[Category] = relationship()
    brand: Mapped[Brand | None] = relationship()
    anime: Mapped[Anime | None] = relationship()
    character: Mapped[Character | None] = relationship()
    images: Mapped[list["ProductImage"]] = relationship(back_populates="product", lazy="selectin")
    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product", lazy="selectin")


class ProductImage(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "product_images"
    product_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    product: Mapped[Product] = relationship(back_populates="images")


class ProductVariant(EntityBase):
    __tablename__ = "product_variants"
    product_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    barcode: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    landed_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[ProductStatus] = mapped_column(Enum(ProductStatus, native_enum=False, length=30), default=ProductStatus.ACTIVE, nullable=False)
    product: Mapped[Product] = relationship(back_populates="variants")
