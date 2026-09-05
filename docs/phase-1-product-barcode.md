# Phase 1 — Product Master and Barcode integration

## Purpose and boundary

Product Master answers **what ANICRAZE sells**: identity, catalogue classification, images, pricing, tax, supplier reference, status, SKU and barcode. Inventory answers **how many units exist, where they are, and why they changed**. Product details therefore expose only a read-only stock summary and a link to the product-filtered Inventory module. Receiving, adjustment, damage, transfers, audits and movement ledgers remain in Inventory.

## Implementation matrix

| Feature | Backend before Phase 1 | Frontend before Phase 1 | Phase 1 result |
|---|---|---|---|
| Product list/search/filter | Present | Basic 50-row list | Server-backed search, pagination and catalogue filters |
| Product create | Present | Connected, but required a client-generated SKU | Backend SKU generation is now used when SKU is blank |
| Product edit/archive | Present | Missing from active Product route | Connected with RBAC and archive confirmation |
| Images | Upload/remove API present | Initial image upload only | Real upload retained; real images are displayed in master/detail |
| SKU/barcode lookup | Present | Not exposed in Product Master | Search uses the common product endpoint; exact lookup service methods reuse the canonical APIs |
| Barcode generation/SVG | Present | Inventory-only operation | Product Master preview, regenerate, SVG download and label print connected |
| CSV import | Dry-run and commit present | Missing | Two-stage validate/confirm dialog connected |
| CSV export | Filter-aware backend export present | Missing | Authenticated filtered export connected |
| Stock summary | Inventory records present | Product detail showed inventory configuration | Read-only central-godown/shop/total summary; full Inventory link |
| Category/brand/anime/character | CRUD APIs present | Category read view; no active management for other masters | Live references power filters and forms; full master-management UI remains follow-up |
| Batch labels | No batch document endpoint | Prototype inventory barcode action | Single print-ready label and Inventory barcode foundation retained; batch sheet remains Phase 2 |

## SKU rules

- SKU is globally unique across products and variants.
- A supplied SKU is normalized to uppercase and validated by the backend.
- When omitted, the backend uses the PostgreSQL `product_sku_sequence` and category prefix: `ANI-{CATEGORY}-{SEQUENCE}`.
- The frontend never generates its own SKU.

## Barcode rules and workflows

Supplier barcode workflow:

1. Enter or scan the supplier/manufacturer barcode in Product Master.
2. The backend validates format and global uniqueness.
3. The stored value becomes available through `/products/search/barcode/{barcode}`.

Internal barcode workflow:

1. Create the product with no usable supplier barcode.
2. Allow backend SKU generation.
3. Request Code 128 generation through `/products/{id}/barcode`.
4. Preview or download the generated SVG and print the ANICRAZE label.

Code 128 is the internal-label format. Existing EAN-13 generation remains backend-controlled and uses the barcode library checksum implementation. Exact barcode lookup is shared with the future mobile POS; no parallel lookup store or API was introduced.

## Label workflow

The Product Master barcode dialog uses the backend-generated SVG. It renders ANICRAZE, product name, SKU, barcode image/text and selling price. SVG download is real. Print opens a clean print document suitable for a standard thermal label or browser-arranged A4 output. The Inventory barcode centre remains the operational entry point. A server-side batch label PDF and quantity-aware A4 sheet are intentionally left for Phase 2 because no such backend contract currently exists.

## APIs used

- `GET|POST /api/v1/products`
- `GET|PATCH|DELETE /api/v1/products/{id}`
- `GET /api/v1/products/search/sku/{sku}`
- `GET /api/v1/products/search/barcode/{barcode}`
- `GET|POST /api/v1/products/{id}/barcode`
- `POST|DELETE /api/v1/products/{id}/images`
- `POST /api/v1/products/import?dry_run=true|false`
- `GET /api/v1/products/export`
- `GET /api/v1/categories`, `/brands`, `/anime`, `/characters`
- `GET /api/v1/inventory?product_id={id}`

Product listing now supports `missing_barcode`. Inventory listing now supports `product_id`. These are query-layer additions and required no schema migration.

## Permissions

The UI hides or disables create, edit, barcode, archive, import and export actions using the existing permission names. Every API remains protected by backend RBAC. Owner wildcard access and the existing role permission matrix are unchanged.

## Phase 2 continuation

- Add a backend batch-label contract with per-product quantities and compact/standard/A4 layouts.
- Reuse that contract in the Inventory receiving/barcode centre.
- Complete lightweight CRUD management for brands, anime franchises and characters.
- Make the Inventory command centre consume the `product_id` URL filter directly.
- Add browser-driven acceptance tests against seeded PostgreSQL, including real image and file downloads.
