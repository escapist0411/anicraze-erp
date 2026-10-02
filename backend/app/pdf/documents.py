"""Typed document presenters. Inputs are already authorized by API/services.

No queries, financial calculations, or mutations belong in this module.
"""
from datetime import timedelta
from decimal import Decimal
from sqlalchemy import inspect as sa_inspect

from app.config.business import BUSINESS_PHONE_DISPLAY
from app.pdf.components import Document, p
from app.pdf.formatters import format_currency as cash, format_date, format_datetime, format_number, format_percentage

LABELS = {
    "gross_sales": "Gross Sales", "discounts": "Discounts", "net_sales": "Net Sales",
    "returns": "Returns", "returns_refunds": "Returns / Refunds", "net_revenue": "Net Revenue",
    "cogs": "COGS", "cost_of_goods_sold": "Cost of Goods Sold", "gross_profit": "Gross Profit",
    "gross_margin_percentage": "Gross Margin", "expenses": "Operating Expenses",
    "estimated_net_operating_profit": "Estimated Operating Profit", "orders": "Bills",
    "average_order_value": "Average Bill", "inventory_value": "Inventory Value",
    "available_units": "Total Units", "low_stock_count": "Low Stock", "out_of_stock_count": "Out of Stock",
    "damaged_units": "Damaged Units", "godown_units": "Warehouse Units", "shop_units": "Shop Units",
    "in_transit_units": "In Transit", "products_sold": "Units Sold", "products": "Products",
}
MONEY_FIELDS = {"gross_sales", "discounts", "net_sales", "returns", "returns_refunds", "net_revenue", "cogs", "cost_of_goods_sold", "gross_profit", "expenses", "estimated_net_operating_profit", "average_order_value", "inventory_value", "amount", "revenue"}


def display(key, value):
    if key in MONEY_FIELDS: return cash(value)
    if key in {"gross_margin_percentage", "percentage"}: return format_percentage(value)
    return format_number(value)


def entries(data, keys):
    return [(LABELS[k], display(k, data[k])) for k in keys if k in data and data[k] is not None]


def loaded(obj, name, default=None):
    """Never trigger async ORM lazy-loading while rendering a synchronous PDF."""
    state = sa_inspect(obj, raiseerr=False)
    if state is not None and name in state.unloaded:
        return default
    return getattr(obj, name, default)


def invoice_pdf(invoice, customer, store, employee, payment_methods=None, *, preview=False):
    doc = Document("INVOICE", internal=False, preview=preview)
    doc.header(store.name, [("Invoice #", invoice.invoice_number), ("Date", format_datetime(invoice.created_at)), ("Shop", store.name), ("Address", store.address or "Address not provided"), ("Contact", BUSINESS_PHONE_DISPLAY), ("Employee", f"{employee.full_name} ({employee.employee_code or '-'})")])
    doc.section("Bill to")
    doc.metadata([("Customer", customer.name), ("WhatsApp", getattr(customer, "phone", None) or "Not provided")])
    doc.section("Items")
    doc.table(["Item", "Qty", "Rate", "Amount"], [[f"{x.product_name}\n{x.sku}", format_number(x.quantity), cash(x.unit_price), cash(x.line_total)] for x in invoice.items], weights=[5.8, .8, 1.7, 1.7], numeric=(1, 2, 3))
    doc.section("Invoice total")
    doc.table(["Summary", "Amount"], [["Subtotal", cash(invoice.subtotal)], ["Discount", cash(invoice.discount)]], weights=[7, 3], numeric=(1,), total=["TOTAL", cash(invoice.grand_total)])
    doc.section("Payment")
    payments = loaded(invoice, "payments", []) or []
    labels = payment_methods or []
    rows = []
    for index, payment in enumerate(payments):
        method = loaded(payment, "method")
        label = method.name if method is not None else labels[index] if index < len(labels) else "Recorded payment"
        rows.append([label, cash(payment.amount)])
        code = getattr(method, "code", label)
        if str(code).upper() == "CASH" and payment.tendered_amount is not None:
            rows.extend([["Cash Received", cash(payment.tendered_amount)], ["Change Returned", cash(payment.change_amount)]])
    if rows:
        doc.table(["Payment Method", "Amount"], rows, weights=[7, 3], numeric=(1,))
    else:
        doc.note(", ".join(labels) or "Payment recorded")
    doc.note("Returns are subject to the ANICRAZE return policy. This is a computer-generated invoice.")
    return doc.build()


def transfer_pdf(transfer, source, target, products, *, variants=None, employee=None, preview=False):
    variants = variants or {}
    doc = Document("STOCK TRANSFER", preview=preview)
    doc.header(metadata=[("Transfer #", transfer.reference_number), ("Date", format_datetime(transfer.created_at))])
    doc.status(transfer.status.value)
    doc.metadata([("From", source.name if source else "Unknown location"), ("To", target.name if target else "Unknown location"), ("Transferred by", getattr(employee, "full_name", None)), ("Notes", getattr(transfer, "remarks", None))])
    doc.kpis([("Product Lines", format_number(len(transfer.items))), ("Total Units", format_number(sum(x.quantity for x in transfer.items)))], columns=2)
    doc.section("Transferred products")
    rows = []
    for item in transfer.items:
        product = products.get(item.product_id)
        variant = variants.get(getattr(item, "variant_id", None))
        rows.append([product.name if product else "Product unavailable", (variant.barcode or variant.sku) if variant else ((product.barcode or product.sku) if product else "-"), format_number(item.quantity)])
    doc.table(["Product", "Barcode", "Qty"], rows, weights=[5, 3.5, 1.5], numeric=(2,), total=["TOTAL", "", format_number(sum(x.quantity for x in transfer.items))])
    doc.note("Direct stock transfer. This document lists all products included in the transfer.")
    return doc.build()


def payslip_pdf(slip, employee, *, period=None, location=None, preview=False):
    doc = Document("EMPLOYEE PAYSLIP", preview=preview)
    metadata = [("Employee", employee.full_name), ("Employee ID", employee.employee_code)]
    if period:
        metadata.append(("Pay Period", f"{format_date(period.start_date)} - {format_date(period.end_date)}"))
    if location:
        metadata.append(("Location", location))
    doc.header(metadata=metadata)
    doc.kpis([("Gross Salary", cash(slip.gross_salary)), ("Deductions", cash(slip.deductions)), ("Net Payable", cash(slip.net_salary))])
    doc.section("Attendance & payable days")
    doc.table(["Description", "Days"], [["Payable Days", format_number(slip.payable_days)], ["Present Days", format_number(slip.present_days)], ["Paid Leave", format_number(slip.paid_leave_days)], ["Unpaid Leave", format_number(slip.unpaid_leave_days)]], weights=[7, 3], numeric=(1,))
    doc.section("Salary statement")
    doc.table(["Description", "Amount"], [["Gross Salary", cash(slip.gross_salary)], ["Deductions", cash(slip.deductions)]], weights=[7, 3], numeric=(1,), total=["NET PAYABLE", cash(slip.net_salary)])
    doc.note("Private payroll document. Authorized signatory: ____________________")
    return doc.build()


def report_metadata(payload):
    meta = payload.get("document_metadata", {})
    items = []
    period = meta.get("period")
    if period: items.append(("Period", period))
    elif payload.get("date_range") or payload.get("summary", {}).get("date_range"):
        dates = payload.get("date_range") or payload["summary"]["date_range"]
        items.append(("Period", f"{format_date(dates['from'])} - {format_date(dates['to'] - timedelta(days=1))}"))
    if meta.get("location"): items.append(("Location", meta["location"]))
    return items


def report_pdf(report_type, payload, *, preview=False):
    summary = payload.get("summary") or {}
    rows = payload.get("rows") or []
    is_pnl = report_type == "finance_shop-profit-loss"
    single_shop = bool(payload.get("filters", {}).get("store_id"))
    titles = {"inventory_summary": "INVENTORY SUMMARY", "sales_summary": "SALES REPORT", "finance_summary": "FINANCIAL SUMMARY", "payments_summary": "PAYMENT SUMMARY", "weekly_owner_report": "WEEKLY OWNER REPORT"}
    title = ("SHOP PROFIT & LOSS" if single_shop else "ALL SHOPS PROFIT & LOSS") if is_pnl else titles.get(report_type, "BUSINESS REPORT")
    doc = Document(title, wide=is_pnl and not single_shop, preview=preview)
    doc.header(metadata=report_metadata(payload))
    if is_pnl:
        keys = ["gross_sales", "discounts", "net_sales", "returns_refunds", "net_revenue", "cogs", "gross_profit", "gross_margin_percentage"]
        doc.kpis(entries(summary, keys if single_shop else ["net_revenue", "cogs", "gross_profit", "gross_margin_percentage"]), columns=3 if single_shop else 4)
        doc.section("Financial summary" if single_shop else "Shop performance comparison")
        if single_shop:
            doc.table(["Metric", "Value"], entries(summary, keys), weights=[7, 3], numeric=(1,))
        else:
            columns = ["gross_sales", "discounts", "net_sales", "returns_refunds", "net_revenue", "cogs", "gross_profit", "gross_margin_percentage"]
            doc.table(["Shop", *[LABELS[k] for k in columns]], [[r.get("shop", "-"), *[display(k, r.get(k)) for k in columns]] for r in rows], weights=[2.35, 1.25, 1, 1.25, 1.1, 1.25, 1.2, 1.25, .95], numeric=tuple(range(1, 9)), total=["TOTAL", *[display(k, summary.get(k)) for k in columns]] if rows else None, padding=4)
        if "expenses" in summary:
            doc.section("Operating expenses")
            doc.table(["Description", "Amount"], entries(summary, ["expenses", "estimated_net_operating_profit"]), weights=[7, 3], numeric=(1,))
    elif report_type.startswith("inventory"):
        keys = ["products", "available_units", "inventory_value", "low_stock_count", "out_of_stock_count"]
        doc.kpis(entries(summary, keys))
        doc.section("Inventory position")
        doc.table(["Metric", "Value"], entries(summary, ["godown_units", "shop_units", "in_transit_units", "damaged_units"]), weights=[7, 3], numeric=(1,))
        # Only render detail actually supplied by an authorized reporting service.
        if rows:
            doc.section("Product inventory")
            doc.table(["Product", "Barcode", "Available", "Reserved", "Damaged"], [[r.get("product_name", "-"), r.get("barcode", "-"), format_number(r.get("available_quantity")), format_number(r.get("reserved_quantity")), format_number(r.get("damaged_quantity"))] for r in rows], weights=[4, 3, 1, 1, 1], numeric=(2, 3, 4))
        doc.note("Stock reflects the selected location scope. Low stock and out of stock are reported as separate counts.")
    elif report_type.startswith("payments"):
        methods = summary.get("methods") or rows
        # Table totals are sums of supplied payment rows, not new accounting logic.
        total = sum((Decimal(str(r["amount"])) for r in methods), Decimal(0))
        count = sum(r["transactions"] for r in methods)
        doc.kpis([("Total Collected", cash(total)), ("Total Transactions", format_number(count))], columns=2)
        doc.section("Collection by payment method")
        doc.table(["Payment Method", "Transactions", "Amount", "Share"], [[r["payment_method"], format_number(r["transactions"]), cash(r["amount"]), format_percentage(r.get("percentage"))] for r in methods], weights=[4, 2, 2.5, 1.5], numeric=(1, 2, 3), total=["TOTAL", format_number(count), cash(total), ""] if methods else None)
    elif report_type == "weekly_owner_report":
        dashboard = payload.get("dashboard", {})
        kpis = dashboard.get("kpis", {})
        inventory = dashboard.get("inventory_summary", {})
        doc.section("Business summary")
        doc.kpis(entries(kpis, ["net_sales", "gross_profit", "orders", "average_order_value"]) + entries(inventory, ["inventory_value", "low_stock_count"]))
        doc.section("Sales overview")
        doc.table(["Metric", "Value"], entries(kpis, ["gross_sales", "discounts", "returns", "estimated_net_operating_profit"]), weights=[7, 3], numeric=(1,))
        doc.section("Shop performance")
        stores = dashboard.get("store_performance", [])
        doc.table(["Shop", "Net Sales", "Bills", "Average Bill"], [[r["store_name"], cash(r["net_sales"]), format_number(r["orders"]), cash(r["average_order_value"])] for r in stores], weights=[4, 2.5, 1, 2.5], numeric=(1, 2, 3))
        doc.section("Inventory health")
        doc.table(["Warehouse Units", "Low Stock", "Out of Stock"], [[format_number(inventory.get(k)) for k in ["godown_units", "low_stock_count", "out_of_stock_count"]]], numeric=(0, 1, 2))
        payment_rows = dashboard.get("payment_summary", [])
        if payment_rows:
            # Keep the method split as one compact line on the executive summary.
            breakdown = " · ".join(f"{r['payment_method']}: {cash(r['amount'])} ({format_number(r['transactions'])} bills)" for r in payment_rows)
            doc.story.append(p(f"PAYMENTS  |  {breakdown}", "small"))
        doc.note("Estimated operating profit reflects recorded operating expenses and is not an audited final profit.")
    elif report_type.startswith("sales") or report_type.startswith("stores"):
        doc.kpis(entries(summary, ["gross_sales", "discounts", "net_sales", "orders", "average_order_value", "returns"]))
        doc.section("Daily sales")
        doc.table(["Date", "Bills", "Billed Sales"], [[format_date(r["date"]), format_number(r["orders"]), cash(r["revenue"])] for r in rows], weights=[5, 2, 3], numeric=(1, 2), total=["TOTAL", format_number(sum(r["orders"] for r in rows)), cash(sum((Decimal(str(r["revenue"])) for r in rows), Decimal(0)))] if rows else None)
        doc.note("Daily billed sales use invoice totals. Summary net sales include completed returns, as calculated by the reporting service.")
    else:
        keys = ["gross_sales", "discounts", "net_sales", "returns", "cost_of_goods_sold", "gross_profit", "expenses", "estimated_net_operating_profit"] if report_type.startswith("finance") else ["gross_sales", "discounts", "net_sales", "returns", "orders", "average_order_value"]
        doc.kpis(entries(summary, keys[:3]))
        doc.section("Financial summary" if report_type.startswith("finance") else "Summary")
        doc.table(["Metric", "Value"], entries(summary, keys), weights=[7, 3], numeric=(1,))
    return doc.build()
