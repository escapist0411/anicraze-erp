"""phase 13 product catalog

Revision ID: 20260806_0004
Revises: 20260806_0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260806_0004"
down_revision = "20260806_0003"
branch_labels = None
depends_on = None


def entity_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def master_columns():
    return [
        sa.Column("name", sa.String(160), nullable=False), sa.Column("code", sa.String(40), nullable=False),
        sa.Column("slug", sa.String(180), nullable=False), sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False), *entity_columns(),
    ]


def entity_constraints():
    return [sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id")]


def master_indexes(table: str):
    for field in ("name", "code", "slug", "status", "deleted_at"):
        op.create_index(f"ix_{table}_{field}", table, [field], unique=field in {"code", "slug"})


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS product_sku_sequence START 1")
    op.create_table("categories", *master_columns(), sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True), sa.Column("image_url", sa.String(2048)), sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False), *entity_constraints(), sa.ForeignKeyConstraint(["parent_id"], ["categories.id"], ondelete="RESTRICT"))
    master_indexes("categories"); op.create_index("ix_categories_parent_id", "categories", ["parent_id"])
    op.create_table("brands", *master_columns(), sa.Column("country", sa.String(100)), sa.Column("website", sa.String(2048)), sa.Column("logo_url", sa.String(2048)), *entity_constraints())
    master_indexes("brands")
    op.create_table("anime_franchises", *master_columns(), sa.Column("studio", sa.String(160)), sa.Column("release_year", sa.Integer()), sa.Column("image_url", sa.String(2048)), *entity_constraints())
    master_indexes("anime_franchises")
    op.create_table("characters", *master_columns(), sa.Column("anime_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("image_url", sa.String(2048)), *entity_constraints(), sa.ForeignKeyConstraint(["anime_id"], ["anime_franchises.id"], ondelete="RESTRICT"))
    master_indexes("characters"); op.create_index("ix_characters_anime_id", "characters", ["anime_id"])
    op.create_table(
        "products",
        sa.Column("sku", sa.String(64), nullable=False), sa.Column("barcode", sa.String(64)), sa.Column("name", sa.String(220), nullable=False), sa.Column("slug", sa.String(240), nullable=False),
        sa.Column("short_description", sa.String(500)), sa.Column("description", sa.Text()),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("brand_id", postgresql.UUID(as_uuid=True)), sa.Column("anime_id", postgresql.UUID(as_uuid=True)), sa.Column("character_id", postgresql.UUID(as_uuid=True)),
        sa.Column("product_type", sa.String(30), nullable=False), sa.Column("material", sa.String(120)), sa.Column("edition", sa.String(120)), sa.Column("manufacturer", sa.String(160)), sa.Column("country_of_origin", sa.String(100)), sa.Column("import_reference", sa.String(120)), sa.Column("hsn_code", sa.String(12)),
        sa.Column("gst_rate", sa.Numeric(5, 2), server_default="0", nullable=False), sa.Column("purchase_price", sa.Numeric(14, 2), server_default="0", nullable=False), sa.Column("landed_cost", sa.Numeric(14, 2)), sa.Column("selling_price", sa.Numeric(14, 2), server_default="0", nullable=False), sa.Column("mrp", sa.Numeric(14, 2)), sa.Column("discount_percentage", sa.Numeric(5, 2), server_default="0", nullable=False), sa.Column("minimum_selling_price", sa.Numeric(14, 2)),
        sa.Column("reorder_level", sa.Integer(), server_default="0", nullable=False), sa.Column("unit_of_measure", sa.String(30), server_default="piece", nullable=False),
        sa.Column("weight", sa.Numeric(12, 3)), sa.Column("length", sa.Numeric(12, 3)), sa.Column("width", sa.Numeric(12, 3)), sa.Column("height", sa.Numeric(12, 3)),
        sa.Column("is_serialized", sa.Boolean(), server_default=sa.false(), nullable=False), sa.Column("has_variants", sa.Boolean(), server_default=sa.false(), nullable=False), sa.Column("status", sa.String(30), server_default="DRAFT", nullable=False), sa.Column("is_featured", sa.Boolean(), server_default=sa.false(), nullable=False), sa.Column("barcode_image_path", sa.String(500)),
        *entity_columns(), *entity_constraints(),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["anime_id"], ["anime_franchises.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("sku"), sa.UniqueConstraint("barcode"), sa.UniqueConstraint("slug"),
        sa.CheckConstraint("purchase_price >= 0 AND selling_price >= 0", name="ck_products_nonnegative_prices"), sa.CheckConstraint("mrp IS NULL OR mrp >= selling_price", name="ck_products_mrp_gte_selling"), sa.CheckConstraint("minimum_selling_price IS NULL OR minimum_selling_price <= selling_price", name="ck_products_min_price_lte_selling"), sa.CheckConstraint("gst_rate >= 0 AND gst_rate <= 100", name="ck_products_gst_rate"),
    )
    for field in ("sku", "barcode", "name", "slug", "status", "category_id", "brand_id", "anime_id", "character_id", "product_type", "hsn_code", "created_at", "deleted_at"):
        op.create_index(f"ix_products_{field}", "products", [field])
    op.create_table("product_images", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("file_path", sa.String(500), nullable=False), sa.Column("file_url", sa.String(2048), nullable=False), sa.Column("alt_text", sa.String(255)), sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False), sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_product_images_product_id", "product_images", ["product_id"]); op.create_index("ix_product_images_deleted_at", "product_images", ["deleted_at"])
    op.create_table("product_variants", sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("sku", sa.String(64), nullable=False), sa.Column("barcode", sa.String(64)), sa.Column("name", sa.String(180), nullable=False), sa.Column("purchase_price", sa.Numeric(14, 2), nullable=False), sa.Column("landed_cost", sa.Numeric(14, 2)), sa.Column("selling_price", sa.Numeric(14, 2), nullable=False), sa.Column("mrp", sa.Numeric(14, 2)), sa.Column("status", sa.String(30), server_default="ACTIVE", nullable=False), *entity_columns(), *entity_constraints(), sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"), sa.UniqueConstraint("sku"), sa.UniqueConstraint("barcode"))
    for field in ("product_id", "sku", "barcode", "deleted_at"): op.create_index(f"ix_product_variants_{field}", "product_variants", [field])


def downgrade() -> None:
    for table in ("product_variants", "product_images", "products", "characters", "anime_franchises", "brands", "categories"): op.drop_table(table)
    op.execute("DROP SEQUENCE IF EXISTS product_sku_sequence")
