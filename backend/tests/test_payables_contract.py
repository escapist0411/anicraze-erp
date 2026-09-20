from decimal import Decimal
from uuid import uuid4
import pytest
import httpx
from types import SimpleNamespace
from pydantic import ValidationError

from app.main import app
from app.models.payables import PayablePaymentMethod, PayableStatus, ReminderStatus
from app.schemas.payables import PayableCreate, PaymentCreate
from app.permissions.dependencies import require_owner
from app.exceptions.domain import AuthorizationError


def test_purchase_payable_contract_uses_decimal_and_rejects_invalid_money():
    payload=PayableCreate(supplier_id=uuid4(),total_amount="50000.00",initially_paid="20000.00",initial_payment_method=PayablePaymentMethod.BANK_TRANSFER)
    assert payload.total_amount==Decimal("50000.00")
    assert payload.initially_paid==Decimal("20000.00")
    with pytest.raises(ValidationError):PayableCreate(supplier_id=uuid4(),total_amount="0")
    with pytest.raises(ValidationError):PaymentCreate(amount="0",payment_method=PayablePaymentMethod.CASH)


def test_owner_payment_routes_are_separate_from_pos_payments():
    paths={route.path for route in app.routes}
    assert {"/api/v1/purchase-payables","/api/v1/purchase-payables/summary","/api/v1/purchase-payables/{payable_id}/payments","/api/v1/purchase-payables/{payable_id}/reminders"}.issubset(paths)
    assert {PayableStatus.UNPAID,PayableStatus.PARTIALLY_PAID,PayableStatus.PAID,PayableStatus.OVERDUE}.issubset(set(PayableStatus))
    assert {ReminderStatus.SCHEDULED,ReminderStatus.TRIGGERED,ReminderStatus.DISMISSED,ReminderStatus.CANCELLED}.issubset(set(ReminderStatus))


@pytest.mark.asyncio
async def test_purchase_payables_require_authentication():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
        assert (await client.get("/api/v1/purchase-payables")).status_code==401


@pytest.mark.asyncio
@pytest.mark.parametrize("role",["MANAGER","SALES","EMPLOYEE"])
async def test_owner_dependency_rejects_non_owner_roles(role):
    actor=SimpleNamespace(id=uuid4(),roles=[SimpleNamespace(code=role,name=role)])
    with pytest.raises(AuthorizationError):await require_owner(actor)


@pytest.mark.asyncio
async def test_owner_dependency_accepts_owner():
    actor=SimpleNamespace(id=uuid4(),roles=[SimpleNamespace(code="OWNER",name="OWNER")])
    assert await require_owner(actor) is actor
