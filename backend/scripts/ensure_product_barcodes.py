#!/usr/bin/env python3
"""Audit and safely complete primary barcodes for active ANICRAZE products."""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import barcode as barcode_library
from barcode.writer import SVGWriter
from dotenv import load_dotenv
from sqlalchemy import func, select, text

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
load_dotenv(BACKEND_ROOT / ".env", override=False)

from app.database.session import AsyncSessionFactory, engine  # noqa: E402
from app.models.catalog import Product, ProductStatus, ProductVariant  # noqa: E402
from app.repositories.catalog import CatalogRepository  # noqa: E402
from app.services.catalog import BarcodeService  # noqa: E402

BARCODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
BARCODE_LOCK_KEY = "anicraze.ensure_product_barcodes.v1"
APPROVED_BARCODE_WIDTH_MM = Decimal("46")
SVG_WIDTH_PATTERN = re.compile(rb'width="([0-9.]+)mm"')


@dataclass
class Metrics:
    active: int = 0
    existing_valid: int = 0
    generated: int = 0
    repaired: int = 0
    missing: int = 0
    duplicate_groups: int = 0
    invalid: int = 0
    render_success: int = 0
    render_failure: int = 0
    asset_success: int = 0
    asset_failure: int = 0
    lookup_success: int = 0
    lookup_failure: int = 0
    fit_failure: int = 0
    problematic_prices: int = 0
    skipped_inactive: int = 0


def normalized(value: str) -> str:
    return value.strip().casefold()


def is_valid_barcode(value: str | None) -> bool:
    return bool(value and value == value.strip() and BARCODE_PATTERN.fullmatch(value))


def render_code128(value: str) -> tuple[bool, Decimal | None, str | None]:
    try:
        rendered = barcode_library.get("code128", value, writer=SVGWriter()).render({"write_text": False})
        match = SVG_WIDTH_PATTERN.search(rendered)
        width = Decimal(match.group(1).decode("ascii")) if match else None
        return True, width, None
    except Exception as error:  # pragma: no cover - library-specific failure details
        return False, None, str(error)[:300]


def duplicate_groups(products: list[Product]) -> dict[str, list[Product]]:
    grouped: dict[str, list[Product]] = defaultdict(list)
    for product in products:
        if product.barcode and product.barcode.strip():
            grouped[normalized(product.barcode)].append(product)
    return {key: rows for key, rows in grouped.items() if len(rows) > 1}


def choose_duplicate_owner(products: list[Product]) -> Product:
    canonical = [product for product in products if product.barcode == product.sku]
    if canonical:
        return sorted(canonical, key=lambda product: (product.created_at, str(product.id)))[0]
    return sorted(products, key=lambda product: (product.created_at, str(product.id)))[0]


async def collect_metrics(session, products: list[Product], skipped_inactive: int) -> tuple[Metrics, list[str]]:
    metrics = Metrics(active=len(products), skipped_inactive=skipped_inactive)
    failures: list[str] = []
    groups = duplicate_groups(products)
    metrics.duplicate_groups = len(groups)
    duplicate_ids = {product.id for rows in groups.values() for product in rows}
    repo = CatalogRepository(session)

    for product in products:
        value = product.barcode
        if not value or not value.strip():
            metrics.missing += 1
            continue
        if not is_valid_barcode(value):
            metrics.invalid += 1
            failures.append(f"invalid barcode: {product.id} | {product.name} | {value!r}")
            continue
        if product.id not in duplicate_ids:
            metrics.existing_valid += 1

        rendered, natural_width, error = render_code128(value)
        if rendered:
            metrics.render_success += 1
            if natural_width is None or natural_width > APPROVED_BARCODE_WIDTH_MM:
                metrics.fit_failure += 1
                failures.append(f"print-fit failure: {product.id} | {product.name} | {value} | natural width {natural_width} mm")
        else:
            metrics.render_failure += 1
            failures.append(f"render failure: {product.id} | {product.name} | {value} | {error}")

        asset_path = Path(product.barcode_image_path) if product.barcode_image_path else None
        if asset_path and asset_path.is_file() and value in asset_path.read_text(encoding="utf-8"):
            metrics.asset_success += 1
        else:
            metrics.asset_failure += 1
            failures.append(f"barcode asset failure: {product.id} | {product.name} | {value}")

        resolved = await repo.product_by_barcode(value)
        if resolved and resolved.id == product.id:
            metrics.lookup_success += 1
        else:
            metrics.lookup_failure += 1
            failures.append(f"lookup failure: {product.id} | {product.name} | {value}")

        if product.selling_price is None or product.selling_price < 0:
            metrics.problematic_prices += 1
            failures.append(f"invalid selling price: {product.id} | {product.name}")
    return metrics, failures


async def run(args: argparse.Namespace) -> int:
    report_path = Path(args.report_path)
    if not report_path.is_absolute():
        report_path = REPO_ROOT / report_path

    async with AsyncSessionFactory() as session:
        async with session.begin():
            database = str(await session.scalar(text("SELECT current_database()")))
            if database != args.expected_database:
                print(f"ERROR: expected database {args.expected_database!r}, connected to {database!r}", file=sys.stderr)
                return 2
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": BARCODE_LOCK_KEY})

            product_stmt = (
                select(Product)
                .where(Product.status == ProductStatus.ACTIVE, Product.deleted_at.is_(None))
                .order_by(Product.created_at, Product.id)
            )
            if args.apply:
                product_stmt = product_stmt.with_for_update()
            products = list((await session.scalars(product_stmt)).all())
            skipped_inactive = int(await session.scalar(select(func.count(Product.id)).where(
                (Product.status != ProductStatus.ACTIVE) | Product.deleted_at.is_not(None)
            )) or 0)
            variants = list((await session.scalars(select(ProductVariant).where(ProductVariant.barcode.is_not(None)))).all())

            before, before_failures = await collect_metrics(session, products, skipped_inactive)
            existing_keys = {
                normalized(product.barcode): product.id
                for product in products
                if product.barcode and product.barcode.strip()
            }
            variant_keys = {normalized(variant.barcode) for variant in variants if variant.barcode and variant.barcode.strip()}
            duplicates = duplicate_groups(products)
            repair_ids: set = set()
            for rows in duplicates.values():
                owner = choose_duplicate_owner(rows)
                repair_ids.update(product.id for product in rows if product.id != owner.id)

            missing_products = [product for product in products if not product.barcode or not product.barcode.strip()]
            invalid_products = [product for product in products if product.barcode and product.barcode.strip() and not is_valid_barcode(product.barcode)]
            repair_ids.update(product.id for product in invalid_products)
            targets = [product for product in products if product in missing_products or product.id in repair_ids]
            target_ids = {product.id for product in targets}
            unresolved: list[str] = []

            for product in targets:
                candidate = product.sku
                key = normalized(candidate)
                owner_id = existing_keys.get(key)
                if not is_valid_barcode(candidate):
                    unresolved.append(f"canonical SKU is not Code128-safe: {product.id} | {product.name} | {candidate!r}")
                elif key in variant_keys:
                    unresolved.append(f"canonical SKU conflicts with a variant barcode: {product.id} | {product.name} | {candidate}")
                elif owner_id is not None and owner_id != product.id and owner_id not in target_ids:
                    unresolved.append(f"canonical SKU conflicts with another product barcode: {product.id} | {product.name} | {candidate}")
                else:
                    rendered, natural_width, error = render_code128(candidate)
                    if not rendered:
                        unresolved.append(f"canonical SKU cannot render as Code128: {product.id} | {product.name} | {candidate} | {error}")
                    elif natural_width is None or natural_width > APPROVED_BARCODE_WIDTH_MM:
                        unresolved.append(f"canonical SKU cannot fit 46 mm barcode area: {product.id} | {product.name} | {candidate} | {natural_width} mm")

            generated = 0
            repaired = 0
            created_paths: list[Path] = []
            if args.apply and not unresolved:
                barcode_service = BarcodeService()
                try:
                    for product in targets:
                        action = "GENERATE" if product in missing_products else "REPAIR"
                        value, path = barcode_service.generate_svg(product, "CODE128")
                        product.barcode = value
                        product.barcode_image_path = path
                        created_paths.append(Path(path))
                        generated += action == "GENERATE"
                        repaired += action == "REPAIR"
                        print(f"{action}: {product.id} | {product.name} | {value}")
                    # Runtime images may be absent after a container restart.
                    # Recreate their assets while preserving valid barcode values.
                    for product in products:
                        if product.id not in target_ids and product.barcode and (
                            not product.barcode_image_path or not Path(product.barcode_image_path).is_file()
                        ):
                            product.barcode_image_path = barcode_service.restore_svg(product)
                            created_paths.append(Path(product.barcode_image_path))
                    await session.flush()
                except Exception:
                    for path in created_paths:
                        path.unlink(missing_ok=True)
                    raise

            if args.apply and unresolved:
                await session.rollback()
            elif not args.apply:
                for product in targets:
                    action = "WOULD GENERATE" if product in missing_products else "WOULD REPAIR"
                    print(f"{action}: {product.id} | {product.name} | {product.sku}")

        # Re-read committed state so validation matches what other connections see.
        await session.rollback()
        products_after = list((await session.scalars(
            select(Product).where(Product.status == ProductStatus.ACTIVE, Product.deleted_at.is_(None)).order_by(Product.created_at, Product.id)
        )).all())
        after, after_failures = await collect_metrics(session, products_after, skipped_inactive)

    longest_barcode_product = max(products_after, key=lambda product: len(product.barcode or ""), default=None)
    longest_name_product = max(products_after, key=lambda product: len(product.name), default=None)
    report_lines = [
        "ANICRAZE BARCODE MASTER AUDIT",
        "==============================",
        f"Database: {database}",
        f"Mode: {'APPLY' if args.apply else 'DRY RUN'}",
        f"Active product count: {after.active}",
        f"Products with existing valid barcode: {before.existing_valid}",
        f"Products with generated barcode: {generated}",
        f"Products repaired: {repaired}",
        f"Duplicate groups before: {before.duplicate_groups}",
        f"Duplicate groups after: {after.duplicate_groups}",
        f"Missing before: {before.missing}",
        f"Missing after: {after.missing}",
        f"Invalid before: {before.invalid}",
        f"Invalid after: {after.invalid}",
        f"Render success count: {after.render_success}",
        f"Render failure count: {after.render_failure}",
        f"Barcode asset success count: {after.asset_success}",
        f"Barcode asset failure count: {after.asset_failure}",
        f"Print-fit failure count: {after.fit_failure}",
        f"Lookup success count: {after.lookup_success}",
        f"Lookup failure count: {after.lookup_failure}",
        f"Longest barcode value length: {len(longest_barcode_product.barcode or '') if longest_barcode_product else 0}",
        f"Longest barcode value: {longest_barcode_product.barcode if longest_barcode_product else 'N/A'}",
        f"Longest product name tested: {longest_name_product.name if longest_name_product else 'N/A'}",
        f"Products with problematic price: {after.problematic_prices}",
        f"Products skipped because inactive/deleted: {after.skipped_inactive}",
        "Barcode architecture: Product.barcode is the single primary printable barcode; no separate barcode table exists.",
        "Barcode format validated: CODE128",
        "Approved label: 50 x 25 mm; barcode area 46 x 10 mm; 203 DPI.",
    ]
    all_failures = unresolved + after_failures
    if all_failures:
        report_lines.extend(["", "UNRESOLVED ISSUES", "-----------------"] + all_failures)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Audit report: {report_path}")

    failed = bool(unresolved or after.asset_failure) if args.dry_run else bool(unresolved or after.missing or after.duplicate_groups or after.invalid or after.render_failure or after.asset_failure or after.fit_failure or after.lookup_failure or after.problematic_prices)
    return 1 if failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Audit and show planned actions without changing data")
    mode.add_argument("--apply", action="store_true", help="Apply safe barcode generation/repairs in one transaction")
    parser.add_argument("--expected-database", default="anicraze_erp", help="Abort unless current_database() matches exactly")
    parser.add_argument("--report-path", default="output/barcode-master-audit.txt")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
