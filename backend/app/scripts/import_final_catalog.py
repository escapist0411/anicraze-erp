"""Idempotent importer for the client-approved ANICRAZE product master."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import func, select, text

from app.database.session import AsyncSessionFactory
from app.models.auth import User
from app.models.catalog import Anime, Brand, CatalogStatus, Category, Character, Product, ProductImage, ProductStatus, ProductType, ProductVariant
from app.services.catalog import SKUService
from app.utils.time import utc_now

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "anicraze_final_product_master.csv"
IMPORT_PREFIX = "FINAL_PRODUCT_MASTER_2026:"
EXPECTED_PRODUCT_COUNT = 160
CATEGORY_CODES = {
    "Action Figures": "ACTION_FIGURES", "Figure Sets": "FIGURE_SETS", "Qposket Figures": "QPOSKET_FIGURES",
    "Keychains": "KEYCHAINS", "Card & Party Games": "CARD_PARTY_GAMES",
    "Novelty / Collectibles": "NOVELTY_COLLECTIBLES", "Anime Weapons / Props": "ANIME_WEAPONS_PROPS",
}
SERIES_CODES = {
    "Naruto": "NARUTO", "Demon Slayer": "DEMON_SLAYER", "One Piece": "ONE_PIECE",
    "Dragon Ball Z": "DRAGON_BALL_Z", "Jujutsu Kaisen": "JJK", "Marvel / DC / Movies": "MARVEL_DC_MOVIES",
    "Character Sets": "CHARACTER_SETS", "Princess / Superhero": "PRINCESS_SUPERHERO",
    "Generic Types": "GENERIC_TYPES", "Games": "GAMES", "Novelty Items": "NOVELTY_ITEMS",
    "Naruto / General": "NARUTO_GENERAL",
}
CATEGORY_TYPES = {
    "Action Figures": ProductType.FIGURE, "Figure Sets": ProductType.COLLECTIBLE,
    "Qposket Figures": ProductType.FIGURE, "Keychains": ProductType.KEYCHAIN,
    "Card & Party Games": ProductType.TOY, "Novelty / Collectibles": ProductType.COLLECTIBLE,
    "Anime Weapons / Props": ProductType.ACCESSORY,
}
OLD_CATEGORY_CODES = {"FIG", "POS", "MNG", "PLU", "APP", "ACC"}
OLD_ANIME_CODES = {"AOT", "DRAGON_BALL"}
OLD_BRAND_CODES = {"BANDAI", "GOOD_SMILE", "FUNKO", "KOTOBUKIYA", "BANPRESTO"}
OLD_CHARACTER_CODES = {"NARUTO_UZUMAKI", "LUFFY", "GOJO", "TANJIRO", "LEVI", "GOKU"}


@dataclass(frozen=True)
class CatalogRow:
    category: str
    series: str
    product: str
    variant: str | None
    price: Decimal

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.series.casefold(), self.product.casefold(), (self.variant or "").casefold()

    @property
    def display_name(self) -> str:
        return f"{self.product} — {self.variant}" if self.variant else self.product

    @property
    def import_reference(self) -> str:
        digest = hashlib.sha256("|".join(self.identity).encode()).hexdigest()[:20]
        return f"{IMPORT_PREFIX}{digest}"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "item"


def load_catalog(path: Path = DATA_FILE) -> list[CatalogRow]:
    rows: list[CatalogRow] = []
    with path.open(newline="", encoding="utf-8") as source:
        for line_number, raw in enumerate(csv.DictReader(source), start=2):
            values = {key: (raw.get(key) or "").strip() for key in ("category", "series", "product", "variant", "price")}
            if not values["category"] or not values["series"] or not values["product"] or not values["price"]:
                raise ValueError(f"Missing required catalog value on CSV line {line_number}")
            if values["category"] not in CATEGORY_CODES or values["series"] not in SERIES_CODES:
                raise ValueError(f"Unknown category or series on CSV line {line_number}")
            try:
                price = Decimal(values["price"])
            except InvalidOperation as exc:
                raise ValueError(f"Invalid price on CSV line {line_number}") from exc
            if price <= 0:
                raise ValueError(f"Selling price must be positive on CSV line {line_number}")
            variant = None if values["variant"] in {"", "-"} else values["variant"]
            rows.append(CatalogRow(values["category"], values["series"], values["product"], variant, price))
    identities = [row.identity for row in rows]
    if len(rows) != EXPECTED_PRODUCT_COUNT:
        raise ValueError(f"Expected {EXPECTED_PRODUCT_COUNT} products, found {len(rows)}")
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate product + series + variant identity in final catalog")
    return rows


async def _upsert_master(session, model, name: str, code: str, owner_id, sort_order: int = 0):
    item = await session.scalar(select(model).where(func.lower(model.name) == name.casefold()).order_by(model.created_at))
    if item is None:
        slug = f"final-{slugify(name)}"
        if await session.scalar(select(model.id).where(model.slug == slug)):
            slug = f"{slug}-{hashlib.sha1(name.encode()).hexdigest()[:8]}"
        item = model(name=name, code=code, slug=slug, status=CatalogStatus.ACTIVE, created_by_id=owner_id, updated_by_id=owner_id)
        if model is Category:
            item.sort_order = sort_order
        session.add(item)
        await session.flush()
    else:
        item.name, item.status, item.deleted_at, item.updated_by_id = name, CatalogStatus.ACTIVE, None, owner_id
        if model is Category:
            item.parent_id, item.sort_order = None, sort_order
    return item


async def import_catalog(*, dry_run: bool = False) -> dict[str, int]:
    rows, now = load_catalog(), utc_now()
    stats = {"created": 0, "updated": 0, "old_deleted": 0, "old_archived": 0}
    async with AsyncSessionFactory() as session:
        await session.execute(text("SELECT pg_advisory_xact_lock(1602026)"))
        owner = await session.scalar(select(User).where(User.email == "owner@anicraze.com"))
        owner_id = owner.id if owner else None
        categories = {name: await _upsert_master(session, Category, name, code, owner_id, index) for index, (name, code) in enumerate(CATEGORY_CODES.items(), 1)}
        series = {name: await _upsert_master(session, Anime, name, code, owner_id) for name, code in SERIES_CODES.items()}
        existing_products = list((await session.scalars(select(Product))).all())
        by_reference = {p.import_reference: p for p in existing_products if p.import_reference and p.import_reference.startswith(IMPORT_PREFIX)}
        final_ids, sku_service = set(), SKUService()
        for row in rows:
            product = by_reference.get(row.import_reference)
            if product is None:
                product = await session.scalar(select(Product).where(Product.anime_id == series[row.series].id, func.lower(Product.name) == row.display_name.casefold(), func.coalesce(Product.edition, "") == (row.variant or "")).order_by(Product.created_at))
            if product is None:
                product = Product(
                    sku=await sku_service.generate(session, categories[row.category].code), barcode=None,
                    name=row.display_name, slug=f"final-{slugify(row.series + '-' + row.display_name)}-{row.import_reference[-8:]}",
                    category_id=categories[row.category].id, anime_id=series[row.series].id,
                    product_type=CATEGORY_TYPES[row.category], edition=row.variant, import_reference=row.import_reference,
                    gst_rate=Decimal("0"), purchase_price=Decimal("0"), landed_cost=None, selling_price=row.price,
                    mrp=None, discount_percentage=Decimal("0"), minimum_selling_price=None, reorder_level=0,
                    unit_of_measure="piece", status=ProductStatus.ACTIVE, created_by_id=owner_id, updated_by_id=owner_id,
                )
                session.add(product)
                await session.flush()
                stats["created"] += 1
            else:
                product.name, product.category_id, product.anime_id = row.display_name, categories[row.category].id, series[row.series].id
                product.product_type, product.edition, product.import_reference = CATEGORY_TYPES[row.category], row.variant, row.import_reference
                product.selling_price, product.status, product.deleted_at, product.updated_by_id = row.price, ProductStatus.ACTIVE, None, owner_id
                stats["updated"] += 1
            final_ids.add(product.id)
        old_products = [product for product in existing_products if product.id not in final_ids]
        for product in old_products:
            product.status, product.deleted_at, product.updated_by_id = ProductStatus.ARCHIVED, product.deleted_at or now, owner_id
        stats["old_archived"] = len(old_products)
        old_ids = [product.id for product in old_products]
        if old_ids:
            for variant in (await session.scalars(select(ProductVariant).where(ProductVariant.product_id.in_(old_ids)))).all():
                variant.status, variant.deleted_at, variant.updated_by_id = ProductStatus.ARCHIVED, variant.deleted_at or now, owner_id
            for image in (await session.scalars(select(ProductImage).where(ProductImage.product_id.in_(old_ids)))).all():
                image.deleted_at = image.deleted_at or now
        for model, codes in ((Category, OLD_CATEGORY_CODES), (Anime, OLD_ANIME_CODES), (Brand, OLD_BRAND_CODES), (Character, OLD_CHARACTER_CODES)):
            for item in (await session.scalars(select(model).where(model.code.in_(codes)))).all():
                if (model is Category and item.name in CATEGORY_CODES) or (model is Anime and item.name in SERIES_CODES):
                    continue
                item.status, item.deleted_at, item.updated_by_id = CatalogStatus.INACTIVE, item.deleted_at or now, owner_id
        # The approved master defines the complete active category/series vocabulary.
        # Other masters remain in place for historical product relationships only.
        final_category_ids = {item.id for item in categories.values()}
        final_series_ids = {item.id for item in series.values()}
        for item in (await session.scalars(select(Category).where(Category.id.not_in(final_category_ids)))).all():
            item.status, item.deleted_at, item.updated_by_id = CatalogStatus.INACTIVE, item.deleted_at or now, owner_id
        for item in (await session.scalars(select(Anime).where(Anime.id.not_in(final_series_ids)))).all():
            item.status, item.deleted_at, item.updated_by_id = CatalogStatus.INACTIVE, item.deleted_at or now, owner_id
        await session.flush()
        stats["active_final"] = int(await session.scalar(select(func.count(Product.id)).where(Product.deleted_at.is_(None), Product.status == ProductStatus.ACTIVE)) or 0)
        if stats["active_final"] != EXPECTED_PRODUCT_COUNT:
            raise RuntimeError(f"Replacement validation failed: expected 160 active products, found {stats['active_final']}")
        await (session.rollback() if dry_run else session.commit())
    return stats


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(await import_catalog(dry_run=args.dry_run), indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(_main())
