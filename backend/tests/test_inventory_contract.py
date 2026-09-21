from decimal import Decimal
import inspect
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.models.inventory import StockReceiptStatus, TransferStatus
from app.schemas.inventory import InventoryCreateRequest, StockMovementRequest, StockReceiptCreate, TransferCreateRequest, TransferPickRequest, TransferReceiveRequest
from app.main import app
from app.services.inventory import StockReceiptService, TransferService
from app.exceptions.domain import AuthorizationError, ConflictError
from types import SimpleNamespace
import httpx

def test_inventory_requires_exactly_one_location():
    with pytest.raises(ValidationError): InventoryCreateRequest(product_id=uuid4())
    with pytest.raises(ValidationError): InventoryCreateRequest(product_id=uuid4(),store_id=uuid4(),warehouse_id=uuid4())

def test_inventory_thresholds_are_validated():
    with pytest.raises(ValidationError): InventoryCreateRequest(product_id=uuid4(),store_id=uuid4(),minimum_stock=10,maximum_stock=5)

def test_movements_require_positive_quantity_and_idempotency():
    with pytest.raises(ValidationError): StockMovementRequest(quantity=0,reference_number="PO",idempotency_key="12345678")
    assert StockMovementRequest(quantity=2,reference_number="PO",idempotency_key="purchase-1",unit_cost=Decimal("10")).quantity==2

def test_transfer_source_and_target_must_differ():
    location=uuid4()
    with pytest.raises(ValidationError): TransferCreateRequest(reference_number="T-1",source_store_id=location,target_store_id=location,items=[{"product_id":uuid4(),"quantity":1}])

@pytest.mark.asyncio
async def test_inventory_openapi_exposes_product_filter_and_full_export():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
        paths=(await client.get("/api/v1/openapi.json")).json()["paths"]
    assert "/api/v1/inventory/export" in paths
    parameters={item["name"] for item in paths["/api/v1/inventory"]["get"]["parameters"]}
    assert "product_id" in parameters
    expected={"/api/v1/stock-transfers/{id}/pick","/api/v1/stock-transfers/{id}/receive"}
    assert expected.issubset(paths)

def test_phase_3_transfer_contracts_cover_picking_receipt_and_discrepancy():
    item=uuid4()
    pick=TransferPickRequest(items=[{"item_id":item,"picked_quantity":4}])
    receipt=TransferReceiveRequest(items=[{"item_id":item,"received_quantity":3,"damaged_quantity":1,"excess_quantity":0,"note":"one damaged"}])
    assert pick.items[0].picked_quantity==4
    assert receipt.items[0].received_quantity+receipt.items[0].damaged_quantity==4
    assert {TransferStatus.PENDING_APPROVAL,TransferStatus.PICKING,TransferStatus.PICKED,TransferStatus.RECEIVING,TransferStatus.DISCREPANCY,TransferStatus.REJECTED}.issubset(set(TransferStatus))

def test_transfer_creation_can_delegate_business_number_generation():
    request=TransferCreateRequest(source_warehouse_id=uuid4(),target_store_id=uuid4(),items=[{"product_id":uuid4(),"quantity":1}])
    assert request.reference_number is None

def test_multi_product_transfer_and_receipt_contract():
    request=TransferCreateRequest(source_warehouse_id=uuid4(),target_store_id=uuid4(),items=[{"product_id":uuid4(),"quantity":2},{"product_id":uuid4(),"quantity":3}])
    assert len(request.items)==2 and sum(item.quantity for item in request.items)==5
    assert "/api/v1/stock-transfers/{id}/receipt" in {route.path for route in app.routes}

def test_created_transfer_is_eagerly_reloaded_for_response_serialization():
    source=inspect.getsource(TransferService.create_transfer)
    assert "created = await self.repo.transfer(t.id)" in source
    assert "return created" in source

def test_simple_stock_receipt_requires_cost_and_multiple_products():
    request=StockReceiptCreate(warehouse_id=uuid4(),items=[{"product_id":uuid4(),"quantity":10,"unit_cost":"400"},{"product_id":uuid4(),"quantity":8,"unit_cost":"220"}])
    assert sum(item.quantity for item in request.items)==18
    assert request.items[0].unit_cost==Decimal("400")
    with pytest.raises(ValidationError): StockReceiptCreate(warehouse_id=uuid4(),items=[{"product_id":uuid4(),"quantity":0,"unit_cost":"400"}])

def actor_with_role(code):
    return SimpleNamespace(roles=[SimpleNamespace(code=code)])

def test_stock_receipt_accepts_no_supplier_for_owner_and_manager():
    request=StockReceiptCreate(warehouse_id=uuid4(),supplier_id=None,supplier_name=None,items=[{"product_id":uuid4(),"quantity":10,"purchase_cost":"400"}])
    StockReceiptService.validate_payable_request(request,actor_with_role("OWNER"))
    StockReceiptService.validate_payable_request(request,actor_with_role("MANAGER"))
    assert request.supplier_id is None and request.supplier_name is None and request.items[0].unit_cost==Decimal("400")

def test_stock_receipt_accepts_optional_supplier_reference():
    supplier_id=uuid4()
    request=StockReceiptCreate(warehouse_id=uuid4(),supplier_id=supplier_id,supplier_name="Existing Supplier",items=[{"product_id":uuid4(),"quantity":10,"unit_cost":"400"}])
    StockReceiptService.validate_payable_request(request,actor_with_role("OWNER"))
    assert request.supplier_id==supplier_id and request.supplier_name=="Existing Supplier"

def test_purchase_payable_requires_supplier_with_approved_message():
    request=StockReceiptCreate(warehouse_id=uuid4(),payment_option="PAY_LATER",items=[{"product_id":uuid4(),"quantity":10,"unit_cost":"400"}])
    with pytest.raises(ConflictError,match="Select a supplier to track this purchase payment"):
        StockReceiptService.validate_payable_request(request,actor_with_role("OWNER"))

def test_manager_cannot_create_purchase_payable():
    request=StockReceiptCreate(warehouse_id=uuid4(),supplier_id=uuid4(),payment_option="PAY_LATER",items=[{"product_id":uuid4(),"quantity":10,"unit_cost":"400"}])
    with pytest.raises(AuthorizationError):
        StockReceiptService.validate_payable_request(request,actor_with_role("MANAGER"))

def test_simple_stock_receipt_routes_and_statuses_are_exposed():
    paths={route.path for route in app.routes}
    assert {"/api/v1/stock-receipts","/api/v1/stock-receipt-suppliers","/api/v1/stock-receipts/import-pdf","/api/v1/stock-receipts/{id}/scan","/api/v1/stock-receipts/{id}/finalize"}.issubset(paths)
    assert {StockReceiptStatus.READY_FOR_BARCODE,StockReceiptStatus.READY_FOR_SCAN,StockReceiptStatus.COMPLETED}.issubset(set(StockReceiptStatus))
