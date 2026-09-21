from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.billing import InvoiceStatus, PaymentMethodCode, PaymentStatus, RefundStatus, ReturnStatus
from app.config.business import BUSINESS_PHONE_DISPLAY

class Strict(BaseModel): model_config=ConfigDict(extra="forbid")
class CustomerCreate(Strict): name:str=Field(min_length=2,max_length=180); phone:str|None=Field(None,max_length=30); email:str|None=Field(None,max_length=320); address:str|None=None
class CustomerResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; name:str; phone:str|None; email:str|None; address:str|None
class PaymentInput(Strict): method:PaymentMethodCode; amount:Decimal=Field(gt=0); tendered_amount:Decimal|None=Field(None,gt=0); transaction_reference:str|None=Field(None,max_length=120)
class BillingItemInput(Strict): inventory_id:UUID; quantity:int=Field(gt=0); unit_price:Decimal|None=Field(None,ge=0); discount:Decimal=Field(Decimal("0"),ge=0)
class BillingCreate(Strict):
    idempotency_key:str=Field(min_length=8,max_length=100); customer_id:UUID; store_id:UUID; items:list[BillingItemInput]=Field(min_length=1); payments:list[PaymentInput]=Field(min_length=1); invoice_discount:Decimal=Field(Decimal("0"),ge=0); notes:str|None=None
    @model_validator(mode="after")
    def payment_rules(self):
        for p in self.payments:
            if p.method==PaymentMethodCode.CASH and p.tendered_amount is not None and p.tendered_amount<p.amount: raise ValueError("Cash tendered amount cannot be below payment amount")
            if p.method not in {PaymentMethodCode.CASH,PaymentMethodCode.WALLET,PaymentMethodCode.GIFT_CARD} and not p.transaction_reference: raise ValueError("Electronic payments require transaction_reference")
        return self
class InvoiceItemResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; inventory_id:UUID; product_id:UUID; variant_id:UUID|None; sku:str; product_name:str; quantity:int; unit_price:Decimal; discount:Decimal; line_total:Decimal
class PaymentResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; invoice_id:UUID; payment_method_id:UUID; amount:Decimal; tendered_amount:Decimal|None; change_amount:Decimal; transaction_reference:str|None; status:PaymentStatus; created_at:datetime
class InvoiceResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True); id:UUID; invoice_number:str; customer_id:UUID; store_id:UUID; employee_id:UUID; store_name:str; store_address:str|None; employee_name:str; employee_code:str|None; customer_name:str; customer_address:str|None; payment_methods:list[str]; business_contact:str=BUSINESS_PHONE_DISPLAY; subtotal:Decimal; discount:Decimal; grand_total:Decimal; payment_status:PaymentStatus; invoice_status:InvoiceStatus; notes:str|None; items:list[InvoiceItemResponse]; payments:list[PaymentResponse]; created_at:datetime
class InvoiceCancelRequest(Strict): reason:str=Field(min_length=3,max_length=255)
class ReturnItemInput(Strict): invoice_item_id:UUID; quantity:int=Field(gt=0)
class ReturnCreate(Strict): invoice_id:UUID; reason:str=Field(min_length=2,max_length=255); items:list[ReturnItemInput]=Field(min_length=1); refund_method:PaymentMethodCode; transaction_reference:str|None=None
class ReturnItemResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; invoice_item_id:UUID; quantity:int; amount:Decimal
class ReturnResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; return_number:str; invoice_id:UUID; reason:str; total_amount:Decimal; status:ReturnStatus; items:list[ReturnItemResponse]; created_at:datetime
class RefundResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; refund_number:str; return_id:UUID; payment_method_id:UUID; amount:Decimal; transaction_reference:str|None; status:RefundStatus; created_at:datetime
class BarcodeResult(BaseModel): inventory_id:UUID; product_id:UUID; sku:str; barcode:str|None; name:str; price:Decimal; available_quantity:int
class BillingAnalytics(BaseModel): today_sales:Decimal; weekly_sales:Decimal; monthly_sales:Decimal; average_bill:Decimal; invoice_count:int; top_products:list[dict]; payment_methods:list[dict]
