from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.exceptions.domain import AuthorizationError
from app.schemas.inventory import DirectTransferRequest
from app.services.inventory import TransferService


def payload():
    return {
        "idempotency_key": uuid4(),
        "source_warehouse_id": uuid4(),
        "target_store_id": uuid4(),
        "items": [
            {"product_id": uuid4(), "quantity": 2},
            {"product_id": uuid4(), "quantity": 1},
        ],
    }


def test_direct_transfer_schema_accepts_multi_product_command():
    command = DirectTransferRequest.model_validate(payload())
    assert [item.quantity for item in command.items] == [2, 1]
    assert command.reference_number is None


def test_direct_transfer_schema_rejects_same_location():
    location_id = uuid4()
    data = payload() | {
        "source_warehouse_id": location_id,
        "target_store_id": None,
        "target_warehouse_id": location_id,
    }
    with pytest.raises(ValidationError, match="Source and target must differ"):
        DirectTransferRequest.model_validate(data)


@pytest.mark.parametrize("role", ["OWNER", "MANAGER", "ADMIN"])
def test_owner_and_manager_roles_can_direct_transfer(role):
    service = TransferService.__new__(TransferService)
    service.actor = SimpleNamespace(roles=[SimpleNamespace(code=role)])
    service.authorize_direct_transfer()


def test_employee_role_cannot_direct_transfer():
    service = TransferService.__new__(TransferService)
    service.actor = SimpleNamespace(roles=[SimpleNamespace(code="EMPLOYEE")])
    with pytest.raises(AuthorizationError):
        service.authorize_direct_transfer()


def test_direct_transfer_source_contains_atomic_safety_controls():
    source = Path("app/services/inventory.py").read_text()
    assert "pg_advisory_xact_lock" in source
    assert "with_for_update" in Path("app/repositories/inventory.py").read_text()
    assert "TransactionType.TRANSFER_OUT" in source
    assert "TransactionType.TRANSFER_IN" in source
    assert "TransferStatus.COMPLETED" in source
    assert 'title="Stock Received"' in source
    assert "TRANSFER_INSUFFICIENT_STOCK" in source
    assert "direct-transfer:{data.idempotency_key}" in source


def test_active_frontend_uses_direct_endpoint_without_lifecycle_actions():
    center = Path("../frontend/src/components/transfers/StockTransferCenter.tsx").read_text()
    divert = Path("../frontend/src/pages/owner/DivertStock.tsx").read_text()
    assert "directTransfer" in center and "directTransfer" in divert
    for obsolete in ("Approve", "Start Picking", "Dispatch", "Receive Stock", "CountWorkflow", "Timeline"):
        assert obsolete not in center


class FakeScalars:
    def __init__(self, values): self.values = values
    def all(self): return self.values


class FakeSession:
    def __init__(self, recipients=()): self.transfer = None; self.added = []; self.recipients = list(recipients)
    async def execute(self, _query): return None
    async def scalar(self, _query): return self.transfer
    async def scalars(self, _query): return FakeScalars(self.recipients)
    def add(self, value):
        self.added.append(value)
        if value.__class__.__name__ == "StockTransfer": self.transfer = value
    async def flush(self):
        if self.transfer and self.transfer.id is None:
            self.transfer.id = uuid4()
            for item in self.transfer.items: item.id = uuid4()


class FakeRepo:
    def __init__(self, inventory): self.inventory = inventory
    async def find(self, product_id, variant_id, store_id, warehouse_id, lock=False):
        return self.inventory.get((product_id, variant_id, store_id, warehouse_id))
    async def transfer(self, _transfer_id): return self.session.transfer


@pytest.mark.asyncio
async def test_exact_direct_transfer_balances_ledger_notification_and_idempotency():
    warehouse_id, store_id, product_a, product_b, recipient = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    def inventory(product_id, quantity, *, store=None, warehouse=None):
        return SimpleNamespace(id=uuid4(), product_id=product_id, variant_id=None, store_id=store, warehouse_id=warehouse,
                               available_quantity=quantity, reserved_quantity=0, minimum_stock=0, reorder_level=0, average_cost=10)
    source_a, source_b = inventory(product_a, 5, warehouse=warehouse_id), inventory(product_b, 3, warehouse=warehouse_id)
    target_a, target_b = inventory(product_a, 1, store=store_id), inventory(product_b, 0, store=store_id)
    records = {
        (product_a, None, None, warehouse_id): source_a, (product_b, None, None, warehouse_id): source_b,
        (product_a, None, store_id, None): target_a, (product_b, None, store_id, None): target_b,
    }
    session, actor = FakeSession([recipient]), SimpleNamespace(id=uuid4(), roles=[SimpleNamespace(code="MANAGER")])
    service = TransferService.__new__(TransferService); service.session = session; service.actor = actor
    service.repo = FakeRepo(records); service.repo.session = session
    service.location = AsyncMock(side_effect=lambda _model, location_id: SimpleNamespace(id=location_id, name="Central Warehouse" if location_id == warehouse_id else "Destination Shop"))
    service.audit = AsyncMock()
    movements = []
    async def move(record, kind, change, reference, key, *args):
        record.available_quantity += change; movements.append((record.product_id, kind.value, change, reference, key))
    service.move = move
    command = DirectTransferRequest.model_validate({
        "idempotency_key": uuid4(), "source_warehouse_id": warehouse_id, "target_store_id": store_id,
        "items": [{"product_id": product_a, "quantity": 2}, {"product_id": product_b, "quantity": 1}],
    })
    result = await service.direct_transfer(command)
    assert (source_a.available_quantity, source_b.available_quantity) == (3, 2)
    assert (target_a.available_quantity, target_b.available_quantity) == (3, 1)
    assert sorted(change for _, _, change, _, _ in movements) == [-2, -1, 1, 2]
    assert result.status.value == "COMPLETED"
    notifications = [item for item in session.added if item.__class__.__name__ == "Notification"]
    assert len(notifications) == 1 and notifications[0].title == "Stock Received"
    assert "2 products / 3 units" in notifications[0].message
    repeated = await service.direct_transfer(command)
    assert repeated.id == result.id and len(movements) == 4


@pytest.mark.asyncio
async def test_insufficient_direct_transfer_has_no_partial_movement():
    warehouse_id, store_id, product_id = uuid4(), uuid4(), uuid4()
    source = SimpleNamespace(id=uuid4(), product_id=product_id, variant_id=None, store_id=None, warehouse_id=warehouse_id,
                             available_quantity=1, minimum_stock=0, reorder_level=0, average_cost=10)
    session, actor = FakeSession(), SimpleNamespace(id=uuid4(), roles=[SimpleNamespace(code="OWNER")])
    service = TransferService.__new__(TransferService); service.session = session; service.actor = actor
    service.repo = FakeRepo({(product_id, None, None, warehouse_id): source}); service.repo.session = session
    service.location = AsyncMock(return_value=SimpleNamespace(name="Location")); service.audit = AsyncMock(); service.move = AsyncMock()
    command = DirectTransferRequest.model_validate({"idempotency_key":uuid4(),"source_warehouse_id":warehouse_id,"target_store_id":store_id,"items":[{"product_id":product_id,"quantity":2}]})
    with pytest.raises(Exception, match="Insufficient stock"):
        await service.direct_transfer(command)
    assert source.available_quantity == 1
    assert service.move.await_count == 0
    assert not any(item.__class__.__name__ in {"StockTransfer", "Notification"} for item in session.added)
