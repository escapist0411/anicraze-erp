from decimal import Decimal
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.models.billing import PaymentMethodCode
from app.schemas.billing import BillingCreate, BillingItemInput, PaymentInput, ReturnCreate
from app.main import app

def test_tax_free_bill_arithmetic():
    assert Decimal("800")*2+Decimal("500") == Decimal("2100")
    assert Decimal("2100")-Decimal("100") == Decimal("2000")
def test_negative_billing_quantity_rejected():
    with pytest.raises(ValidationError): BillingItemInput(inventory_id=uuid4(),quantity=-1)
def test_electronic_payment_requires_reference():
    with pytest.raises(ValidationError): BillingCreate(idempotency_key="sale-request-1",customer_id=uuid4(),store_id=uuid4(),items=[BillingItemInput(inventory_id=uuid4(),quantity=1)],payments=[PaymentInput(method=PaymentMethodCode.UPI,amount=Decimal("1"))])
def test_billing_requires_idempotency_key():
    with pytest.raises(ValidationError): BillingCreate(customer_id=uuid4(),store_id=uuid4(),items=[BillingItemInput(inventory_id=uuid4(),quantity=1)],payments=[PaymentInput(method=PaymentMethodCode.CASH,amount=Decimal("1"))])
def test_production_pos_endpoints_are_exposed():
    paths=app.openapi()["paths"]
    for path in ("/api/v1/billing","/api/v1/billing/search","/api/v1/billing/barcode/{barcode}","/api/v1/billing/customers","/api/v1/invoices","/api/v1/invoices/{id}/pdf"):
        assert path in paths
def test_pos_barcode_schema_has_no_cost_or_margin_fields():
    fields=set(__import__('app.schemas.billing',fromlist=['BarcodeResult']).BarcodeResult.model_fields)
    assert not fields.intersection({"purchase_price","average_cost","inventory_value","profit","margin"})
def test_return_requires_items():
    with pytest.raises(ValidationError): ReturnCreate(invoice_id=uuid4(),reason="bad",items=[],refund_method=PaymentMethodCode.CASH)
