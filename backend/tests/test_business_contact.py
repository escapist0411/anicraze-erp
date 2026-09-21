from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from pypdf import PdfReader

from app.config.business import BUSINESS_PHONE_DISPLAY, BUSINESS_PHONE_NORMALIZED
from app.main import app
from app.services.billing import InvoicePDFService


def test_official_business_contact_is_centralized():
    assert BUSINESS_PHONE_DISPLAY == "+91 80105 26600"
    assert BUSINESS_PHONE_NORMALIZED == "+918010526600"


def test_invoice_api_contract_contains_business_and_print_details():
    fields = app.openapi()["components"]["schemas"]["InvoiceResponse"]["properties"]
    for field in ("business_contact", "store_name", "store_address", "employee_name", "customer_name", "payment_methods"):
        assert field in fields


def test_invoice_pdf_renders_official_contact_and_payment(tmp_path):
    service = InvoicePDFService()
    service.root = tmp_path
    invoice = SimpleNamespace(
        invoice_number="CONTACT-VERIFY",
        created_at=datetime.now(timezone.utc),
        items=[SimpleNamespace(sku="ANI-001", product_name="Demo Figure", quantity=1, unit_price=Decimal("800"), discount=Decimal("0"), line_total=Decimal("800"))],
        subtotal=Decimal("800"),
        discount=Decimal("0"),
        grand_total=Decimal("800"),
    )
    path = service.generate(
        invoice,
        SimpleNamespace(name="Demo Customer", address="Pune"),
        SimpleNamespace(name="Elpro City Square Mall", address="Pimpri-Chinchwad"),
        SimpleNamespace(full_name="Demo Employee", employee_code="EMP-ELPRO-001"),
        ["UPI"],
    )
    text = " ".join(page.extract_text() or "" for page in PdfReader(path).pages)
    assert BUSINESS_PHONE_DISPLAY in text
    assert "Payment" in text and "UPI" in text
    assert "TOTAL" in text
