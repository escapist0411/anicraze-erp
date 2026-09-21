# Phase 3 — Central Godown to Shop Transfers

## Existing architecture and extension

Phase 3 extends the existing `StockTransfer` and `StockTransferItem` domain. No second transfer model or inventory movement service was introduced.

The original state machine was:

`CREATED → APPROVED → PACKED → DISPATCHED → RECEIVED → COMPLETED`

It moved available stock only at dispatch and could not persist picking, receiving counts, discrepancies, or operational actors. The production lifecycle is now:

`CREATED → PENDING_APPROVAL → APPROVED → PICKING → PICKED → PACKED → DISPATCHED → RECEIVING → COMPLETED`

Alternate terminal/review states are `REJECTED`, `CANCELLED`, and `DISCREPANCY`.

## Inventory semantics

- Creation validates current godown availability but does not mutate inventory.
- Approval locks source records and reserves each line: available decreases and reserved increases.
- Cancellation or rejection before dispatch releases active reservations exactly once.
- Dispatch consumes reserved quantities and writes `TRANSFER_OUT` transactions and ledger entries. Dispatched units are neither godown-available nor shop-available; in-transit totals are derived from dispatched/receiving transfers.
- Clean receipt writes `TRANSFER_IN` at the destination and completes the transfer.
- Damaged-on-arrival units are transferred into the destination and immediately moved from available to damaged using the existing damage service.
- A shortage remains recorded on the transfer as unresolved discrepancy and is not added to shop inventory.
- Excess is persisted as a discrepancy and is never automatically added to inventory.

A transfer creates no invoice, customer billing record, revenue, customer transaction or sale.

## Transfer numbering and creation

The server creates an immutable, concurrency-safe human reference when the client omits one:

`ANI-TRF-{YEAR}-{UUID_PREFIX}`

The production form fixes the source to the configured central godown, lists real stores, supports product/SKU/barcode lookup, shows godown availability and destination stock, prevents duplicate lines, and sends one transfer request to the backend.

## Approval and reservation

Submission changes `CREATED` to `PENDING_APPROVAL`. Approval re-locks every source inventory row and rejects the entire transaction if any line is no longer available. Successful approval creates persisted `StockReservation` rows under the transfer reference. This protects concurrent transfers from oversubscribing godown stock.

## Picking and packing

Picking counts are persisted per transfer item. Manual counts and barcode scans are supported. Unknown products and counts above the requested quantity are rejected. A transfer reaches `PICKED` only after every line is fully picked. Packing records actor and time and is only allowed from `PICKED`.

## Dispatch and in-transit accounting

Dispatch is a single backend transition. It validates all picked counts and active reservations, consumes reservations, reduces godown-held physical inventory, writes append-only transactions/ledger records, and stores dispatcher/time. Repeated dispatch is rejected by the state machine and deterministic transaction idempotency keys.

## Shop receiving and scanner

The receiving interface is mobile-first and contains no cost, valuation, supplier, margin or profit fields. It supports:

- USB/Bluetooth keyboard scanners
- Manual barcode/SKU entry
- Native `BarcodeDetector` camera scanning where browser support and permission exist
- Rear-camera preference, duplicate debounce and stream cleanup
- Manual fallback when camera detection is unavailable

Receiving requests contain only item IDs and good/damaged/excess counts. The backend derives shortages, applies destination inventory movements atomically and persists discrepancies.

## Store authorization

Transfer list queries are automatically restricted by `users.assigned_store_id`. Detail and receiving services also enforce that a store-assigned user can access only a transfer whose destination matches that store. Owner/godown users with no assigned store retain authorized global access. Frontend filtering is not trusted for authorization.

## Traceability and audit

Transfers persist created, approved, picked, packed, dispatched and received actors/timestamps. Audit events cover creation, submission, approval, picking start/completion, packing, dispatch, receiving start, clean receipt, discrepancy, rejection and cancellation. Inventory effects remain traceable through the existing transaction and ledger tables.

## API endpoints

Reused:

- `GET|POST /stock-transfers`
- `GET /stock-transfers/{id}`
- `PATCH /stock-transfers/{id}/status`
- Inventory, store, warehouse, transaction and ledger APIs

Added:

- `POST /stock-transfers/{id}/pick`
- `POST /stock-transfers/{id}/receive`

## Migration

Migration `20260831_0012` is required to persist operational actors/timestamps, picking counts, received/damaged/shortage/excess quantities, cancellation reason and discrepancy notes. It preserves existing rows through nullable actor/timestamp fields and zero-default item quantities and includes a downgrade.

## Notifications

No persistent notification service/model exists in the current backend. Transfer events are fully audited, but in-app notification creation was not faked. A later notification implementation can subscribe to the documented audit/domain events.

## Known limitations

- Discrepant transfers stay in `DISCREPANCY`; manager resolution and reconciliation are not yet implemented.
- Packed cancellation releases reservations but no package records exist.
- Vehicle, courier, package count and proof-of-delivery are outside the current model.
- Native camera scanning depends on browser `BarcodeDetector`; manual/USB scanning is the universal fallback.
- Existing records created before migration have zero picking/receiving counts and retain their existing statuses.

## Phase 4 handoff

Phase 4 can rely on assigned-store authorization, accurate shop inventory, canonical product barcode lookup, the reusable scanner, and append-only store inventory movements. Mobile POS must deduct only from the authenticated employee's assigned-shop available stock and must not reuse transfer operations as sales.
