from decimal import Decimal
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.models.crm import CustomerType
from app.schemas.crm import CustomerCreateRequest,LoyaltyRedeemRequest,MembershipTierRequest
from app.services.communications import DevelopmentWhatsAppProvider,valid_meta_signature
from app.utils.phone import normalize_indian_phone
from app.main import app
def test_customer_requires_name():
 with pytest.raises(ValidationError): CustomerCreateRequest(full_name="x")
def test_walkin_needs_no_contact(): assert CustomerCreateRequest(full_name="Walk-in",customer_type=CustomerType.WALK_IN).mobile is None
def test_redemption_positive():
 with pytest.raises(ValidationError): LoyaltyRedeemRequest(customer_id=uuid4(),points=0)
def test_tier_money_decimal_and_discount_bounds():
 x=MembershipTierRequest(name="Gold",code="GOLD",level=2,minimum_spend=Decimal("25000"),discount_percentage=5,loyalty_multiplier=Decimal("1.25"));assert x.minimum_spend==Decimal("25000")
 with pytest.raises(ValidationError): MembershipTierRequest(name="Bad",code="BAD",level=1,minimum_spend=0,discount_percentage=101,loyalty_multiplier=1)
def test_indian_phone_normalization_prevents_country_code_duplicates():
 assert normalize_indian_phone("+91 98765 00001")==normalize_indian_phone("9876500001")=="919876500001"
def test_phase5_communication_endpoints_are_exposed():
 paths=app.openapi()["paths"]
 for path in ("/api/v1/customer-communications","/api/v1/customers/{id}/communications","/api/v1/invoices/{id}/communications","/api/v1/communications/whatsapp/send","/api/v1/communications/{id}/retry"):
  assert path in paths
@pytest.mark.asyncio
async def test_development_provider_is_honestly_simulated(tmp_path):
 pdf=tmp_path/"invoice.pdf";pdf.write_bytes(b"%PDF-test")
 invoice=type("Invoice",(),{"invoice_number":"ANI-INV-TEST"})();customer=type("Customer",(),{"name":"Test Customer"})()
 result=await DevelopmentWhatsAppProvider().send_invoice(invoice,customer,"919876543210",pdf)
 assert result.status=="SIMULATED" and result.message_id is None and result.reference.startswith("development:")
def test_communication_model_has_provider_tracking_and_idempotency():
 from app.models.crm import CustomerCommunication
 fields=set(CustomerCommunication.__table__.columns.keys())
 assert {"provider","provider_message_id","idempotency_key","attempt_count","delivered_at","read_at","failure_code"}<=fields
def test_meta_webhook_signature_is_authenticated(monkeypatch):
 import app.services.communications as communications
 monkeypatch.setattr(communications,"get_settings",lambda:type("Cfg",(),{"whatsapp_app_secret":"test-secret"})())
 import hashlib,hmac
 body=b'{"entry":[]}'
 signature="sha256="+hmac.new(b"test-secret",body,hashlib.sha256).hexdigest()
 assert valid_meta_signature(body,signature)
 assert not valid_meta_signature(body,"sha256=invalid")
