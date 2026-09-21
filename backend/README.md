# ANICRAZE ERP Backend

FastAPI, async SQLAlchemy, PostgreSQL, Alembic, JWT rotation, database-backed RBAC, direct user permissions, session administration, and audit logging.

## Phase 12 access management

The API follows route → service → repository boundaries. Routes enforce database permissions; services own validation, transactions, final-owner protection, password/session operations and audit events; repositories contain async persistence queries. Effective access is the union of role permissions and direct user permissions. `OWNER` retains wildcard `*` access.

System roles are `OWNER`, `ADMIN`, `MANAGER`, `ACCOUNTANT`, `INVENTORY`, `SALES`, `HR`, and `EMPLOYEE`. System roles cannot be deleted, assigned roles cannot be deleted, the final active owner cannot be deleted/deactivated/suspended or lose OWNER, and an owner cannot delete their own account. Deletion is soft and revokes sessions.

### Setup

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.scripts.seed_owner
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The seed is idempotent. Credentials below are development-only:

| Role | Email | Password |
|---|---|---|
| OWNER | owner@anicraze.com | `LOCAL_OWNER_PASSWORD` |
| MANAGER | manager@anicraze.com | `LOCAL_MANAGER_PASSWORD` |
| ACCOUNTANT | accountant@anicraze.com | `LOCAL_ACCOUNTANT_PASSWORD` |
| INVENTORY | inventory@anicraze.com | `LOCAL_INVENTORY_PASSWORD` |
| SALES | sales@anicraze.com | `LOCAL_SALES_PASSWORD` |
| HR | hr@anicraze.com | `LOCAL_HR_PASSWORD` |

### Default matrix

- OWNER: `*`
- ADMIN: every seeded permission except `*`
- MANAGER: dashboard, product/inventory operations, billing/report/employee/store read
- ACCOUNTANT: finance, billing/report exports and expenses
- INVENTORY: product maintenance, inventory, purchasing and suppliers
- SALES: products/inventory read, billing and customers
- HR: employees, attendance, leave and payroll read
- EMPLOYEE: own profile, attendance and tasks

### Endpoints and permissions

| Resource | Operations | Required permissions |
|---|---|---|
| `/api/v1/users` | list, create, detail, update, soft-delete | `users.read/create/update/delete` |
| `/api/v1/users/{id}/status` | activate, deactivate, suspend, lock | `users.manage_status` |
| `/api/v1/users/{id}/roles` | assign/remove roles | `users.assign_roles` |
| `/api/v1/users/{id}/permissions` | assign/remove direct grants | `users.assign_permissions` |
| `/api/v1/users/{id}/reset-password` | admin reset | `users.reset_password` |
| `/api/v1/users/{id}/unlock` | clear lock state | `users.manage_status` |
| `/api/v1/users/{id}/sessions` | list/revoke sessions | `users.manage_sessions` |
| `/api/v1/users/{id}/audit-logs` | activity history | `users.read` |
| `/api/v1/roles` | CRUD, users and permission assignments | `roles.*` |
| `/api/v1/permissions` | CRUD and grouped list | `permissions.*` |

Role permission assignment supports `mode: "replace"` (the default) or `mode: "add"`. Store IDs are nullable and UUID-ready; Phase 12 does not create the future store domain.

### Swagger demo

Open `http://127.0.0.1:8000/api/v1/docs`. Login as owner, copy the access token into Swagger authorization, list users, create a manager, assign MANAGER, inspect effective permissions, suspend the user and verify login rejection, reactivate it, verify the manager receives 403 on user-management routes, then login as owner and revoke the manager sessions.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner@anicraze.com","password":"<LOCAL_OWNER_PASSWORD>","remember_me":false}'

curl http://127.0.0.1:8000/api/v1/users \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

Common errors include `AUTH_PERMISSION_DENIED` (403), `USER_NOT_FOUND` (404), duplicate email/employee code (409), protected final owner/system resources (409), and password-policy failures (422). Passwords, token hashes, reset tokens and internal secrets are never returned or audited.

## Phase 13 product catalog

The catalog domain adds nested categories, brands, anime franchises, characters, products, image galleries and product variants. Products reference their catalog masters; characters belong to an anime franchise. Product money uses PostgreSQL `NUMERIC` and Python `Decimal`. Inventory quantities are deliberately absent and will be introduced by the inventory phase.

SKU generation uses the PostgreSQL `product_sku_sequence`, never row counts, with format `ANI-{CATEGORY_CODE}-{SEQUENCE}`. Code 128 is the default barcode; EAN-13 is available through the generation request. SVG files are served under `/uploads/barcodes`. Product images accept JPEG, PNG or WEBP up to 5 MB, validate file signatures, use generated filenames, and are stored under `/uploads/products/{product_id}` through a replaceable storage service.

### Catalog setup and demo data

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.scripts.seed_owner
.venv/bin/python -m app.scripts.seed_catalog
```

The catalog seed is idempotent and creates seven categories, five brands, six anime franchises, six characters, and fifteen realistic development products including Gojo Hollow Purple, Naruto Sage Mode, Luffy Gear 5, Tanjiro Nendoroid, Levi Figma, Goku Ultra Instinct, Pochita Plushie, manga, apparel, keychains and posters.

### Catalog endpoints

| Resource | Operations | Permission family |
|---|---|---|
| `/api/v1/products` | List, create, detail, update, soft-delete | `products.read/create/update/delete` |
| `/products/{id}/status` | Status transition with reason | `products.update_status` |
| `/products/{id}/images` | Multipart add and soft-remove | `products.manage_images` |
| `/products/{id}/barcode` | Generate/regenerate and retrieve | `products.manage_barcode`, read retrieval |
| `/products/{id}/history` | Product-scoped audit history | `products.read_history` |
| `/products/search/sku/{sku}` | Exact SKU lookup | `products.read` |
| `/products/search/barcode/{barcode}` | Exact barcode lookup | `products.read` |
| `/products/import` | CSV preview or atomic import | `products.import` |
| `/products/export` | Filter-aware streamed CSV | `products.export` |
| `/categories`, `/categories/tree` | Nested category CRUD/tree | `categories.*` |
| `/brands` | Brand CRUD | `brands.*` |
| `/anime` | Franchise CRUD/search | `anime.*` |
| `/characters` | Character CRUD/search/anime filter | `characters.*` |

ADMIN receives full catalog management. MANAGER can read/create/update products and read masters. INVENTORY can manage products, status, imports, exports, images and barcodes. SALES is read-only. ACCOUNTANT can read products and categories. OWNER retains wildcard access.

### CSV import

Send a UTF-8 CSV (maximum 5 MB) with headers matching product create fields. Required columns are `name`, `category_id`, and `product_type`; pricing fields accept decimal strings. Use `dry_run=true` for validation. Invalid non-partial batches do not commit.

```csv
name,sku,category_id,product_type,purchase_price,landed_cost,selling_price,mrp,status
Gojo Figure,,CATEGORY_UUID,FIGURE,1200,1450,2499,2999,18,ACTIVE
```

### Catalog curl flow

```bash
# Create category
curl -X POST http://127.0.0.1:8000/api/v1/categories -H 'Authorization: Bearer TOKEN' -H 'Content-Type: application/json' -d '{"name":"Figures","code":"FIG"}'

# Create product (SKU generated)
curl -X POST http://127.0.0.1:8000/api/v1/products -H 'Authorization: Bearer TOKEN' -H 'Content-Type: application/json' -d '{"name":"Gojo Figure","category_id":"UUID","product_type":"FIGURE","purchase_price":"1200","landed_cost":"1450","selling_price":"2499","mrp":"2999","status":"ACTIVE"}'

curl 'http://127.0.0.1:8000/api/v1/products?search=gojo&status=ACTIVE' -H 'Authorization: Bearer TOKEN'
curl http://127.0.0.1:8000/api/v1/products/search/barcode/BARCODE -H 'Authorization: Bearer TOKEN'
curl -X POST http://127.0.0.1:8000/api/v1/products/UUID/barcode -H 'Authorization: Bearer TOKEN' -H 'Content-Type: application/json' -d '{"format":"CODE128","regenerate":false}'
curl -X PATCH http://127.0.0.1:8000/api/v1/products/UUID -H 'Authorization: Bearer TOKEN' -H 'Content-Type: application/json' -d '{"selling_price":"2299","mrp":"2999"}'
curl -X DELETE http://127.0.0.1:8000/api/v1/products/UUID -H 'Authorization: Bearer TOKEN'
```

Swagger demo: login as owner, list categories, create an anime franchise and character, create a product and inspect its generated SKU, generate a barcode, search by that barcode, update selling price, inspect product history, filter the product list, then login as SALES and confirm list access succeeds while creation returns `AUTH_PERMISSION_DENIED`.

Catalog conflicts use stable codes such as `PRODUCT_SKU_EXISTS`, `PRODUCT_BARCODE_EXISTS`, `PRODUCT_PRICING_INVALID`, `PRODUCT_CHARACTER_ANIME_MISMATCH`, `CATEGORY_CIRCULAR_PARENT`, and `{MASTER}_IN_USE`. Catalog deletion is soft; active referenced products block master deletion, and historical product records remain intact.
# Inventory management

Phase 14 adds canonical store/warehouse inventory, append-only movement transactions and ledger, weighted purchase costing, idempotent stock operations, threshold alerts, reservations, adjustments, transfers, analytics and stock reports. Apply with `alembic upgrade head`; seed demo locations and stock with `python -m app.scripts.seed_inventory`. Inventory endpoints are documented at `/api/v1/docs` and require the `inventory.*` permissions.

# Billing and POS architecture

The POS workflow atomically handles customers, invoices, discounts, payments, returns, refunds, cash registers and inventory-ledger movements. `POST /api/v1/billing` locks inventory, validates products and authoritative prices, applies discounts, persists payment, completes the invoice and deducts stock in one transaction.

Invoice and item values are immutable monetary snapshots. Split tender is represented by multiple payment entries. Cash change uses `tendered_amount`, while electronic payments require a reference.

Returns use `POST /api/v1/returns`, enforce cumulative quantities against the source invoice, restore inventory through the ledger and refund the actual amount attributable to the sold line. Download branded PDFs from `GET /api/v1/invoices/{id}/pdf`.

Swagger examples and all POS, barcode, invoice, payment, return, refund, analytics and report contracts are available at `/api/v1/docs`. Seed demo billing data with `python -m app.scripts.seed_billing` after migrations and the catalog/inventory seeds. Notification abstractions (`WhatsAppService`, `SMSService`, `EmailService`) log safely in development and expose provider-neutral methods for later integrations.

# Procurement architecture

Phase 16 implements `Purchase Request → Approval → Purchase Order → Supplier Confirmation → GRN → Inventory → Supplier Invoice → Payment → Purchase Return`. Services own state transitions and calculations; repositories own async persistence. Request-scoped transactions make receiving, stock ledger changes, balances, payments and reversals atomic. Document numbers use locked `procurement_sequences` rows.

Legacy procurement totals, discounts and landed charges are calculated by the backend. The PO state machine is `DRAFT → SUBMITTED → APPROVED → SENT → CONFIRMED → PARTIALLY_RECEIVED/RECEIVED → CLOSED`. GRN completion locks the PO, prevents over-receipt, sends accepted and damaged quantities through the inventory ledger and updates weighted costs. Approved supplier invoices increase accounts payable; payments and reversals update invoice and supplier balances together. Purchase returns use compensating stock transactions. Supplier list responses omit bank account details. Supplier performance weights are delivery 45%, quality 35%, and rating 20%.

```bash
alembic upgrade head
python -m app.scripts.seed_owner
python -m app.scripts.seed_procurement
uvicorn app.main:app --reload --port 8000
```

The idempotent seed provides five suppliers, three requests, four POs, three GRNs with partial/damaged receiving, three supplier invoices, two payments, one completed return and imported-order landed costs.

Representative authenticated requests:

```bash
curl -X POST http://localhost:8000/api/v1/suppliers -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"company_name":"Tokyo Demo Imports","display_name":"Tokyo Demo","supplier_type":"IMPORT","country":"Japan","currency_code":"JPY","import_export_code":"IEC-DEMO-1"}'
curl -X POST http://localhost:8000/api/v1/purchase-requests -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"requested_for_warehouse_id":"WAREHOUSE_UUID","preferred_supplier_id":"SUPPLIER_UUID","reason":"Replenishment","items":[{"product_id":"PRODUCT_UUID","requested_quantity":10,"estimated_unit_cost":500}]}'
curl -X POST http://localhost:8000/api/v1/purchase-requests/REQUEST_UUID/submit -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/v1/purchase-requests/REQUEST_UUID/approve -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'
curl -X POST 'http://localhost:8000/api/v1/purchase-requests/REQUEST_UUID/convert-to-po?supplier_id=SUPPLIER_UUID' -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/v1/purchase-orders/PO_UUID/approve -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'
curl -X POST http://localhost:8000/api/v1/grns -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"purchase_order_id":"PO_UUID","items":[{"purchase_order_item_id":"PO_ITEM_UUID","received_quantity":5,"accepted_quantity":4,"damaged_quantity":1}]}'
curl -X POST http://localhost:8000/api/v1/grns/GRN_UUID/complete -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/v1/supplier-invoices -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"supplier_invoice_number":"SUP-001","supplier_id":"SUPPLIER_UUID","invoice_date":"2026-08-06","due_date":"2026-09-05","items":[{"product_id":"PRODUCT_UUID","quantity":5,"unit_cost":500}]}'
curl -X POST http://localhost:8000/api/v1/supplier-payments -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"supplier_id":"SUPPLIER_UUID","supplier_invoice_id":"INVOICE_UUID","payment_method":"BANK_TRANSFER","amount":1000,"reference_number":"NEFT-001"}'
curl -X POST http://localhost:8000/api/v1/purchase-returns -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"supplier_id":"SUPPLIER_UUID","source_warehouse_id":"WAREHOUSE_UUID","reason":"Quality issue","items":[{"inventory_id":"INVENTORY_UUID","quantity":1,"unit_cost":500,"condition":"DAMAGED","reason":"Transit damage"}]}'
```

Swagger at `/api/v1/docs` documents the endpoint contracts. Common errors include `*_STATUS_INVALID`, `GRN_OVER_RECEIPT`, `SUPPLIER_PAYMENT_OVERPAYMENT`, `PROCUREMENT_PRODUCT_INVALID`, and `AUTH_PERMISSION_DENIED`.

# Customer CRM, loyalty and membership

Phase 17 extends the Phase 15 customer, invoice, return and refund source of truth with additive customer profiles, addresses, notes, tags, strict rule segments, communication history, loyalty accounts and immutable transactions, membership history and store-credit ledger entries. `WALK-IN` is stable, unenrolled and retained for anonymous POS sales.

Customer numbers and loyalty transaction numbers use locked database counters. Invoice completion updates order count, lifetime spend and average order value and earns configured loyalty points inside the billing transaction. Loyalty redemption and reversal lock the account and reject negative balances or duplicate reversals. Active membership multipliers influence earning without duplicating billing discount calculations.

The default program earns one point per ₹100 of eligible taxable spending, requires 100 points to redeem, values each point at ₹0.50 and expires earnings after 365 days. All values are configurable. Tiers are Silver, Gold, Platinum and VIP with configurable thresholds and preserved membership history. Communications enforce channel opt-outs except explicitly transactional records.

```bash
alembic upgrade head
python -m app.scripts.seed_owner
python -m app.scripts.seed_crm
```

```bash
curl -X POST http://localhost:8000/api/v1/customers -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"full_name":"Aiko Sharma","mobile":"9898989898","email":"aiko@example.com","loyalty_enrolled":true}'
curl -X POST http://localhost:8000/api/v1/customers/CUSTOMER_UUID/loyalty/adjust -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"points":200,"description":"Service recovery"}'
curl -X POST http://localhost:8000/api/v1/loyalty/redeem -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"customer_id":"CUSTOMER_UUID","points":100}'
curl -X POST http://localhost:8000/api/v1/customers/CUSTOMER_UUID/membership -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"tier_id":"TIER_UUID","reason":"Spend threshold reached"}'
curl -X POST http://localhost:8000/api/v1/sales-returns -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"invoice_id":"INVOICE_UUID","reason":"Changed mind","refund_method":"CASH","items":[{"invoice_item_id":"ITEM_UUID","quantity":1}]}'
curl http://localhost:8000/api/v1/customers/CUSTOMER_UUID/statement -H "Authorization: Bearer $TOKEN"
```

CRM analytics use invoice-derived orders and lifetime value. Retention and inactivity use a 90-day inactivity window. Dashboard insight strings are deterministic and do not call an external AI service. Common errors include `CUSTOMER_MOBILE_EXISTS`, `CUSTOMER_EMAIL_EXISTS`, `LOYALTY_INSUFFICIENT_POINTS`, `LOYALTY_ALREADY_REVERSED`, `MEMBERSHIP_TIER_NOT_FOUND`, and `CUSTOMER_COMMUNICATION_OPT_OUT`.

# Employee and HRMS architecture

Phase 18 adds employee profiles linked one-to-one with existing users, departments, designations, store/warehouse assignments, documents, shifts, attendance, holidays, leave balances and requests, configurable salary components and structures, payroll runs, payslips, performance reviews, goals and tasks. Normal employee responses omit bank accounts, PAN, Aadhaar, UAN and ESI details.

Attendance check-in/out uses server timestamps, authenticated user linkage, one row per employee/day and resolved shift grace/break/overtime rules. Manual attendance requires an administrative permission and reason. Shift assignment history rejects overlapping effective periods.

Leave submission locks the annual balance and reserves pending days. Approval moves pending days to used days; rejection or cancellation releases the reservation. Overlapping requests and negative paid-leave balances are rejected.

Payroll is an attendance-aware foundation rather than a complete statutory Indian payroll engine. It snapshots monthly CTC, period days, payable attendance, paid/unpaid leave, gross deductions and net salary. Calculated runs can be approved and finalized; finalized runs are immutable. Statutory components remain configurable and arbitrary formulas are not evaluated.

```bash
alembic upgrade head
python -m app.scripts.seed_owner
python -m app.scripts.seed_hr
uvicorn app.main:app --reload --port 8000
```

```bash
curl -X POST http://localhost:8000/api/v1/employees -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"first_name":"Aarav","last_name":"Shah","email":"aarav.hr@example.com","phone":"9898000001","joining_date":"2026-08-06","employment_type":"FULL_TIME","store_id":"STORE_UUID"}'
curl -X POST http://localhost:8000/api/v1/employees/EMPLOYEE_UUID/link-user -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"user_id":"USER_UUID"}'
curl -X POST http://localhost:8000/api/v1/attendance/check-in -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'
curl -X POST http://localhost:8000/api/v1/attendance/check-out -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'
curl -X POST http://localhost:8000/api/v1/leave/requests -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"employee_id":"EMPLOYEE_UUID","leave_type_id":"TYPE_UUID","start_date":"2026-09-10","end_date":"2026-09-11","reason":"Family event"}'
curl -X POST http://localhost:8000/api/v1/leave/requests/REQUEST_UUID/approve -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"reason":"Approved"}'
curl -X POST http://localhost:8000/api/v1/payroll/runs -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"period_id":"PERIOD_UUID"}'
curl -X POST http://localhost:8000/api/v1/payroll/runs/RUN_UUID/calculate -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/api/v1/payroll/payslips/PAYSLIP_UUID/pdf -H "Authorization: Bearer $TOKEN" -o payslip.pdf
curl -X POST http://localhost:8000/api/v1/performance/reviews -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"employee_id":"EMPLOYEE_UUID","review_period_start":"2026-01-01","review_period_end":"2026-06-30","attendance_score":90,"sales_score":85,"task_score":88,"customer_feedback_score":92}'
```

Common errors include `EMPLOYEE_DUPLICATE`, `EMPLOYEE_USER_ALREADY_LINKED`, `ATTENDANCE_DUPLICATE_CHECKIN`, `ATTENDANCE_CHECKIN_REQUIRED`, `SHIFT_ASSIGNMENT_OVERLAP`, `LEAVE_OVERLAP`, `LEAVE_BALANCE_INSUFFICIENT`, `PAYROLL_RUN_EXISTS`, and `PAYROLL_STATUS_INVALID`.
# Phase 19 — Reports, BI, Finance and Exports

The reporting layer aggregates live operational records and exposes owner KPIs, sales, inventory, finance, purchase, customer, employee, store, warehouse, payment, return and loyalty report routes under `/api/v1/dashboard` and `/api/v1/reports`. Non-owner users are always constrained to `users.assigned_store_id`; omitting `store_id` never expands their access.

Revenue is the completed-invoice final billed amount. COGS uses inventory cost, gross profit is revenue minus COGS, and estimated operating profit subtracts approved expenses and completed refunds. Inventory valuation uses persisted inventory value.

All presets and custom dates are resolved in the requested IANA business timezone (default `Asia/Kolkata`) and converted to exclusive UTC query boundaries. Supported presets include today, yesterday, current/previous week, month, quarter, and year.

Exports are available through `GET|POST /api/v1/reports/export` in PDF, Excel-readable XML, and UTF-8 BOM CSV. CSV formula prefixes are neutralized. Each export creates a history record. Report schedules support daily, weekly and monthly task-ready definitions and `run-now`; execution can be connected to the deployment scheduler without requiring Celery.

Apply and seed:

```bash
alembic upgrade head
python -m app.scripts.seed_owner
```

Examples:

```bash
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/dashboard/owner?preset=THIS_MONTH&compare_with_previous=true"
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/reports/sales/summary?date_from=2026-08-01&date_to=2026-08-31"
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/reports/finance/profit-loss?preset=THIS_MONTH"
curl -OJ -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/reports/export?report_type=sales_summary&format=PDF"
```

For Swagger, open `/api/v1/docs`, authorize as owner, then demonstrate owner dashboard → store filter → sales/P&L → weekly summary → exports → schedules. Indexes on new date, store, status, and reporting discriminator fields are included in migration `20addf49befe`.
