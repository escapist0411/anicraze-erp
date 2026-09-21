from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.inventory import AlertStatus, AlertType, AdjustmentStatus, LocationStatus, LocationType, ReservationStatus, StockReceiptStatus, TransactionType, TransferStatus
from app.models.payables import PayablePaymentMethod


class StrictModel(BaseModel): model_config=ConfigDict(extra="forbid")
class StoreCreateRequest(StrictModel): code:str=Field(min_length=2,max_length=40); name:str=Field(min_length=2,max_length=160); short_name:str|None=Field(None,max_length=100); location_type:LocationType=LocationType.PERMANENT_STORE; address:str|None=None; contact_number:str|None=Field(None,max_length=30); status:LocationStatus=LocationStatus.ACTIVE
class StoreUpdateRequest(StrictModel): name:str|None=Field(None,min_length=2,max_length=160); short_name:str|None=Field(None,max_length=100); location_type:LocationType|None=None; address:str|None=None; contact_number:str|None=Field(None,max_length=30); status:LocationStatus|None=None
class WarehouseCreateRequest(StrictModel): code:str=Field(min_length=2,max_length=40); name:str=Field(min_length=2,max_length=160); address:str|None=None; status:LocationStatus=LocationStatus.ACTIVE
class LocationResponse(BaseModel): id:UUID; code:str; name:str; short_name:str|None=None; address:str|None; contact_number:str|None=None; location_type:LocationType|None=None; status:LocationStatus


class InventoryCreateRequest(StrictModel):
    product_id:UUID; variant_id:UUID|None=None; store_id:UUID|None=None; warehouse_id:UUID|None=None
    opening_quantity:int=Field(default=0,ge=0); minimum_stock:int=Field(default=0,ge=0); maximum_stock:int|None=Field(None,ge=0); reorder_level:int=Field(default=0,ge=0); average_cost:Decimal=Field(default=Decimal("0"),ge=0); reference_number:str|None=Field(None,max_length=100)
    @model_validator(mode="after")
    def location(self):
        if (self.store_id is None)==(self.warehouse_id is None): raise ValueError("Exactly one store_id or warehouse_id is required")
        if self.maximum_stock is not None and self.maximum_stock < self.minimum_stock: raise ValueError("maximum_stock cannot be below minimum_stock")
        return self
class InventoryUpdateRequest(StrictModel):
    minimum_stock:int|None=Field(None,ge=0); maximum_stock:int|None=Field(None,ge=0); reorder_level:int|None=Field(None,ge=0); average_cost:Decimal|None=Field(None,ge=0); last_purchase_cost:Decimal|None=Field(None,ge=0)
class StockMovementRequest(StrictModel):
    quantity:int=Field(gt=0); reference_number:str=Field(min_length=2,max_length=100); idempotency_key:str=Field(min_length=8,max_length=100); unit_cost:Decimal|None=Field(None,ge=0); batch_number:str|None=Field(None,max_length=100); remarks:str|None=None


class InventoryResponse(BaseModel):
    id:UUID; product_id:UUID; variant_id:UUID|None; sku:str; barcode:str|None; product_name:str; category:str; brand:str|None; anime:str|None
    store:LocationResponse|None; warehouse:LocationResponse|None; available_quantity:int; reserved_quantity:int; damaged_quantity:int; total_quantity:int; minimum_stock:int; maximum_stock:int|None; reorder_level:int; average_cost:Decimal; last_purchase_cost:Decimal|None; inventory_value:Decimal; stock_level:str; reorder_recommended:bool; last_movement_at:datetime|None; updated_at:datetime
class InventoryListResponse(BaseModel): items:list[InventoryResponse]; page:int; page_size:int; total:int; pages:int
class InventoryTransactionResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True); id:UUID; inventory_id:UUID; product_id:UUID; store_id:UUID|None; warehouse_id:UUID|None; transaction_type:TransactionType; quantity:int; unit_cost:Decimal|None; reference_number:str; batch_number:str|None; remarks:str|None; created_by_id:UUID|None; created_at:datetime
class LedgerResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True); id:UUID; transaction_id:UUID; inventory_id:UUID; product_id:UUID; store_id:UUID|None; warehouse_id:UUID|None; transaction_type:TransactionType; quantity_before:int; quantity_changed:int; quantity_after:int; reference_number:str; batch_number:str|None; created_by_id:UUID|None; created_at:datetime


class TransferItemRequest(StrictModel): product_id:UUID; variant_id:UUID|None=None; quantity:int=Field(gt=0); batch_number:str|None=None
class TransferCreateRequest(StrictModel):
    reference_number:str|None=Field(None,min_length=3,max_length=100); source_store_id:UUID|None=None; source_warehouse_id:UUID|None=None; target_store_id:UUID|None=None; target_warehouse_id:UUID|None=None; items:list[TransferItemRequest]=Field(min_length=1); remarks:str|None=None
    @model_validator(mode="after")
    def locations(self):
        if (self.source_store_id is None)==(self.source_warehouse_id is None): raise ValueError("Exactly one source location is required")
        if (self.target_store_id is None)==(self.target_warehouse_id is None): raise ValueError("Exactly one target location is required")
        if self.source_store_id==self.target_store_id and self.source_store_id is not None: raise ValueError("Source and target must differ")
        if self.source_warehouse_id==self.target_warehouse_id and self.source_warehouse_id is not None: raise ValueError("Source and target must differ")
        return self
class TransferStatusRequest(StrictModel): status:TransferStatus; reason:str|None=Field(None,max_length=500)
class TransferPickItemRequest(StrictModel): item_id:UUID; picked_quantity:int=Field(ge=0)
class TransferPickRequest(StrictModel): items:list[TransferPickItemRequest]=Field(min_length=1)
class TransferReceiveItemRequest(StrictModel): item_id:UUID; received_quantity:int=Field(ge=0); damaged_quantity:int=Field(0,ge=0); excess_quantity:int=Field(0,ge=0); note:str|None=Field(None,max_length=500)
class TransferReceiveRequest(StrictModel): items:list[TransferReceiveItemRequest]=Field(min_length=1); notes:str|None=Field(None,max_length=1000)
class TransferItemResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; product_id:UUID; variant_id:UUID|None; product_name:str; sku:str; barcode:str|None; quantity:int; picked_quantity:int=0; received_quantity:int=0; damaged_quantity:int=0; shortage_quantity:int=0; excess_quantity:int=0; discrepancy_note:str|None=None; batch_number:str|None
class TransferResponse(BaseModel):
    id:UUID; reference_number:str; source_store_id:UUID|None; source_warehouse_id:UUID|None; target_store_id:UUID|None; target_warehouse_id:UUID|None; status:TransferStatus; remarks:str|None; items:list[TransferItemResponse]; created_by_id:UUID|None; approved_by_id:UUID|None; picked_by_id:UUID|None=None; packed_by_id:UUID|None=None; dispatched_by_id:UUID|None=None; received_by_id:UUID|None=None; approved_at:datetime|None=None; picking_started_at:datetime|None=None; picked_at:datetime|None=None; packed_at:datetime|None=None; dispatched_at:datetime|None; receiving_started_at:datetime|None=None; received_at:datetime|None; completed_at:datetime|None; cancellation_reason:str|None=None; discrepancy_notes:str|None=None; created_at:datetime


class AdjustmentItemRequest(StrictModel): inventory_id:UUID; quantity_change:int; batch_number:str|None=None; remarks:str|None=None
class AdjustmentCreateRequest(StrictModel): reference_number:str=Field(min_length=3,max_length=100); reason:str=Field(min_length=2,max_length=255); items:list[AdjustmentItemRequest]=Field(min_length=1)
class AdjustmentItemResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; inventory_id:UUID; quantity_change:int; batch_number:str|None; remarks:str|None
class AdjustmentResponse(BaseModel): id:UUID; reference_number:str; reason:str; status:AdjustmentStatus; items:list[AdjustmentItemResponse]; created_by_id:UUID|None; created_at:datetime


class ReservationCreateRequest(StrictModel): reference_number:str=Field(min_length=2,max_length=100); inventory_id:UUID; quantity:int=Field(gt=0); batch_number:str|None=None; expires_at:datetime|None=None
class ReservationResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; reference_number:str; inventory_id:UUID; quantity:int; batch_number:str|None; status:ReservationStatus; expires_at:datetime|None; released_at:datetime|None; created_by_id:UUID|None; created_at:datetime
class AlertResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; inventory_id:UUID; alert_type:AlertType; status:AlertStatus; quantity_at_trigger:int; threshold:int; resolved_at:datetime|None; resolved_by_id:UUID|None; created_at:datetime


class InventoryAnalyticsResponse(BaseModel): total_inventory_value:Decimal; total_available_quantity:int; total_reserved_quantity:int; low_stock_count:int; out_of_stock_count:int; reorder_count:int; dead_stock_count:int; fast_moving:list[dict]; slow_moving:list[dict]; top_products:list[dict]; store_comparison:list[dict]; warehouse_comparison:list[dict]


class StockReceiptItemCreate(StrictModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(gt=0, le=100000)
    unit_cost: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class StockReceiptCreate(StrictModel):
    warehouse_id: UUID
    supplier_name: str | None = Field(None, max_length=180)
    invoice_number: str | None = Field(None, max_length=100)
    purchase_date: date | None = None
    notes: str | None = Field(None, max_length=2000)
    items: list[StockReceiptItemCreate] = Field(min_length=1, max_length=200)
    supplier_id: UUID | None = None
    payment_option: str | None = Field(None, pattern="^(FULLY_PAID|PARTIALLY_PAID|PAY_LATER)$")
    initially_paid: Decimal = Field(default=Decimal("0"), ge=0)
    initial_payment_method: PayablePaymentMethod | None = None
    payment_due_date: date | None = None
    payment_remind_at: datetime | None = None


class StockReceiptScanRequest(StrictModel):
    code: str = Field(min_length=1, max_length=160)


class StockReceiptItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_id: UUID | None
    product_name: str
    sku: str
    barcode: str | None
    expected_quantity: int
    scanned_quantity: int
    unit_cost: Decimal
    selling_price: Decimal


class StockReceiptResponse(BaseModel):
    id: UUID
    reference_number: str
    warehouse_id: UUID
    status: StockReceiptStatus
    supplier_name: str | None
    invoice_number: str | None
    purchase_date: date | None
    notes: str | None
    items: list[StockReceiptItemResponse]
    total_products: int
    total_expected: int
    total_scanned: int
    total_purchase_value: Decimal
    completed_at: datetime | None
    created_at: datetime


class StockPdfImportRow(BaseModel):
    detected_product: str
    suggested_product_id: UUID | None
    suggested_product_name: str | None
    quantity: int
    unit_cost: Decimal
    status: str


class StockPdfImportPreview(BaseModel):
    rows: list[StockPdfImportRow]
    readable_text: bool
    message: str
