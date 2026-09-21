from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services import catalog


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

