# Phase 2 — Central Godown and Inventory Command Center

## Operating model

The production interface presents one operational warehouse: the configured database warehouse, falling back to **ANICRAZE Central Warehouse**. `inventoryConfig.multiWarehouseEnabled` remains `false`. The database stays multi-warehouse capable for future expansion, but the active UI has no warehouse selector, comparison workflow or invented capacity metric.

Product Master defines what ANICRAZE sells. Inventory owns physical quantities, location, valuation, availability, damage, reservations and movement history.

## Implementation matrix

| Capability | Existing backend | Phase 2 production connection |
|---|---|---|
| Inventory by location | Yes | Aggregated central-godown and shop stock table/detail |
| Summary and analytics | Yes | Real KPI strip and godown overview |
| GRN receiving | Yes | Draft submission and submitted-GRN completion connected |
| Stock adjustment | Yes | Permission-gated preview, confirmation and mutation |
| Damage | Yes | Dedicated view and traceable available-to-damaged operation |
| Barcode | Yes | Phase 1 generator/preview/download/print reused in Inventory |
| Transfers | Yes | Godown-to-shop creation connected; lifecycle remains Phase 3 |
| Ledger | Yes | Append-only movement table and product timeline |
| Alerts | Yes | Reliable low/out/damage classifications from live quantities |
| Reservations | Yes | Available and reserved quantities shown separately |
| Inventory export | Missing | Added full, server-generated CSV export |
| Stock-audit sessions | Missing | Not faked; Audit tab documents and disables unavailable action |

## Stock states

The active UI only derives states that current data supports reliably:

- `OUT OF STOCK`: central godown available quantity is zero.
- `DAMAGED`: one or more damaged units are recorded.
- `CRITICAL`: godown available quantity is at or below minimum stock.
- `LOW STOCK`: godown available quantity is at or below reorder level.
- `HEALTHY`: none of the above.

Fast/slow/dead analytics remain available from the backend summary, but are not presented as row states without a shared classification contract. Damaged units are not sellable. Reserved units are excluded from available stock.

## Receiving workflow

Procurement remains the single receiving architecture:

`Confirmed PO → Draft GRN → Submitted GRN → Complete → Inventory`

The Receiving tab lists real GRNs. Submission changes a draft to submitted. Completing a submitted GRN calls the existing GRN service, which locks the PO, validates over-receipt, creates or locks the destination inventory, moves accepted stock, records received-damaged units as damaged, updates weighted cost, updates PO quantities/status, writes immutable transactions/ledger entries and audits completion. Buttons lock while requests are running.

Manual stock-in is no longer the primary Receive Stock action. It remains an API capability for authorized exceptional use but is not offered as a shortcut around procurement.

## Barcode workflow

Inventory reuses the Phase 1 product barcode dialog and canonical endpoints. Scanner-style inputs accept keyboard scanner text, suppress accidental form submission on Enter and search product name, SKU or barcode. Code 128 generation, SVG preview/download and clean label printing use real product data.

## Adjustment and damage workflows

Adjustments show current quantity, signed change and resulting quantity before confirmation. The backend prevents negative stock and creates an immutable `ADJUSTMENT` transaction plus audit record.

Damage uses the existing damage movement. It atomically decreases available quantity, increases damaged quantity, writes a `DAMAGE` transaction and ledger entry, evaluates alerts and audits the movement. Disposition states such as write-off/return-to-supplier are not implemented by the current inventory domain and are deferred.

## Ledger and idempotency

The command center reads the append-only inventory ledger and exposes date, product, movement, quantity change, location, reference, resulting balance and actor identifier. Stock movement, GRN and transfer services use deterministic or client-generated idempotency keys; active mutation controls are disabled while pending.

## Reorder and shop visibility

Low/out/reorder thresholds come from persisted inventory values. The overview shows actionable central-godown alerts and a read-only snapshot for every configured shop, including units, valuation, low-stock count and out-of-stock count. Full transfer lifecycle refinement belongs to Phase 3.

## Permissions

Existing backend RBAC remains authoritative. The frontend gates adjustment, transfer, barcode and export controls using existing permissions. Cost and valuation are returned only where the current inventory/report API permissions authorize access; a future response-level field policy may further restrict financial fields for sales-facing roles.

## APIs reused

- `/inventory`, `/inventory/reports/stock`, `/inventory/analytics/summary`
- `/inventory/transactions`, `/inventory/ledger`, `/inventory-alerts`
- `/inventory/{id}/damage`, `/stock-adjustments`
- `/stock-transfers`, `/stores`, `/warehouses`
- `/grns`, `/grns/{id}/submit`, `/grns/{id}/complete`
- `/products/{id}/barcode`, product SKU/barcode lookup

## API added

- `GET /inventory/export`: server-generated full-location CSV protected by `reports.inventory.export` and audited as `INVENTORY_EXPORTED`.

No Phase 2 database migration was required.

## Audit approach and limitations

The database has immutable movement/audit logs but no physical stock-audit session, count lines, variance review or approval state. Phase 2 therefore uses approved stock adjustments for isolated corrections and explicitly disables “Start Stock Audit.” A real audit subsystem would require a justified schema migration and is not represented by browser-only state.

Other limitations:

- Creating a new GRN line-by-line still belongs to the Procurement UI; Inventory handles submission/completion of existing GRNs.
- Transfer creation is connected, but approval/packing/dispatch/shop receipt UX is Phase 3.
- Damaged-stock disposition is not modeled.
- Batch label jobs and persistent barcode job history are not modeled.
- Analytics are summary cards and live location distribution; additional charts should use backend series rather than mock arrays.

## Phase 3 handoff

Phase 3 should implement the godown-to-shop transfer lifecycle UI: request/approval, picking, packing, dispatch, in-transit tracking, shop receipt, discrepancies and completion. It should reuse the existing `StockTransfer` state machine and inventory ledger rather than introduce a second transfer domain.
