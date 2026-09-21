from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.main import app
from app.models.catalog import ProductStatus, ProductType
from app.schemas.catalog import ProductCreateRequest, ProductImageCreateRequest, ProductUpdateRequest


def valid_product(**overrides):
    values = dict(name="Gojo Figure", category_id=uuid4(), product_type=ProductType.FIGURE, purchase_price="1200", landed_cost="1450", selling_price="2499", mrp="2999")
    values.update(overrides); return values


def test_product_pricing_uses_decimal_and_validates_relationships():
    product = ProductCreateRequest.model_validate(valid_product())
    assert isinstance(product.selling_price, Decimal)
    with pytest.raises(ValidationError): ProductCreateRequest.model_validate(valid_product(mrp="1000"))
    with pytest.raises(ValidationError): ProductCreateRequest.model_validate(valid_product(landed_cost="1000"))


def test_product_payload_rejects_mass_assignment_and_invalid_sku():
    with pytest.raises(ValidationError): ProductCreateRequest.model_validate(valid_product(created_by_id=str(uuid4())))
    with pytest.raises(ValidationError): ProductCreateRequest.model_validate(valid_product(sku="bad sku"))
    with pytest.raises(ValidationError): ProductUpdateRequest.model_validate({"id": str(uuid4())})
    with pytest.raises(ValidationError): ProductCreateRequest.model_validate(valid_product(has_variants=True))
    variant_product = ProductCreateRequest.model_validate(valid_product(has_variants=True, variants=[{"name":"Red XL","purchase_price":"10","selling_price":"20","mrp":"25"}]))
    assert variant_product.variants[0].name == "Red XL"


def test_image_reference_validation_blocks_unsafe_formats_and_traversal():
    ProductImageCreateRequest(file_url="/uploads/products/item.webp")
    with pytest.raises(ValidationError): ProductImageCreateRequest(file_url="../../secret.png")
    with pytest.raises(ValidationError): ProductImageCreateRequest(file_url="payload.svg")


@pytest.mark.asyncio
async def test_openapi_documents_phase_13_catalog_routes():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    expected = {"/api/v1/products", "/api/v1/products/import", "/api/v1/products/export", "/api/v1/products/search/barcode/{barcode}", "/api/v1/products/search/sku/{sku}", "/api/v1/products/{product_id}/barcode", "/api/v1/products/{product_id}/images", "/api/v1/products/{product_id}/history", "/api/v1/categories", "/api/v1/categories/tree", "/api/v1/brands", "/api/v1/anime", "/api/v1/characters"}
    assert expected.issubset(paths)
    list_parameters = {item["name"] for item in paths["/api/v1/products"]["get"]["parameters"]}
    assert {"search", "category_id", "brand_id", "anime_id", "status", "missing_barcode"}.issubset(list_parameters)
    assert "gst_rate" not in list_parameters
    inventory_parameters = {item["name"] for item in paths["/api/v1/inventory"]["get"]["parameters"]}
    assert "product_id" in inventory_parameters
