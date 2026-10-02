from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace as Obj

from pypdf import PdfReader

from app.pdf.documents import invoice_pdf, report_pdf
from app.pdf.formatters import format_currency, format_date, format_datetime, format_number


def invoice_fixture(payments):
    invoice = Obj(
        invoice_number="ANI-INV-TEST-001",
        created_at=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
        subtotal=Decimal("1000"), discount=Decimal("0"), grand_total=Decimal("1000"),
        items=[Obj(sku="ANI-KEY-000001", product_name="Sample keychain", quantity=1, unit_price=Decimal("1000"), line_total=Decimal("1000"))],
        payments=payments,
    )
    return invoice, Obj(name="Sample Customer", phone="+91 98765 43210"), Obj(name="ANICRAZE Sample Shop", address="Sample address"), Obj(full_name="Sample Employee", employee_code="EMP-001")


def test_indian_currency_and_date_formatters():
    assert format_currency(499) == "₹499"
    assert format_currency(12999) == "₹12,999"
    assert format_currency(100000) == "₹1,00,000"
    assert format_currency(486000) == "₹4,86,000"
    assert format_currency(1250000) == "₹12,50,000"
    assert format_currency("678.57") == "₹678.57"
    assert format_number(1240) == "1,240"
    assert format_date(date(2026, 9, 27)) == "27 Sep 2026"
    assert format_datetime(datetime(2026, 9, 27, 18, tzinfo=timezone.utc)) == "27 Sep 2026, 11:30 PM"


def test_customer_invoice_is_one_a4_page_has_rupee_and_no_gst(tmp_path):
    pdf = tmp_path / "invoice.pdf"
    pdf.write_bytes(invoice_pdf(*invoice_fixture([Obj(method=Obj(name="UPI", code="UPI"), amount=Decimal("1000"))]), preview=True))
    reader = PdfReader(pdf)
    assert len(reader.pages) == 1
    assert round(float(reader.pages[0].mediabox.width) * 25.4 / 72) == 210
    text = reader.pages[0].extract_text()
    assert all(term not in text.upper() for term in ("GST", "CGST", "SGST", "IGST", "HSN", "INR"))
    assert "₹1,000" in text and "SAMPLE PREVIEW" in text and "Page 1 of 1" in text


def test_invoice_renders_real_cash_change_and_split_amounts(tmp_path):
    cash = Obj(method=Obj(name="Cash", code="CASH"), amount=Decimal("450"), tendered_amount=Decimal("500"), change_amount=Decimal("50"))
    path = tmp_path / "cash.pdf"; path.write_bytes(invoice_pdf(*invoice_fixture([cash]), preview=True))
    text = PdfReader(path).pages[0].extract_text()
    assert "Cash Received" in text and "₹500" in text and "Change Returned" in text and "₹50" in text
    split = [cash, Obj(method=Obj(name="UPI", code="UPI"), amount=Decimal("550"), tendered_amount=None, change_amount=Decimal("0"))]
    path = tmp_path / "split.pdf"; path.write_bytes(invoice_pdf(*invoice_fixture(split), preview=True))
    text = PdfReader(path).pages[0].extract_text()
    assert "Cash" in text and "UPI" in text and "₹450" in text and "₹550" in text


def test_all_shop_pnl_table_is_landscape_and_has_total(tmp_path):
    rows = [{"shop": f"Shop {i}", "gross_sales": Decimal(1000), "discounts": Decimal(10), "net_sales": Decimal(990), "returns_refunds": Decimal(5), "net_revenue": Decimal(985), "cogs": Decimal(500), "gross_profit": Decimal(485), "gross_margin_percentage": Decimal("49.24")} for i in range(8)]
    summary = {key: sum((row[key] for row in rows), Decimal(0)) for key in ("gross_sales", "discounts", "net_sales", "returns_refunds", "net_revenue", "cogs", "gross_profit")}
    summary["gross_margin_percentage"] = Decimal("49.24")
    path = tmp_path / "shops.pdf"; path.write_bytes(report_pdf("finance_shop-profit-loss", {"summary": summary, "rows": rows, "filters": {}, "document_metadata": {"period": "01 Sep 2026 - 30 Sep 2026", "location": "All Shops"}}, preview=True))
    reader = PdfReader(path)
    assert len(reader.pages) == 1 and reader.pages[0].mediabox.width > reader.pages[0].mediabox.height
    text = reader.pages[0].extract_text()
    assert all(f"Shop {i}" in text for i in range(8)) and "TOTAL" in text and "Gross\nMargin" in text


def test_empty_report_has_clean_empty_state_and_page_number(tmp_path):
    path = tmp_path / "empty.pdf"; path.write_bytes(report_pdf("sales_summary", {"summary": {}, "rows": [], "document_metadata": {}}, preview=True))
    reader = PdfReader(path)
    assert len(reader.pages) == 1
    assert "No records found" in reader.pages[0].extract_text()
    assert "Page 1 of 1" in reader.pages[0].extract_text()


def test_long_invoice_starts_items_on_first_page_and_repeats_table_headers(tmp_path):
    invoice, customer, store, employee = invoice_fixture([])
    invoice.items = [Obj(sku=f"ANI-KEY-{i:06d}", product_name=f"Long named collector figure with interchangeable accessories {i}", quantity=1, unit_price=Decimal("1000"), line_total=Decimal("1000")) for i in range(1, 29)]
    invoice.subtotal = invoice.grand_total = Decimal("28000")
    path = tmp_path / "long.pdf"
    path.write_bytes(invoice_pdf(invoice, customer, store, employee))
    reader = PdfReader(path)
    assert len(reader.pages) > 1
    assert "ANI-KEY-000001" in reader.pages[0].extract_text()
    assert "ANI-KEY-000028" in "\n".join(page.extract_text() for page in reader.pages)
    for index, page in enumerate(reader.pages):
        assert f"Page {index + 1} of {len(reader.pages)}" in page.extract_text()
