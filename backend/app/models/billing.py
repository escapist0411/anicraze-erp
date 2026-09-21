from decimal import Decimal
from enum import StrEnum
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, EntityBase, TimestampMixin, UUIDMixin

class PaymentStatus(StrEnum): PENDING="PENDING"; PAID="PAID"; PARTIAL="PARTIAL"; CANCELLED="CANCELLED"; REFUNDED="REFUNDED"
class InvoiceStatus(StrEnum): DRAFT="DRAFT"; COMPLETED="COMPLETED"; CANCELLED="CANCELLED"; RETURNED="RETURNED"
class PaymentMethodCode(StrEnum): CASH="CASH"; UPI="UPI"; CARD="CARD"; NET_BANKING="NET_BANKING"; WALLET="WALLET"; GIFT_CARD="GIFT_CARD"; SPLIT_PAYMENT="SPLIT_PAYMENT"
class ReturnStatus(StrEnum): COMPLETED="COMPLETED"; CANCELLED="CANCELLED"
class RefundStatus(StrEnum): COMPLETED="COMPLETED"; FAILED="FAILED"
class RegisterStatus(StrEnum): OPEN="OPEN"; CLOSED="CLOSED"

class Customer(EntityBase):
    __tablename__="customers"; name:Mapped[str]=mapped_column(String(180),index=True); phone:Mapped[str|None]=mapped_column(String(30),index=True); email:Mapped[str|None]=mapped_column(String(320),index=True); gstin:Mapped[str|None]=mapped_column(String(15),index=True); state_code:Mapped[str]=mapped_column(String(2),default="27"); address:Mapped[str|None]=mapped_column(Text)
class PaymentMethod(EntityBase):
    __tablename__="payment_methods"; code:Mapped[PaymentMethodCode]=mapped_column(Enum(PaymentMethodCode,native_enum=False,length=30),unique=True,index=True); name:Mapped[str]=mapped_column(String(80)); is_active:Mapped[bool]=mapped_column(Boolean,default=True)
class InvoiceSequence(UUIDMixin,Base):
    __tablename__="invoice_sequence"; key:Mapped[str]=mapped_column(String(40),unique=True); current_value:Mapped[int]=mapped_column(Integer,default=0)
class Invoice(EntityBase):
    __tablename__="invoices"; __table_args__=(CheckConstraint("subtotal >= 0 AND discount >= 0 AND grand_total >= 0",name="ck_invoice_nonnegative"),)
    invoice_number:Mapped[str]=mapped_column(String(40),unique=True,index=True); idempotency_key:Mapped[str]=mapped_column(String(100),unique=True,index=True); customer_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("customers.id",ondelete="RESTRICT"),index=True); store_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("stores.id",ondelete="RESTRICT"),index=True); employee_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"),index=True); payment_id:Mapped[UUID|None]=mapped_column(PGUUID(as_uuid=True),nullable=True,index=True)
    subtotal:Mapped[Decimal]=mapped_column(Numeric(16,2)); discount:Mapped[Decimal]=mapped_column(Numeric(16,2),default=0); taxable_amount:Mapped[Decimal]=mapped_column(Numeric(16,2)); cgst:Mapped[Decimal]=mapped_column(Numeric(16,2),default=0); sgst:Mapped[Decimal]=mapped_column(Numeric(16,2),default=0); igst:Mapped[Decimal]=mapped_column(Numeric(16,2),default=0); gst_total:Mapped[Decimal]=mapped_column(Numeric(16,2),default=0); grand_total:Mapped[Decimal]=mapped_column(Numeric(16,2)); round_off:Mapped[Decimal]=mapped_column(Numeric(8,2),default=0); payment_status:Mapped[PaymentStatus]=mapped_column(Enum(PaymentStatus,native_enum=False,length=20),index=True); invoice_status:Mapped[InvoiceStatus]=mapped_column(Enum(InvoiceStatus,native_enum=False,length=20),index=True); notes:Mapped[str|None]=mapped_column(Text); pdf_path:Mapped[str|None]=mapped_column(String(500)); items:Mapped[list["InvoiceItem"]]=relationship(back_populates="invoice",lazy="selectin",cascade="all, delete-orphan"); payments:Mapped[list["Payment"]]=relationship(back_populates="invoice",lazy="selectin")
    customer:Mapped["Customer"]=relationship(foreign_keys=[customer_id],lazy="selectin")
    store=relationship("Store",foreign_keys=[store_id],lazy="selectin")
    employee=relationship("User",foreign_keys=[employee_id],lazy="selectin")
    @property
    def store_name(self): return self.store.name
    @property
    def store_address(self): return self.store.address
    @property
    def employee_name(self): return self.employee.full_name
    @property
    def employee_code(self): return self.employee.employee_code
    @property
    def customer_name(self): return self.customer.name
    @property
    def customer_address(self): return self.customer.address
    @property
    def payment_methods(self): return [payment.method.name for payment in self.payments]
class InvoiceItem(UUIDMixin,TimestampMixin,Base):
    __tablename__="invoice_items"; __table_args__=(CheckConstraint("quantity > 0 AND unit_price >= 0",name="ck_invoice_item_valid"),)
    invoice_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("invoices.id",ondelete="CASCADE"),index=True); inventory_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("inventory.id",ondelete="RESTRICT"),index=True); product_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("products.id",ondelete="RESTRICT"),index=True); variant_id:Mapped[UUID|None]=mapped_column(PGUUID(as_uuid=True),ForeignKey("product_variants.id",ondelete="RESTRICT")); sku:Mapped[str]=mapped_column(String(64)); product_name:Mapped[str]=mapped_column(String(220)); hsn_code:Mapped[str|None]=mapped_column(String(12)); quantity:Mapped[int]=mapped_column(Integer); unit_price:Mapped[Decimal]=mapped_column(Numeric(14,2)); discount:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0); gst_rate:Mapped[Decimal]=mapped_column(Numeric(5,2)); taxable_amount:Mapped[Decimal]=mapped_column(Numeric(16,2)); tax_amount:Mapped[Decimal]=mapped_column(Numeric(16,2)); line_total:Mapped[Decimal]=mapped_column(Numeric(16,2)); invoice:Mapped[Invoice]=relationship(back_populates="items")
class Payment(EntityBase):
    __tablename__="payments"; __table_args__=(CheckConstraint("amount > 0",name="ck_payment_positive"),)
    invoice_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("invoices.id",ondelete="RESTRICT"),index=True); payment_method_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("payment_methods.id",ondelete="RESTRICT"),index=True); amount:Mapped[Decimal]=mapped_column(Numeric(16,2)); tendered_amount:Mapped[Decimal|None]=mapped_column(Numeric(16,2)); change_amount:Mapped[Decimal]=mapped_column(Numeric(16,2),default=0); transaction_reference:Mapped[str|None]=mapped_column(String(120),index=True); status:Mapped[PaymentStatus]=mapped_column(Enum(PaymentStatus,native_enum=False,length=20),index=True); invoice:Mapped[Invoice]=relationship(back_populates="payments"); method:Mapped[PaymentMethod]=relationship()
class InvoiceDiscount(UUIDMixin,TimestampMixin,Base):
    __tablename__="invoice_discounts"; invoice_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("invoices.id",ondelete="CASCADE"),index=True); description:Mapped[str]=mapped_column(String(160)); amount:Mapped[Decimal]=mapped_column(Numeric(16,2))
class InvoiceTax(UUIDMixin,TimestampMixin,Base):
    __tablename__="invoice_taxes"; invoice_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("invoices.id",ondelete="CASCADE"),index=True); gst_rate:Mapped[Decimal]=mapped_column(Numeric(5,2)); taxable_amount:Mapped[Decimal]=mapped_column(Numeric(16,2)); cgst:Mapped[Decimal]=mapped_column(Numeric(16,2)); sgst:Mapped[Decimal]=mapped_column(Numeric(16,2)); igst:Mapped[Decimal]=mapped_column(Numeric(16,2)); total_tax:Mapped[Decimal]=mapped_column(Numeric(16,2))
class Return(EntityBase):
    __tablename__="returns"; return_number:Mapped[str]=mapped_column(String(50),unique=True,index=True); invoice_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("invoices.id",ondelete="RESTRICT"),index=True); reason:Mapped[str]=mapped_column(String(255)); total_amount:Mapped[Decimal]=mapped_column(Numeric(16,2)); status:Mapped[ReturnStatus]=mapped_column(Enum(ReturnStatus,native_enum=False,length=20)); items:Mapped[list["ReturnItem"]]=relationship(lazy="selectin",cascade="all, delete-orphan")
class ReturnItem(UUIDMixin,TimestampMixin,Base):
    __tablename__="return_items"; return_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("returns.id",ondelete="CASCADE"),index=True); invoice_item_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("invoice_items.id",ondelete="RESTRICT"),index=True); quantity:Mapped[int]=mapped_column(Integer); amount:Mapped[Decimal]=mapped_column(Numeric(16,2))
class Refund(EntityBase):
    __tablename__="refunds"; refund_number:Mapped[str]=mapped_column(String(50),unique=True,index=True); return_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("returns.id",ondelete="RESTRICT"),index=True); payment_method_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("payment_methods.id",ondelete="RESTRICT")); amount:Mapped[Decimal]=mapped_column(Numeric(16,2)); transaction_reference:Mapped[str|None]=mapped_column(String(120)); status:Mapped[RefundStatus]=mapped_column(Enum(RefundStatus,native_enum=False,length=20))
class CashRegister(EntityBase):
    __tablename__="cash_register"; store_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("stores.id",ondelete="RESTRICT"),index=True); employee_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"),index=True); opening_balance:Mapped[Decimal]=mapped_column(Numeric(16,2)); cash_sales:Mapped[Decimal]=mapped_column(Numeric(16,2),default=0); cash_refunds:Mapped[Decimal]=mapped_column(Numeric(16,2),default=0); closing_balance:Mapped[Decimal|None]=mapped_column(Numeric(16,2)); status:Mapped[RegisterStatus]=mapped_column(Enum(RegisterStatus,native_enum=False,length=20),index=True)
