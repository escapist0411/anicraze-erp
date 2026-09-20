from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.domain import AuthorizationError
from app.models.auth import AuditLog, User
from app.models.billing import Invoice, InvoiceItem, InvoiceStatus, Payment, PaymentMethod, PaymentStatus, Refund, Return, ReturnItem, ReturnStatus
from app.models.catalog import Anime, Category, Product
from app.models.crm import Channel, CustomerCommunication, CustomerProfile, LoyaltyAccount, LoyaltyTransaction, LoyaltyType, MembershipStatus, CustomerMembership
from app.models.hr import Attendance, AttendanceStatus, Employee, EmploymentStatus, PayrollRun, PayrollStatus
from app.models.inventory import Inventory, InventoryAlert, InventoryLedger, Store, StockTransfer, StockTransferItem, TransferStatus
from app.models.procurement import PurchaseOrder, SupplierInvoice
from app.models.reports import Expense, ExpenseStatus
from app.schemas.reports import ReportFilterRequest

ZERO = Decimal("0.00")


def resolve_date_range(filters: ReportFilterRequest) -> tuple[datetime, datetime]:
    tz = ZoneInfo(filters.timezone)
    today = datetime.now(tz).date(); preset = (filters.preset or "THIS_MONTH").upper()
    if filters.date_from or filters.date_to:
        start = filters.date_from or filters.date_to or today; end = filters.date_to or filters.date_from or today
    elif preset == "TODAY": start = end = today
    elif preset == "YESTERDAY": start = end = today - timedelta(days=1)
    elif preset in {"THIS_WEEK", "LAST_WEEK"}:
        start = today - timedelta(days=today.weekday()) - (timedelta(days=7) if preset == "LAST_WEEK" else timedelta()); end = start + timedelta(days=6)
    elif preset in {"THIS_YEAR", "LAST_YEAR"}:
        year = today.year - (preset == "LAST_YEAR"); start = date(year, 1, 1); end = date(year, 12, 31)
    elif preset in {"THIS_QUARTER", "LAST_QUARTER"}:
        q = (today.month - 1) // 3
        year = today.year
        if preset == "LAST_QUARTER": q -= 1
        if q < 0: q = 3; year -= 1
        start = date(year, q * 3 + 1, 1); m = q * 3 + 3; end = date(year, m, monthrange(year, m)[1])
    else:
        year, month = today.year, today.month
        if preset == "LAST_MONTH": month -= 1; year -= month == 0; month = 12 if month == 0 else month
        start = date(year, month, 1); end = date(year, month, monthrange(year, month)[1])
    return datetime.combine(start, time.min, tz).astimezone(timezone.utc), datetime.combine(end + timedelta(days=1), time.min, tz).astimezone(timezone.utc)


def scoped_store(actor: User, requested: UUID | None) -> UUID | None:
    roles = {r.code for r in actor.roles}
    if roles & {"OWNER", "ADMIN"}: return requested
    if actor.assigned_store_id is None: raise AuthorizationError("No store is assigned to this user", "REPORT_STORE_SCOPE_REQUIRED")
    if requested and requested != actor.assigned_store_id: raise AuthorizationError("Cross-store reporting is not allowed", "REPORT_STORE_SCOPE_DENIED")
    return actor.assigned_store_id


class ReportingService:
    def __init__(self, session: AsyncSession, actor: User): self.session = session; self.actor = actor
    async def audit(self, action: str, report_type: str, filters: dict | None = None):
        self.session.add(AuditLog(actor_user_id=self.actor.id, target_user_id=None, action=action, entity_type="REPORT", entity_id=None, metadata_json={"report_type": report_type, "filters": filters or {}}, ip_address=None, user_agent=None, created_at=datetime.now(timezone.utc)))

    async def summary(self, filters: ReportFilterRequest) -> dict:
        start, end = resolve_date_range(filters); store_id = scoped_store(self.actor, filters.store_id)
        invoice_where = [Invoice.created_at >= start, Invoice.created_at < end, Invoice.invoice_status.in_([InvoiceStatus.COMPLETED,InvoiceStatus.RETURNED]), Invoice.deleted_at.is_(None)]
        if store_id: invoice_where.append(Invoice.store_id == store_id)
        gross_sales,discounts,net_billed,orders,customers = (await self.session.execute(select(func.coalesce(func.sum(Invoice.subtotal),0),func.coalesce(func.sum(Invoice.discount),0),func.coalesce(func.sum(Invoice.grand_total),0),func.count(Invoice.id),func.count(func.distinct(Invoice.customer_id))).where(*invoice_where))).one()
        units=await self.session.scalar(select(func.coalesce(func.sum(InvoiceItem.quantity),0)).join(Invoice).where(*invoice_where)) or 0
        cost_q = select(func.coalesce(func.sum(InvoiceItem.quantity * Inventory.average_cost), 0)).join(Invoice, Invoice.id == InvoiceItem.invoice_id).join(Inventory, Inventory.id == InvoiceItem.inventory_id).where(*invoice_where)
        sold_cost = Decimal(await self.session.scalar(cost_q) or ZERO)
        return_where=[Return.created_at>=start,Return.created_at<end,Return.status==ReturnStatus.COMPLETED]
        if store_id:return_where.append(Invoice.store_id==store_id)
        returned_total,returned_cost,returned_taxable = (await self.session.execute(select(func.coalesce(func.sum(ReturnItem.amount),0),func.coalesce(func.sum(ReturnItem.quantity*Inventory.average_cost),0),func.coalesce(func.sum(ReturnItem.amount*Invoice.taxable_amount/func.nullif(Invoice.grand_total,0)),0)).join(Return,Return.id==ReturnItem.return_id).join(InvoiceItem,InvoiceItem.id==ReturnItem.invoice_item_id).join(Inventory,Inventory.id==InvoiceItem.inventory_id).join(Invoice,Invoice.id==Return.invoice_id).where(*return_where))).one()
        net_sales=Decimal(net_billed)-Decimal(returned_total);cost=max(ZERO,sold_cost-Decimal(returned_cost))
        exp_where = [Expense.expense_date >= start.date(), Expense.expense_date < end.date(), Expense.status == ExpenseStatus.APPROVED, Expense.deleted_at.is_(None)]
        if store_id: exp_where.append(Expense.store_id == store_id)
        expenses = await self.session.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(*exp_where)) or ZERO
        refunds=Decimal(returned_total);gross_profit=net_sales-cost;operating=gross_profit-Decimal(expenses)
        return {"date_range":{"from":start,"to":end},"store_id":store_id,"gross_sales":Decimal(gross_sales),"discounts":Decimal(discounts),"returns":refunds,"refunds":refunds,"net_sales":net_sales,"revenue":net_sales,"orders":int(orders),"products_sold":max(0,int(units)),"customers":int(customers),"cost_of_goods_sold":cost,"gross_profit":gross_profit,"expenses":Decimal(expenses),"estimated_net_operating_profit":operating,"net_profit":operating,"average_order_value":net_sales/orders if orders else ZERO}

    async def inventory_summary(self, filters: ReportFilterRequest) -> dict:
        store_id = scoped_store(self.actor, filters.store_id); where = [Inventory.deleted_at.is_(None)]
        if store_id: where.append(Inventory.store_id == store_id)
        if filters.warehouse_id: where.append(Inventory.warehouse_id == filters.warehouse_id)
        value, units, low, out, damaged,godown,shops = (await self.session.execute(select(func.coalesce(func.sum(Inventory.inventory_value),0),func.coalesce(func.sum(Inventory.available_quantity),0),func.count(Inventory.id).filter(and_(Inventory.available_quantity<=Inventory.reorder_level,Inventory.available_quantity>0)),func.count(Inventory.id).filter(Inventory.available_quantity==0),func.coalesce(func.sum(Inventory.damaged_quantity),0),func.coalesce(func.sum(Inventory.available_quantity).filter(Inventory.warehouse_id.is_not(None)),0),func.coalesce(func.sum(Inventory.available_quantity).filter(Inventory.store_id.is_not(None)),0)).where(*where))).one()
        in_transit=await self.session.scalar(select(func.coalesce(func.sum(StockTransferItem.quantity),0)).join(StockTransfer).where(StockTransfer.status.in_([TransferStatus.DISPATCHED,TransferStatus.RECEIVING]))) or 0
        return {"inventory_value":Decimal(value),"available_units":int(units),"low_stock_count":int(low),"out_of_stock_count":int(out),"damaged_units":int(damaged),"godown_units":int(godown),"shop_units":int(shops),"in_transit_units":int(in_transit or 0)}

    async def sales_trend(self, filters: ReportFilterRequest) -> list[dict]:
        start, end = resolve_date_range(filters); store_id = scoped_store(self.actor, filters.store_id); where = [Invoice.created_at >= start, Invoice.created_at < end, Invoice.invoice_status.in_([InvoiceStatus.COMPLETED,InvoiceStatus.RETURNED]), Invoice.deleted_at.is_(None)]
        if store_id: where.append(Invoice.store_id == store_id)
        rows = (await self.session.execute(select(func.date(Invoice.created_at), func.sum(Invoice.grand_total), func.count(Invoice.id)).where(*where).group_by(func.date(Invoice.created_at)).order_by(func.date(Invoice.created_at)))).all()
        return [{"date": d, "revenue": Decimal(v), "orders": n} for d, v, n in rows]

    async def top_products(self, filters: ReportFilterRequest, limit=10) -> list[dict]:
        start, end = resolve_date_range(filters); store_id = scoped_store(self.actor, filters.store_id); where = [Invoice.created_at >= start, Invoice.created_at < end, Invoice.invoice_status.in_([InvoiceStatus.COMPLETED,InvoiceStatus.RETURNED])]
        if store_id: where.append(Invoice.store_id == store_id)
        rows=(await self.session.execute(select(InvoiceItem.product_id,InvoiceItem.product_name,InvoiceItem.sku,func.sum(InvoiceItem.quantity),func.sum(InvoiceItem.taxable_amount),func.sum(InvoiceItem.quantity*Inventory.average_cost)).join(Invoice).join(Inventory,Inventory.id==InvoiceItem.inventory_id).where(*where).group_by(InvoiceItem.product_id,InvoiceItem.product_name,InvoiceItem.sku).order_by(func.sum(InvoiceItem.quantity).desc()).limit(limit))).all()
        return [{"product_id":p,"product_name":n,"sku":sku,"quantity":int(q),"net_sales":Decimal(v),"revenue":Decimal(v),"gross_profit":Decimal(v)-Decimal(c)} for p,n,sku,q,v,c in rows]

    async def store_performance(self, filters: ReportFilterRequest) -> list[dict]:
        start, end = resolve_date_range(filters); store_id = scoped_store(self.actor, filters.store_id)
        where = [Invoice.created_at >= start, Invoice.created_at < end, Invoice.invoice_status.in_([InvoiceStatus.COMPLETED, InvoiceStatus.RETURNED]), Invoice.deleted_at.is_(None)]
        if store_id: where.append(Invoice.store_id == store_id)
        rows = (await self.session.execute(
            select(Store.id, Store.name, func.coalesce(func.sum(Invoice.taxable_amount), 0), func.count(Invoice.id))
            .join(Invoice, Invoice.store_id == Store.id)
            .where(*where).group_by(Store.id, Store.name).order_by(func.sum(Invoice.taxable_amount).desc())
        )).all()
        return_where=[Return.created_at>=start,Return.created_at<end,Return.status==ReturnStatus.COMPLETED]
        if store_id:return_where.append(Invoice.store_id==store_id)
        returned=dict((await self.session.execute(select(Invoice.store_id,func.coalesce(func.sum(ReturnItem.amount*Invoice.taxable_amount/func.nullif(Invoice.grand_total,0)),0)).join(Return,Return.id==ReturnItem.return_id).join(Invoice,Invoice.id==Return.invoice_id).where(*return_where).group_by(Invoice.store_id))).all())
        result=[]
        for sid,name,sales,orders in rows:
            net=Decimal(sales)-Decimal(returned.get(sid,ZERO));result.append({"store_id":sid,"store_name":name,"net_sales":net,"revenue":net,"orders":int(orders),"average_order_value":net/orders if orders else ZERO})
        return result

    async def payment_summary(self, filters: ReportFilterRequest) -> list[dict]:
        start, end = resolve_date_range(filters); store_id = scoped_store(self.actor, filters.store_id)
        where = [Payment.created_at >= start, Payment.created_at < end, Payment.deleted_at.is_(None), Payment.status.in_([PaymentStatus.PAID, PaymentStatus.PARTIAL])]
        if store_id: where.append(Invoice.store_id == store_id)
        rows = (await self.session.execute(select(PaymentMethod.name, func.sum(Payment.amount), func.count(Payment.id)).join(PaymentMethod, PaymentMethod.id == Payment.payment_method_id).join(Invoice, Invoice.id == Payment.invoice_id).where(*where).group_by(PaymentMethod.name).order_by(func.sum(Payment.amount).desc()))).all()
        total = sum((Decimal(amount) for _, amount, _ in rows), ZERO)
        return [{"payment_method":method,"amount":Decimal(amount),"transactions":int(count),"percentage":(Decimal(amount)*100/total).quantize(Decimal("0.01")) if total else ZERO} for method,amount,count in rows]

    async def owner_dashboard(self, filters: ReportFilterRequest) -> dict:
        financial = await self.summary(filters); inventory = await self.inventory_summary(filters); trend = await self.sales_trend(filters)
        store_id = scoped_store(self.actor, filters.store_id); emp_where=[Employee.employment_status == EmploymentStatus.ACTIVE, Employee.deleted_at.is_(None)]
        if store_id: emp_where.append(Employee.store_id == store_id)
        active_employees = await self.session.scalar(select(func.count(Employee.id)).where(*emp_where)) or 0
        today = datetime.now(ZoneInfo(filters.timezone)).date(); attendance_total = await self.session.scalar(select(func.count(Attendance.id)).where(Attendance.attendance_date == today)) or 0; present = await self.session.scalar(select(func.count(Attendance.id)).where(Attendance.attendance_date == today, Attendance.status.in_([AttendanceStatus.PRESENT,AttendanceStatus.LATE,AttendanceStatus.HALF_DAY]))) or 0
        from app.services.notifications import NotificationService
        notification_rows=await NotificationService(self.session,self.actor).list(limit=10)
        alerts=[{"severity":x.severity.value,"code":x.dedupe_key,"message":x.message,"category":x.category.value,"action_path":x.action_path} for x in notification_rows]
        insights=[]
        if financial["orders"] == 0: insights.append({"severity":"WARNING","code":"NO_SALES","message":"No completed sales were recorded for the selected period."})
        if financial["estimated_net_operating_profit"] < 0: insights.append({"severity":"CRITICAL","code":"OPERATING_LOSS","message":"Estimated operating profit is negative for the selected period."})
        if inventory["low_stock_count"] or inventory["out_of_stock_count"]: insights.append({"severity":"WARNING","code":"REPLENISHMENT_REQUIRED","message":"Replenishment is required for low or out-of-stock products."})
        if not insights: insights.append({"severity":"SUCCESS","code":"OPERATIONS_STABLE","message":"No critical financial or inventory exception was detected for this period."})
        return {"kpis":financial,"inventory_summary":inventory,"sales_trend":trend,"top_selling_products":await self.top_products(filters),"store_performance":await self.store_performance(filters),"payment_summary":await self.payment_summary(filters),"active_employees":active_employees,"attendance_percentage":(Decimal(present)*100/attendance_total).quantize(Decimal("0.01")) if attendance_total else ZERO,"alerts":alerts,"business_insights":insights,"definitions":{"net_sales":"Taxable sales excluding GST, less the taxable portion of completed returns.","gross_profit":"Net sales less estimated cost of goods sold.","estimated_net_operating_profit":"Gross profit less approved operating expenses; excludes payroll, depreciation, interest and income tax unless recorded as expenses.","inventory_valuation":"Current inventory quantities multiplied by current average cost."}}

    async def report(self, domain: str, report: str, filters: ReportFilterRequest) -> dict:
        await self.audit("REPORT_VIEWED", f"{domain}.{report}", filters.model_dump(mode="json"))
        if domain == "inventory": data = await self.inventory_summary(filters)
        elif domain == "payments": data = {"methods": await self.payment_summary(filters), **(await self.summary(filters))}
        elif domain in {"sales","finance","gst","returns"}: data = await self.summary(filters)
        elif domain == "employees":
            data = (await self.owner_dashboard(filters)); data = {k:data[k] for k in ("active_employees","attendance_percentage")}
        else: data = await self.summary(filters)
        return {"report_type":f"{domain}_{report}", "filters":filters.model_dump(mode="json"), "summary":data, "rows":await self.sales_trend(filters) if domain in {"sales","stores"} else []}
