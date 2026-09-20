from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions.domain import ConflictError, NotFoundError
from app.models.auth import AuditLog, User
from app.models.payables import PaymentReminder, PayableStatus, PurchasePayable, PurchasePaymentTransaction, ReminderStatus
from app.models.procurement import Supplier
from app.repositories.management import ManagementRepository
from app.schemas.payables import PayableCreate, PayableResponse, PayableSummary, PayableUpdate, PaymentCreate, PaymentResponse, ReminderResponse
from app.utils.time import utc_now


class PayableService:
    def __init__(self, session: AsyncSession, actor: User, ip: str | None = None, user_agent: str | None = None):
        self.session, self.actor, self.audit_repo = session, actor, ManagementRepository(session)
        self.ip, self.user_agent = ip, user_agent

    async def audit(self, action: str, entity_id: UUID, metadata: dict | None = None) -> None:
        await self.audit_repo.audit(AuditLog(actor_user_id=self.actor.id, action=action, entity_type="purchase_payable", entity_id=entity_id, metadata_json=metadata, ip_address=self.ip, user_agent=self.user_agent, created_at=utc_now()))

    def query(self):
        return select(PurchasePayable).options(selectinload(PurchasePayable.payments), selectinload(PurchasePayable.reminders), selectinload(PurchasePayable.supplier)).where(PurchasePayable.deleted_at.is_(None))

    async def get(self, payable_id: UUID, lock: bool = False) -> PurchasePayable:
        query = self.query().where(PurchasePayable.id == payable_id)
        if lock:
            query = query.with_for_update()
        row = await self.session.scalar(query)
        if not row:
            raise NotFoundError("Purchase payable not found", "PURCHASE_PAYABLE_NOT_FOUND")
        return row

    @staticmethod
    def paid(row: PurchasePayable) -> Decimal:
        return sum((payment.amount for payment in row.payments if payment.deleted_at is None), Decimal("0"))

    def status(self, row: PurchasePayable, paid: Decimal | None = None) -> PayableStatus:
        paid = self.paid(row) if paid is None else paid
        if paid >= row.total_amount:
            return PayableStatus.PAID
        if row.due_date and row.due_date < date.today():
            return PayableStatus.OVERDUE
        return PayableStatus.PARTIALLY_PAID if paid > 0 else PayableStatus.UNPAID

    def response(self, row: PurchasePayable) -> PayableResponse:
        paid = self.paid(row); row.status = self.status(row, paid)
        scheduled = sorted((r for r in row.reminders if r.status == ReminderStatus.SCHEDULED and r.deleted_at is None), key=lambda r: r.remind_at)
        return PayableResponse(id=row.id, supplier_id=row.supplier_id, supplier_name=row.supplier_name_snapshot, stock_receipt_id=row.stock_receipt_id, reference_number=row.reference_number, invoice_number=row.invoice_number, invoice_date=row.invoice_date, total_amount=row.total_amount, amount_paid=paid, pending_amount=row.total_amount-paid, status=row.status, due_date=row.due_date, next_reminder_at=scheduled[0].remind_at if scheduled else None, reminder_enabled=bool(scheduled), notes=row.notes, payments=[PaymentResponse.model_validate(x) for x in sorted(row.payments, key=lambda x:x.created_at, reverse=True) if x.deleted_at is None], reminders=[ReminderResponse.model_validate(x) for x in sorted(row.reminders, key=lambda x:x.remind_at, reverse=True) if x.deleted_at is None], created_at=row.created_at, updated_at=row.updated_at)

    async def list(self, status: PayableStatus | None = None) -> list[PayableResponse]:
        rows=list((await self.session.scalars(self.query().order_by(PurchasePayable.created_at.desc()).limit(500))).unique().all())
        result=[self.response(row) for row in rows]
        return [row for row in result if row.status == status] if status else result

    async def create(self, data: PayableCreate) -> PayableResponse:
        supplier=await self.session.scalar(select(Supplier).where(Supplier.id==data.supplier_id, Supplier.deleted_at.is_(None)))
        if not supplier: raise NotFoundError("Supplier not found", "SUPPLIER_NOT_FOUND")
        if data.initially_paid > data.total_amount: raise ConflictError("Initial payment cannot exceed purchase total", "PAYABLE_PAYMENT_EXCEEDS_TOTAL")
        if data.initially_paid and not data.initial_payment_method: raise ConflictError("Payment method is required", "PAYABLE_PAYMENT_METHOD_REQUIRED")
        if data.stock_receipt_id and await self.session.scalar(select(PurchasePayable.id).where(PurchasePayable.stock_receipt_id==data.stock_receipt_id)): raise ConflictError("This receipt already has a payable", "PAYABLE_RECEIPT_EXISTS")
        row=PurchasePayable(supplier_id=supplier.id, stock_receipt_id=data.stock_receipt_id, reference_number=f"PAY-{date.today().year}-{uuid4().hex[:8].upper()}", invoice_number=data.invoice_number, invoice_date=data.invoice_date, supplier_name_snapshot=supplier.display_name, total_amount=data.total_amount, status=PayableStatus.UNPAID, due_date=data.due_date, reminder_enabled=bool(data.remind_at), notes=data.notes, payments=[], reminders=[], created_by_id=self.actor.id, updated_by_id=self.actor.id)
        self.session.add(row); await self.session.flush()
        if data.initially_paid:
            row.payments.append(PurchasePaymentTransaction(payable_id=row.id, amount=data.initially_paid, payment_method=data.initial_payment_method, payment_date=data.invoice_date, reference_number="Initial payment", created_by_id=self.actor.id, updated_by_id=self.actor.id))
        if data.remind_at:
            row.reminders.append(PaymentReminder(payable_id=row.id, remind_at=data.remind_at, status=ReminderStatus.SCHEDULED, created_by_id=self.actor.id, updated_by_id=self.actor.id))
        await self.session.flush(); await self.audit("PURCHASE_PAYABLE_CREATED", row.id, {"total": str(row.total_amount), "initially_paid": str(data.initially_paid)})
        return self.response(await self.get(row.id))

    async def record_payment(self, payable_id: UUID, data: PaymentCreate) -> PayableResponse:
        row=await self.get(payable_id, True); paid=self.paid(row); pending=row.total_amount-paid
        if row.status==PayableStatus.PAID or data.amount>pending: raise ConflictError("Payment exceeds the pending amount", "PAYABLE_PAYMENT_EXCEEDS_PENDING")
        tx=PurchasePaymentTransaction(payable_id=row.id, **data.model_dump(), created_by_id=self.actor.id, updated_by_id=self.actor.id); row.payments.append(tx); await self.session.flush()
        new_paid=paid+data.amount; row.status=self.status(row,new_paid);row.updated_by_id=self.actor.id
        if row.status==PayableStatus.PAID:
            for reminder in row.reminders:
                if reminder.status==ReminderStatus.SCHEDULED: reminder.status=ReminderStatus.CANCELLED
            row.reminder_enabled=False
        await self.audit("PURCHASE_PAYMENT_RECORDED",row.id,{"amount":str(data.amount),"pending_after":str(row.total_amount-new_paid),"method":data.payment_method.value});await self.session.flush()
        return self.response(await self.get(row.id))

    async def schedule_reminder(self, payable_id: UUID, remind_at: datetime) -> PayableResponse:
        row=await self.get(payable_id,True)
        if self.status(row)==PayableStatus.PAID: raise ConflictError("Paid purchases cannot be reminded", "PAYABLE_ALREADY_PAID")
        if remind_at <= datetime.now(timezone.utc): raise ConflictError("Reminder must be in the future", "PAYABLE_REMINDER_PAST")
        previous=next(iter(sorted((r for r in row.reminders if r.status in {ReminderStatus.SCHEDULED,ReminderStatus.TRIGGERED}),key=lambda r:r.remind_at,reverse=True)),None)
        if previous:
            previous.status=ReminderStatus.CANCELLED if previous.status==ReminderStatus.SCHEDULED else ReminderStatus.DISMISSED
            if previous.status==ReminderStatus.DISMISSED:previous.dismissed_at=datetime.now(timezone.utc)
        reminder=PaymentReminder(payable_id=row.id,remind_at=remind_at,status=ReminderStatus.SCHEDULED,snoozed_from_id=previous.id if previous else None,created_by_id=self.actor.id,updated_by_id=self.actor.id);row.reminders.append(reminder);row.reminder_enabled=True
        await self.audit("PAYMENT_REMINDER_SCHEDULED",row.id,{"remind_at":remind_at.isoformat()});await self.session.flush();return self.response(await self.get(row.id))

    async def dismiss_reminder(self,payable_id:UUID,reminder_id:UUID)->PayableResponse:
        row=await self.get(payable_id,True);reminder=next((x for x in row.reminders if x.id==reminder_id),None)
        if not reminder:raise NotFoundError("Payment reminder not found","PAYMENT_REMINDER_NOT_FOUND")
        if reminder.status not in {ReminderStatus.SCHEDULED,ReminderStatus.TRIGGERED}:raise ConflictError("Reminder is already closed","PAYMENT_REMINDER_CLOSED")
        reminder.status=ReminderStatus.DISMISSED;reminder.dismissed_at=datetime.now(timezone.utc);row.reminder_enabled=False
        await self.audit("PAYMENT_REMINDER_DISMISSED",row.id,{"reminder_id":str(reminder.id)});await self.session.flush();return self.response(row)

    async def update(self,payable_id:UUID,data:PayableUpdate)->PayableResponse:
        row=await self.get(payable_id,True);before={"due_date":str(row.due_date),"notes":row.notes}
        for key,value in data.model_dump(exclude_unset=True).items():setattr(row,key,value)
        row.updated_by_id=self.actor.id;await self.audit("PURCHASE_PAYABLE_UPDATED",row.id,{"before":before,"after":data.model_dump(exclude_unset=True,mode="json")});await self.session.flush();return self.response(row)

    async def reconcile_due_reminders(self)->int:
        now=datetime.now(timezone.utc);rows=list((await self.session.scalars(select(PaymentReminder).where(PaymentReminder.status==ReminderStatus.SCHEDULED,PaymentReminder.remind_at<=now).with_for_update(skip_locked=True))).all())
        for reminder in rows: reminder.status=ReminderStatus.TRIGGERED;reminder.triggered_at=now
        await self.session.flush();return len(rows)

    async def summary(self)->PayableSummary:
        rows=await self.list();today=date.today();week=today+timedelta(days=7)
        pending=lambda row:row.pending_amount
        open_rows=[row for row in rows if row.status!=PayableStatus.PAID]
        next_row=min((r for r in open_rows if r.due_date),key=lambda r:r.due_date,default=None)
        return PayableSummary(total_purchase_value=sum((r.total_amount for r in rows),Decimal("0")),total_paid=sum((r.amount_paid for r in rows),Decimal("0")),total_pending=sum((pending(r) for r in open_rows),Decimal("0")),overdue=sum((pending(r) for r in open_rows if r.due_date and r.due_date<today),Decimal("0")),due_this_week=sum((pending(r) for r in open_rows if r.due_date and today<=r.due_date<=week),Decimal("0")),next_payment=next_row)
