# PHP/MySQL migration: non-negotiable business rules

This is the behavior to preserve from the FastAPI reference, not a claim that a PHP implementation already exists. The [machine-readable route inventory](php-migration-api-contract.json) covers 232 registered method/path combinations. Each ported route must have a reviewed implementation and a parity test before Hostinger staging acceptance.

## Authorization and data scope

- Authentication uses access and refresh tokens, revocable refresh sessions, token versions, disabled/inactive-user rejection, and role/permission checks on the server. Do not accept a frontend route or hidden menu as authorization.
- OWNER has global scope. MANAGER has operational global scope, but not Owner-only finance, purchase payments or vendor settlement. SALES is limited to its authenticated `assigned_store_id`, including reads, PDFs, invoice history, POS, returns, cash register and reports. Missing assignment fails closed.
- Request `store_id`, query `store_id`, foreign inventory/invoice IDs, and guessed document paths never expand SALES scope. Keep the 15 global-safe, 24 assigned-shop, 193 denied SALES classifications from [the Phase 3 matrix](../output/sales-endpoint-permission-matrix.md), but manually confirm every service/query boundary.
- Private invoice/report documents require authorization *before* file lookup or streaming. This includes historical PDFs and downloadable report exports.

## Product and barcode identity

- The approved CSV defines exactly 160 genuine product names/variants/categories/series/prices. The [canonical barcode manifest](../backend/data/anicraze_canonical_product_barcodes.csv) is a read-only export of 160 approved source reference/SKU/barcode triples; all 160 source values were unique and equal to their SKU at export. A PHP import must reject any mismatch, duplicate, blank, invalid Code 128 value or unexpected existing target row. It must not silently rename/reprice products or regenerate canonical barcodes.
- New-product SKU/barcode allocation must be unique under concurrency, case-insensitively. MySQL/MariaDB collation and unique indexes must be chosen and tested deliberately. The existing 50 × 25 mm label HTML/CSS and human-readable barcode value remain unchanged.

## Inventory, inward, transfer

- Four stock states—available, reserved, damaged, in transit—must never become negative. Every stock-affecting command uses one database transaction, locks rows in a consistent order, validates sufficient quantity under lock, updates balance, and writes its transaction/ledger exactly once. Retrying an idempotency key returns the previous result rather than moving stock again.
- Create receipt records product, positive quantity and non-negative purchase cost; supplier is optional unless payable tracking is selected. **Creating a receipt does not increase stock.** Barcode scan/confirmation is distinct; finalization adds stock to Central Warehouse exactly once. Duplicate scans/finalize retries cannot double-add. Weighted purchase costing must remain consistent.
- The active transfer path is direct multi-product warehouse-to-shop transfer, not the superseded pick/dispatch approval flow. One atomic command removes source available stock, adds destination available stock, writes transfer/items/ledger, and is idempotent. Concurrent transfers must not overdraw source stock.

## POS and invoices

- SALES bills only against its assigned shop. Every product/inventory ID in a cart must belong to that shop, have enough available stock under lock, and be charged from authoritative database prices/rules. No overselling, including simultaneous checkout of the last unit.
- Preserve flat-rupee discount behavior and exact DECIMAL arithmetic; never use floating point for money. Customer name/phone are snapshots on the invoice without requiring CRM creation. A successful sale atomically records invoice/items/payment and stock deduction; repeat `idempotency_key` does not create another invoice/payment/movement.
- Issued invoice number generation is concurrency-safe. Preserve tax-free invoice wording and calculations; do not reintroduce GST/HSN presentation. Preserve logo, rupee glyph, Indian formatting, pagination, and exact issued PDF copies. WhatsApp is disabled and cannot block sale completion.

## Operational gates

Test owner, manager and two distinct SALES shops over HTTP against an isolated MariaDB-compatible database. Include foreign IDs and path traversal, idempotent retries, last-unit concurrent sales/transfers, duplicate receipt confirmation, rollback on payment failure, empty-opening-stock audit, report/P&L comparisons and PDF authorization. Source inspection alone is not a pass.
