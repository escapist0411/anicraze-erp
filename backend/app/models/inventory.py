from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, EntityBase, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.catalog import Product, ProductVariant


class LocationStatus(StrEnum): ACTIVE = "ACTIVE"; INACTIVE = "INACTIVE"
class LocationType(StrEnum): PERMANENT_STORE="PERMANENT_STORE"; EVENT_LOCATION="EVENT_LOCATION"
class TransactionType(StrEnum): PURCHASE="PURCHASE"; SALE="SALE"; RETURN="RETURN"; TRANSFER_IN="TRANSFER_IN"; TRANSFER_OUT="TRANSFER_OUT"; ADJUSTMENT="ADJUSTMENT"; OPENING_STOCK="OPENING_STOCK"; DAMAGE="DAMAGE"; EXPIRED="EXPIRED"
class TransferStatus(StrEnum): CREATED="CREATED"; PENDING_APPROVAL="PENDING_APPROVAL"; APPROVED="APPROVED"; PICKING="PICKING"; PICKED="PICKED"; PACKED="PACKED"; DISPATCHED="DISPATCHED"; RECEIVING="RECEIVING"; DISCREPANCY="DISCREPANCY"; COMPLETED="COMPLETED"; CANCELLED="CANCELLED"; REJECTED="REJECTED"
class ReservationStatus(StrEnum): ACTIVE="ACTIVE"; RELEASED="RELEASED"; CONSUMED="CONSUMED"; EXPIRED="EXPIRED"
class AlertType(StrEnum): LOW_STOCK="LOW_STOCK"; OUT_OF_STOCK="OUT_OF_STOCK"; REORDER="REORDER"
class AlertStatus(StrEnum): OPEN="OPEN"; RESOLVED="RESOLVED"
class AdjustmentStatus(StrEnum): COMPLETED="COMPLETED"; REVERSED="REVERSED"
class StockReceiptStatus(StrEnum): DRAFT="DRAFT"; READY_FOR_BARCODE="READY_FOR_BARCODE"; READY_FOR_SCAN="READY_FOR_SCAN"; COMPLETED="COMPLETED"; CANCELLED="CANCELLED"


class Store(EntityBase):
    __tablename__ = "stores"
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True); name: Mapped[str] = mapped_column(String(160), index=True); short_name: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text); contact_number: Mapped[str | None] = mapped_column(String(30)); location_type: Mapped[LocationType] = mapped_column(Enum(LocationType,native_enum=False,length=30),default=LocationType.PERMANENT_STORE,index=True); status: Mapped[LocationStatus] = mapped_column(Enum(LocationStatus, native_enum=False, length=20), default=LocationStatus.ACTIVE, index=True)


class EmployeeLocationSequence(UUIDMixin, Base):
    __tablename__ = "employee_location_sequences"
    store_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), unique=True, index=True)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Warehouse(EntityBase):
    __tablename__ = "warehouses"
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True); name: Mapped[str] = mapped_column(String(160), index=True)
    address: Mapped[str | None] = mapped_column(Text); status: Mapped[LocationStatus] = mapped_column(Enum(LocationStatus, native_enum=False, length=20), default=LocationStatus.ACTIVE, index=True)


class Inventory(EntityBase):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("product_id", "variant_id", "store_id", "warehouse_id", name="uq_inventory_product_variant_location", postgresql_nulls_not_distinct=True),
        CheckConstraint("(store_id IS NOT NULL AND warehouse_id IS NULL) OR (store_id IS NULL AND warehouse_id IS NOT NULL)", name="ck_inventory_single_location"),
        CheckConstraint("available_quantity >= 0 AND reserved_quantity >= 0 AND damaged_quantity >= 0", name="ck_inventory_nonnegative_quantities"),
    )
    product_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    variant_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), index=True)
    store_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    warehouse_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    available_quantity: Mapped[int] = mapped_column(Integer, default=0); reserved_quantity: Mapped[int] = mapped_column(Integer, default=0); damaged_quantity: Mapped[int] = mapped_column(Integer, default=0)
    minimum_stock: Mapped[int] = mapped_column(Integer, default=0); maximum_stock: Mapped[int | None] = mapped_column(Integer); reorder_level: Mapped[int] = mapped_column(Integer, default=0)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(14,2), default=Decimal("0")); last_purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(14,2)); inventory_value: Mapped[Decimal] = mapped_column(Numeric(18,2), default=Decimal("0"))
    last_movement_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    product: Mapped[Product] = relationship(); variant: Mapped[ProductVariant | None] = relationship(); store: Mapped[Store | None] = relationship(); warehouse: Mapped[Warehouse | None] = relationship()


class StoreInventory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "store_inventory"
    inventory_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("inventory.id", ondelete="CASCADE"), unique=True, index=True)
    store_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True)


class WarehouseInventory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "warehouse_inventory"
    inventory_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("inventory.id", ondelete="CASCADE"), unique=True, index=True)
    warehouse_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), index=True)


class InventoryTransaction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "inventory_transactions"
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    inventory_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("inventory.id", ondelete="RESTRICT"), index=True)
    product_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    store_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), index=True); warehouse_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, native_enum=False, length=30), index=True)
    quantity: Mapped[int] = mapped_column(Integer); unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14,2)); reference_number: Mapped[str] = mapped_column(String(100), index=True)
    batch_number: Mapped[str | None] = mapped_column(String(100), index=True); remarks: Mapped[str | None] = mapped_column(Text); created_by_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)


class InventoryLedger(UUIDMixin, Base):
    __tablename__ = "inventory_ledger"
    __table_args__ = (UniqueConstraint("transaction_id", name="uq_inventory_ledger_transaction"),)
    transaction_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("inventory_transactions.id", ondelete="RESTRICT"), index=True)
    inventory_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("inventory.id", ondelete="RESTRICT"), index=True); product_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    store_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), index=True); warehouse_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, native_enum=False, length=30), index=True); quantity_before: Mapped[int] = mapped_column(Integer); quantity_changed: Mapped[int] = mapped_column(Integer); quantity_after: Mapped[int] = mapped_column(Integer)
    reference_number: Mapped[str] = mapped_column(String(100), index=True); batch_number: Mapped[str | None] = mapped_column(String(100), index=True); created_by_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class StockTransfer(EntityBase):
    __tablename__ = "stock_transfers"
    reference_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    source_store_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT")); source_warehouse_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT")); target_store_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT")); target_warehouse_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"))
    status: Mapped[TransferStatus] = mapped_column(Enum(TransferStatus, native_enum=False, length=30), default=TransferStatus.CREATED, index=True); remarks: Mapped[str | None] = mapped_column(Text); approved_by_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")); picked_by_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")); packed_by_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")); dispatched_by_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")); received_by_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")); approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); picking_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); picked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); packed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); receiving_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); cancellation_reason: Mapped[str | None] = mapped_column(Text); discrepancy_notes: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list["StockTransferItem"]] = relationship(back_populates="transfer", lazy="selectin", cascade="all, delete-orphan")


class StockTransferItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "stock_transfer_items"
    transfer_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("stock_transfers.id", ondelete="CASCADE"), index=True); product_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True); variant_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT")); quantity: Mapped[int] = mapped_column(Integer); picked_quantity: Mapped[int] = mapped_column(Integer,default=0); received_quantity: Mapped[int] = mapped_column(Integer,default=0); damaged_quantity: Mapped[int] = mapped_column(Integer,default=0); shortage_quantity: Mapped[int] = mapped_column(Integer,default=0); excess_quantity: Mapped[int] = mapped_column(Integer,default=0); batch_number: Mapped[str | None] = mapped_column(String(100)); discrepancy_note: Mapped[str | None] = mapped_column(Text); transfer: Mapped[StockTransfer] = relationship(back_populates="items"); product:Mapped[Product]=relationship(); variant:Mapped[ProductVariant|None]=relationship()
    @property
    def product_name(self): return self.product.name
    @property
    def sku(self): return self.variant.sku if self.variant else self.product.sku
    @property
    def barcode(self): return self.variant.barcode if self.variant else self.product.barcode


class StockAdjustment(EntityBase):
    __tablename__ = "stock_adjustments"
    reference_number: Mapped[str] = mapped_column(String(100), unique=True, index=True); reason: Mapped[str] = mapped_column(String(255)); status: Mapped[AdjustmentStatus] = mapped_column(Enum(AdjustmentStatus, native_enum=False, length=30), default=AdjustmentStatus.COMPLETED); items: Mapped[list["StockAdjustmentItem"]] = relationship(back_populates="adjustment", lazy="selectin", cascade="all, delete-orphan")


class StockAdjustmentItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "stock_adjustment_items"
    adjustment_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("stock_adjustments.id", ondelete="CASCADE"), index=True); inventory_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("inventory.id", ondelete="RESTRICT"), index=True); quantity_change: Mapped[int] = mapped_column(Integer); batch_number: Mapped[str | None] = mapped_column(String(100)); remarks: Mapped[str | None] = mapped_column(Text); adjustment: Mapped[StockAdjustment] = relationship(back_populates="items")


class StockReservation(EntityBase):
    __tablename__ = "stock_reservations"
    __table_args__ = (UniqueConstraint("reference_number", "inventory_id", name="uq_stock_reservation_reference_inventory"),)
    reference_number: Mapped[str] = mapped_column(String(100), index=True); inventory_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("inventory.id", ondelete="RESTRICT"), index=True); quantity: Mapped[int] = mapped_column(Integer); batch_number: Mapped[str | None] = mapped_column(String(100)); status: Mapped[ReservationStatus] = mapped_column(Enum(ReservationStatus, native_enum=False, length=30), default=ReservationStatus.ACTIVE, index=True); expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True); released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InventoryAlert(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "inventory_alerts"
    inventory_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("inventory.id", ondelete="CASCADE"), index=True); alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType, native_enum=False, length=30), index=True); status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus, native_enum=False, length=20), default=AlertStatus.OPEN, index=True); quantity_at_trigger: Mapped[int] = mapped_column(Integer); threshold: Mapped[int] = mapped_column(Integer); resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); resolved_by_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class StockReceipt(EntityBase):
    __tablename__ = "stock_receipts"
    reference_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    warehouse_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    status: Mapped[StockReceiptStatus] = mapped_column(Enum(StockReceiptStatus, native_enum=False, length=30), default=StockReceiptStatus.READY_FOR_BARCODE, index=True)
    supplier_name: Mapped[str | None] = mapped_column(String(180))
    invoice_number: Mapped[str | None] = mapped_column(String(100))
    purchase_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list["StockReceiptItem"]] = relationship(back_populates="receipt", lazy="selectin", cascade="all, delete-orphan")


class StockReceiptItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "stock_receipt_items"
    __table_args__ = (
        UniqueConstraint("receipt_id", "product_id", "variant_id", name="uq_stock_receipt_product_variant", postgresql_nulls_not_distinct=True),
        CheckConstraint("expected_quantity > 0 AND scanned_quantity >= 0 AND scanned_quantity <= expected_quantity", name="ck_stock_receipt_quantities"),
        CheckConstraint("unit_cost >= 0", name="ck_stock_receipt_unit_cost"),
    )
    receipt_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("stock_receipts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    variant_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), index=True)
    expected_quantity: Mapped[int] = mapped_column(Integer)
    scanned_quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    product: Mapped[Product] = relationship()
    variant: Mapped[ProductVariant | None] = relationship()
    receipt: Mapped[StockReceipt] = relationship(back_populates="items")
