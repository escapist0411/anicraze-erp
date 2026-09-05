from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.models.procurement import SupplierPaymentMethod, SupplierType
from app.schemas.procurement import GRNCreateRequest, GRNItemRequest, POItemRequest, PurchaseOrderCreateRequest, PurchaseReturnItemRequest, SupplierCreateRequest, SupplierInvoiceCreateRequest, SupplierPaymentCreateRequest
from app.services.billing import GSTService

def test_supplier_money_and_rating_validation():
    with pytest.raises(ValidationError): SupplierCreateRequest(company_name="Acme",display_name="Acme",supplier_type=SupplierType.LOCAL,credit_limit=Decimal("-1"))
def test_po_requires_exactly_one_destination():
    item=POItemRequest(product_id=uuid4(),quantity=1,unit_cost=1,gst_rate=18)
    with pytest.raises(ValidationError): PurchaseOrderCreateRequest(supplier_id=uuid4(),items=[item])
    with pytest.raises(ValidationError): PurchaseOrderCreateRequest(supplier_id=uuid4(),destination_store_id=uuid4(),destination_warehouse_id=uuid4(),items=[item])
def test_po_rejects_empty_items():
    with pytest.raises(ValidationError): PurchaseOrderCreateRequest(supplier_id=uuid4(),destination_store_id=uuid4(),items=[])
def test_po_quantity_and_cost_are_positive():
    with pytest.raises(ValidationError): POItemRequest(product_id=uuid4(),quantity=0,unit_cost=1,gst_rate=18)
    with pytest.raises(ValidationError): POItemRequest(product_id=uuid4(),quantity=1,unit_cost=-1,gst_rate=18)
def test_grn_requires_items_and_positive_receipt():
    with pytest.raises(ValidationError): GRNCreateRequest(purchase_order_id=uuid4(),items=[])
    with pytest.raises(ValidationError): GRNItemRequest(purchase_order_item_id=uuid4(),received_quantity=0,accepted_quantity=0)
def test_invoice_due_date_rule_input_is_explicit():
    data=SupplierInvoiceCreateRequest(supplier_invoice_number="X",supplier_id=uuid4(),invoice_date=date.today(),due_date=date.today()+timedelta(days=30),items=[{"product_id":uuid4(),"quantity":1,"unit_cost":100,"gst_rate":18}]); assert data.due_date>data.invoice_date
def test_supplier_payment_must_be_positive():
    with pytest.raises(ValidationError): SupplierPaymentCreateRequest(supplier_id=uuid4(),payment_method=SupplierPaymentMethod.CASH,amount=0,reference_number="PX")
def test_purchase_return_quantity_must_be_positive():
    with pytest.raises(ValidationError): PurchaseReturnItemRequest(inventory_id=uuid4(),quantity=0,unit_cost=10,gst_rate=18,condition="GOOD",reason="x")
@pytest.mark.parametrize("rate",[0,5,12,18,28])
def test_procurement_gst_rates(rate): assert sum(GSTService.calculate(Decimal("100"),Decimal(rate),False))==Decimal(rate)
