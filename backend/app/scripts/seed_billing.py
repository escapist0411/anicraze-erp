import asyncio
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from app.database.session import AsyncSessionFactory
from app.models.auth import User
from app.models.billing import CashRegister, Customer, Invoice, InvoiceSequence, PaymentMethod, PaymentMethodCode, RegisterStatus, Return
from app.models.inventory import Inventory, Store
from app.schemas.billing import BillingCreate, BillingItemInput, CustomerCreate, PaymentInput, ReturnCreate, ReturnItemInput
from app.services.billing import BillingService, ReturnService

async def seed():
    async with AsyncSessionFactory() as s:
        owner=await s.scalar(select(User).where(User.email=="owner@anicraze.com"))
        for key in ("invoice","return","refund"):
            if not await s.scalar(select(InvoiceSequence).where(InvoiceSequence.key==key)): s.add(InvoiceSequence(key=key,current_value=0))
        for code in PaymentMethodCode:
            if not await s.scalar(select(PaymentMethod).where(PaymentMethod.code==code)): s.add(PaymentMethod(code=code,name=code.value.replace("_"," ").title(),is_active=True,created_by_id=owner.id,updated_by_id=owner.id))
        await s.flush(); billing=BillingService(s,owner)
        customers=[]
        for name,phone,email in (("Aarav Sharma","9876500001","aarav@example.com"),("Meera Iyer","9876500002","meera@example.com"),("Walk-in Customer","9876500003",None)):
            x=await s.scalar(select(Customer).where(Customer.phone==phone))
            if not x: x=await billing.create_customer(CustomerCreate(name=name,phone=phone,email=email,address="Mumbai, Maharashtra"))
            customers.append(x)
        store=await s.scalar(select(Store).order_by(Store.code)); inventory=list((await s.scalars(select(Inventory).options(selectinload(Inventory.product),selectinload(Inventory.variant)).where(Inventory.store_id==store.id,Inventory.available_quantity>=3,Inventory.deleted_at.is_(None)).limit(3))).all())
        if not await s.scalar(select(CashRegister).where(CashRegister.store_id==store.id,CashRegister.status==RegisterStatus.OPEN)): s.add(CashRegister(store_id=store.id,employee_id=owner.id,opening_balance=Decimal("5000"),cash_sales=0,cash_refunds=0,status=RegisterStatus.OPEN,created_by_id=owner.id,updated_by_id=owner.id))
        made=[]
        if int(await s.scalar(select(func.count()).select_from(Invoice)) or 0)==0:
            for idx,inv in enumerate(inventory):
                qty=2 if idx==0 else 1; total=Decimal("100")*qty
                made.append(await billing.create(BillingCreate(customer_id=customers[idx].id,store_id=store.id,items=[BillingItemInput(inventory_id=inv.id,quantity=qty,unit_price=Decimal("100"))],payments=[PaymentInput(method=PaymentMethodCode.CASH if idx==0 else PaymentMethodCode.UPI,amount=total,tendered_amount=total if idx==0 else None,transaction_reference=None if idx==0 else f"UPI-DEMO-{idx}")],notes="Demo POS invoice")))
        if made and not await s.scalar(select(Return)):
            await ReturnService(s,owner).create_return(ReturnCreate(invoice_id=made[0].id,reason="Demo partial return",items=[ReturnItemInput(invoice_item_id=made[0].items[0].id,quantity=1)],refund_method=PaymentMethodCode.CASH))
        await s.commit()
if __name__=="__main__": asyncio.run(seed())
