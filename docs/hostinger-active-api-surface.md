# Hostinger PHP active API surface (implementation triage)

## Phase 5C final machine gate (local, 5 October 2026)

`cd frontend && npm run check:hostinger-parity` recursively walks the current React route imports, resolves reachable service calls (including CRUD helpers), scans direct HTTP calls, and compares method/path pairs against registered PHP routes. `--list` emits the complete caller/file evidence. Final result: **64 active patterns, 64 registered PHP patterns, 0 missing**. The count increased by one because the completed password-reset screen adds its required reset submission. Refresh rotation is additionally covered as a required internal route.

The closure pass implemented stock-PDF preview extraction, signed short-lived password reset with one-use token-version invalidation and private rate limiting, a reset screen, and Owner-only environment-configured report schedule list/run-now with private PDF storage. No schema migration was added.

Current PHP additions include Owner-only product create/update/archive, canonical new-product SKU/barcode allocation, image upload and CSV import, inventory corrections, supplier/payable handling, notifications, account directory, dashboards, report exports and the four closure routes. Existing 160 product barcodes were preserved. The complete available PHP integration suite passed **232 checks with 0 failures**.

The route gate proves registration, while the integration suite proves service contracts, role boundaries, shop isolation, concurrency and document behavior. The actual React production build was also walked in Chrome against local PHP/MariaDB for Owner, Manager and ELPRO, with no visible API failure on current role-reachable pages. Expense and general return modules have no current reachable frontend HTTP call; the active Owner invoice-cancellation flow is implemented and tested atomically.

This is a source-based triage of the current React routes and their imported pages/components/services, not a claim of PHP parity. The full 232-route reference contract remains in [the machine-readable inventory](php-migration-api-contract.json). **UNCERTAIN stays fail-closed until a caller or approved workflow is proved.** A service declaration alone is not proof that a UI uses it.

| Current UI/workflow | Directly observed API groups | Classification |
| --- | --- | --- |
| Login/session, protected routes | `/auth/login`, `/auth/me`, `/auth/refresh`, `/auth/logout`; forgot-password page uses `/auth/forgot-password` | ACTIVE_FRONTEND |
| Owner/manager Products, categories, import, labels | `/products`, `/products/{id}`, barcode/SKU search and barcode endpoint, product image/import/export, `/categories`, `/anime` | ACTIVE_FRONTEND (individual actions need parity cases) |
| Employee shop products/POS | `/billing/search`, `/billing/barcode/{barcode}`, `/billing/products`, `/billing`, `/invoices`, detail/cancel/PDF | ACTIVE_FRONTEND |
| Inward/Scan to Godown | `/stock-receipts`, supplier list, detail/scan/finalize, PDF preview import | ACTIVE_FRONTEND |
| Inventory/outward | `/inventory`, detail/transactions/ledger, stores/warehouses, stock reports/export, `/stock-transfers/direct`, list/detail/receipt | ACTIVE_FRONTEND |
| Owner reports/finance | `/reports/{domain}/{report}`, report export/weekly summary/targets/schedules, `/expenses`, dashboard | ACTIVE_FRONTEND |
| Owner purchase payments | `/purchase-payables`, summary, payment/reminder endpoints, supplier list | ACTIVE_FRONTEND |
| Notifications and POS WhatsApp status (disabled) | notifications list/summary/read and invoice communication/settings endpoints | ACTIVE_FRONTEND; Meta send remains disabled |
| Current `InventoryCommandCenterV2` | GRN/procurement service calls are reachable via the active Inventory route | ACTIVE_FRONTEND **despite** superseded business process; requires review with client before de-scoping |
| Historical HR/payroll/leave/performance, general CRM/loyalty, legacy transfer approval/pick/receive | Some modules/pages still exist; exact route reachability and approved status have not been fully resolved | UNCERTAIN, **not proven LEGACY_UNUSED** |
| Internal DB/session/role grants, stock locks/idempotency, authorization, private-file checks | No direct frontend call | REQUIRED_BACKEND_DEPENDENCY |

Unknown or unported paths continue to fail closed. The 232-route FastAPI inventory remains rollback/reference material; it is not the Hostinger candidate runtime surface.
