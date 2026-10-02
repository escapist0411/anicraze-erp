from io import BytesIO
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import UploadFile
from pydantic import ValidationError

from app.exceptions.domain import ConflictError
from app.api.v1.billing import barcode as pos_barcode_lookup
from app.models.catalog import Product, ProductType
from app.models.inventory import StockReceiptStatus
from app.repositories.catalog import CatalogRepository
from app.schemas.catalog import ProductCreateRequest, ProductUpdateRequest, ProductVariantCreateRequest
from app.services import catalog
from app.services.inventory import StockReceiptService


@pytest.mark.asyncio
async def test_missing_barcode_svg_is_restored_without_changing_code(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, "UPLOAD_ROOT", tmp_path)
    product = SimpleNamespace(
        id=uuid4(),
        sku="ANI-FIG-000158",
        barcode="ANI-FIG-000158",
        barcode_image_path=str(tmp_path / "barcodes" / "missing.svg"),
    )
    service = catalog.ProductService.__new__(catalog.ProductService)
    service.barcodes = catalog.BarcodeService()
    service.session = SimpleNamespace(flush=AsyncMock())

    await service.ensure_barcode_image(product)

    assert product.barcode == "ANI-FIG-000158"
    assert Path(product.barcode_image_path).is_file()
    assert "ANI-FIG-000158" in Path(product.barcode_image_path).read_text()
    service.session.flush.assert_awaited_once()


def test_code128_generation_preserves_exact_sku_value(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, "UPLOAD_ROOT", tmp_path)
    product = SimpleNamespace(id=uuid4(), sku="ANI-FIG-000158")

    value, generated = catalog.BarcodeService().generate_svg(product)

    assert value == product.sku
    assert Path(generated).is_file()
    assert product.sku in Path(generated).read_text()


def test_product_barcode_inputs_are_trimmed_before_validation():
    category_id = uuid4()
    created = ProductCreateRequest(
        name="Barcode Test Product",
        sku="ANI-FIG-999991",
        barcode="  ANI-FIG-999991  ",
        category_id=category_id,
        product_type=ProductType.FIGURE,
    )
    updated = ProductUpdateRequest(barcode="  ANI-FIG-999992  ")
    variant = ProductVariantCreateRequest(
        name="Variant",
        barcode="  ANI-FIG-999993  ",
        purchase_price=0,
        selling_price=1,
    )

    assert created.barcode == "ANI-FIG-999991"
    assert updated.barcode == "ANI-FIG-999992"
    assert variant.barcode == "ANI-FIG-999993"


def test_product_barcode_rejects_non_code128_master_characters():
    with pytest.raises(ValidationError):
        ProductCreateRequest(
            name="Invalid Barcode Product",
            barcode="not a barcode!",
            category_id=uuid4(),
            product_type=ProductType.FIGURE,
        )


@pytest.mark.asyncio
async def test_product_creation_always_requests_primary_barcode_generation():
    category = SimpleNamespace(code="FIG")
    service = catalog.ProductService.__new__(catalog.ProductService)
    service.actor = SimpleNamespace(id=uuid4())
    service.session = SimpleNamespace(add=MagicMock(), flush=AsyncMock(), refresh=AsyncMock())
    service.repo = SimpleNamespace(product_by_sku=AsyncMock(return_value=None), product_by_barcode=AsyncMock(return_value=None))
    service.skus = SimpleNamespace(generate=AsyncMock())
    service.validate_refs = AsyncMock(return_value=(category, None))
    service.unique_slug = AsyncMock(return_value="barcode-test-product")
    service.generate_barcode = AsyncMock()
    service.ensure_barcode_image = AsyncMock()
    service.audit = AsyncMock()
    request = ProductCreateRequest(
        name="Barcode Test Product",
        sku="ANI-FIG-999994",
        category_id=uuid4(),
        product_type=ProductType.FIGURE,
        status="ACTIVE",
    )

    product = await service.create(request)

    service.generate_barcode.assert_awaited_once_with(product.id, False, "CODE128")
    service.ensure_barcode_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_generated_barcode_cannot_collide_with_variant(tmp_path):
    product = SimpleNamespace(id=uuid4(), sku="ANI-FIG-999995", barcode=None, barcode_image_path=None)
    output = tmp_path / "candidate.svg"
    output.write_text("temporary")
    service = catalog.ProductService.__new__(catalog.ProductService)
    service.get = AsyncMock(return_value=product)
    service.barcodes = SimpleNamespace(generate_svg=MagicMock(return_value=(product.sku, str(output))))
    service.repo = SimpleNamespace(product_by_barcode=AsyncMock(return_value=product))
    service.session = SimpleNamespace(scalar=AsyncMock(return_value=uuid4()))
    service.audit = AsyncMock()

    with pytest.raises(ConflictError, match="Generated barcode already exists"):
        await service.generate_barcode(product.id, False)

    assert not output.exists()
    service.audit.assert_not_awaited()


def create_service() -> catalog.ProductService:
    service = catalog.ProductService.__new__(catalog.ProductService)
    service.actor = SimpleNamespace(id=uuid4())
    service.session = SimpleNamespace(add=MagicMock(), flush=AsyncMock(), refresh=AsyncMock())
    service.repo = SimpleNamespace(product_by_sku=AsyncMock(return_value=None), product_by_barcode=AsyncMock(return_value=None))
    service.skus = SimpleNamespace(generate=AsyncMock())
    service.validate_refs = AsyncMock(return_value=(SimpleNamespace(code="FIG"), None))
    service.unique_slug = AsyncMock(return_value="barcode-test-product")
    service.generate_barcode = AsyncMock()
    service.ensure_barcode_image = AsyncMock()
    service.audit = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_valid_explicit_barcode_is_preserved_and_asset_is_ensured():
    service = create_service()
    request = ProductCreateRequest(
        name="Explicit Barcode Product",
        sku="ANI-FIG-999996",
        barcode="ANI-EXPLICIT-999996",
        category_id=uuid4(),
        product_type=ProductType.FIGURE,
        status="ACTIVE",
    )

    product = await service.create(request)

    assert product.barcode == request.barcode
    service.ensure_barcode_image.assert_awaited_once_with(product)
    service.generate_barcode.assert_not_awaited()


def test_product_barcode_has_database_unique_constraint():
    assert Product.__table__.c.barcode.unique is True


@pytest.mark.asyncio
async def test_csv_import_delegates_valid_missing_barcode_to_automatic_product_creation():
    category_id = uuid4()
    products = SimpleNamespace(
        repo=SimpleNamespace(product_by_sku=AsyncMock(return_value=None), product_by_barcode=AsyncMock(return_value=None)),
        create=AsyncMock(),
    )
    upload = UploadFile(
        filename="products.csv",
        file=BytesIO(f"name,sku,category_id,product_type,status\nImported Product,ANI-FIG-999997,{category_id},FIGURE,ACTIVE\n".encode()),
    )

    result = await catalog.ProductImportService(products).execute(upload, dry_run=False, partial=False)

    assert result.created_rows == 1
    imported = products.create.await_args.args[0]
    assert imported.barcode is None


@pytest.mark.asyncio
async def test_csv_import_rejects_explicit_duplicate_barcode():
    category_id = uuid4()
    products = SimpleNamespace(
        repo=SimpleNamespace(product_by_sku=AsyncMock(return_value=None), product_by_barcode=AsyncMock(return_value=SimpleNamespace(id=uuid4()))),
        create=AsyncMock(),
    )
    upload = UploadFile(
        filename="products.csv",
        file=BytesIO(f"name,sku,barcode,category_id,product_type,status\nDuplicate Product,ANI-FIG-999998,ANI-DUP-999998,{category_id},FIGURE,ACTIVE\n".encode()),
    )

    result = await catalog.ProductImportService(products).execute(upload, dry_run=False, partial=False)

    assert result.invalid_rows == 1
    assert "duplicate barcode" in result.errors[0].message
    products.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_product_creation_propagates_barcode_failure_before_audit():
    service = create_service()
    service.generate_barcode.side_effect = RuntimeError("barcode writer failed")
    request = ProductCreateRequest(
        name="Rollback Barcode Product",
        sku="ANI-FIG-999999",
        category_id=uuid4(),
        product_type=ProductType.FIGURE,
        status="ACTIVE",
    )

    with pytest.raises(RuntimeError, match="barcode writer failed"):
        await service.create(request)

    service.audit.assert_not_awaited()


@pytest.mark.asyncio
async def test_barcode_repository_uses_trimmed_case_insensitive_lookup():
    product = SimpleNamespace(id=uuid4())
    session = SimpleNamespace(scalar=AsyncMock(return_value=product))

    resolved = await CatalogRepository(session).product_by_barcode("  ani-fig-000158  ")

    assert resolved is product
    statement = str(session.scalar.await_args.args[0])
    assert "lower(btrim(products.barcode))" in statement


@pytest.mark.asyncio
async def test_product_pagination_has_unique_tie_breaker_for_imported_timestamps():
    session = SimpleNamespace(
        scalars=AsyncMock(return_value=SimpleNamespace(unique=lambda: SimpleNamespace(all=lambda: []))),
        scalar=AsyncMock(return_value=0),
    )
    await CatalogRepository(session).list_products(page=2, page_size=100)
    statement = str(session.scalars.await_args.args[0])
    assert "ORDER BY products.created_at DESC, products.id ASC" in statement


@pytest.mark.asyncio
async def test_scan_to_godown_matches_barcode_case_insensitively_without_mutation():
    line = SimpleNamespace(
        variant=None,
        product=SimpleNamespace(sku="ANI-FIG-000158", barcode="ANI-FIG-000158"),
        scanned_quantity=1,
        expected_quantity=1,
    )
    receipt = SimpleNamespace(status=StockReceiptStatus.READY_FOR_SCAN, items=[line])
    service = StockReceiptService.__new__(StockReceiptService)
    service.get_receipt = AsyncMock(return_value=receipt)

    with pytest.raises(ConflictError, match="Expected quantity already reached"):
        await service.scan(uuid4(), "  ani-fig-000158  ")

    assert line.scanned_quantity == 1


def test_production_barcode_centre_has_no_manual_generate_action():
    repo_root = Path(__file__).resolve().parents[2]
    barcode_centre = (repo_root / "frontend/src/pages/owner/BarcodeCentre.tsx").read_text()
    single_dialog = (repo_root / "frontend/src/components/inventory/ProductBarcodeDialog.tsx").read_text()
    bulk_dialog = (repo_root / "frontend/src/components/inventory/BulkBarcodePrintDialog.tsx").read_text()
    combined = barcode_centre + single_dialog + bulk_dialog

    assert "Generate Barcode" not in combined
    assert "Generate / Regenerate" not in combined
    assert "productsService.generateBarcode" not in combined
    assert "Print Labels" in barcode_centre
    assert "selling_price" in barcode_centre


def test_approved_thermal_label_contract_is_fixed_and_uses_selling_price():
    repo_root = Path(__file__).resolve().parents[2]
    renderer = (repo_root / "frontend/src/lib/barcode-label.ts").read_text()

    assert "size: 50mm 25mm" in renderer
    assert "width: 46mm" in renderer
    assert "height: 10mm" in renderer
    assert "sellingPrice" in renderer
    assert "purchase_price" not in renderer


def test_canonical_code128_value_remains_compatible_with_pos_lookup():
    source = inspect.getsource(pos_barcode_lookup)

    assert "Product.barcode==barcode" in source
    assert "Product.sku==barcode" in source
    assert "QR" not in source
