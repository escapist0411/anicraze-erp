# Phase 4 — Mobile Shop POS, Billing and GST Invoice

## Architecture

Phase 4 reuses the existing `BillingService`, billing repository, GST calculator, invoice sequence, payment, cash-register, return/refund, inventory movement, CRM integration and ReportLab invoice PDF. The shared mobile UI is mounted at `/{role}/pos` and invoice history at `/{role}/invoices`; permissions determine visibility and backend access.

## Employee shop resolution and security

The authenticated profile supplies `assigned_store_id`. Employees do not receive a shop picker. Every product search, barcode lookup, invoice, invoice detail/PDF, cancellation and return is checked against the backend actor assignment. Owners/admins without an assignment can select an authorized operating store. POS responses expose selling price, GST and available shop quantity only—not cost, valuation or margin.

## Scan, cart and checkout

The Phase 3 `BarcodeScanner` is reused. It prefers the rear camera, debounces reads, releases media tracks and retains manual/USB input. Lookups query only shop inventory. Repeated scans merge quantity and cannot exceed `available_quantity`. Customer search/create and walk-in checkout use real billing-customer APIs.

Cash, UPI, card and cash+UPI split payments are recorded. UPI/card references are records only and are not represented as bank verification. The UI previews GST, while the backend uses catalogue prices and calculates authoritative GST, discounts, rounding and totals. Payment components must exactly settle the invoice.

## Transaction, concurrency and idempotency

`BillingService.create` validates actor/store/customer, locks inventory rows, verifies active products and shop availability, rejects browser price changes, creates the invoice/items/taxes/payments, writes SALE inventory movements and updates CRM in the request transaction. The unique `invoices.idempotency_key` makes mobile retries return the original invoice without another payment or stock deduction. Row locks prevent concurrent overselling.

PDF generation is attempted after business records have been prepared; PDF failure is caught so it does not invalidate a completed sale. The PDF endpoint remains authenticated and store-scoped. Invoice history uses mobile cards and desktop tables; detail supports authenticated PDF download, browser print and permission-controlled cancellation. Existing return/refund APIs remain in the billing domain and are store-scoped.

## APIs reused

- `POST /billing`
- `GET /billing/search`, `GET /billing/barcode/{barcode}`
- `GET /invoices`, `GET /invoices/{id}`, `GET /invoices/{id}/pdf`
- `POST /invoices/{id}/cancel`
- `GET/POST /returns`, `GET /refunds`
- `GET /stores`, `GET /auth/me`

Added: `GET/POST /billing/customers`. Existing billing search, invoice and PDF routes were tightened for assigned-store scope.

## Migration

`20260831_0013_invoice_idempotency` adds the essential unique invoice idempotency key. Existing invoices are backfilled with stable `legacy:<uuid>` keys.

## PostgreSQL verification

Employee `sales@anicraze.com` was assigned to Nexus Ahmedabad One. Barcode `8901234567012` resolved to the correct shop product with 41 available. UPI invoice `ANI-INV-000005` completed for INR 471, shop availability moved 41 → 40, exactly one SALE movement and one payment were written, repeating the same idempotency key returned the same invoice, cross-store lookup returned 403, and the authenticated PDF endpoint returned a non-empty 2,981-byte PDF.

## Phase 5 handoff and limitations

Completed invoices provide invoice ID/number, customer/mobile, store, amount, status, payments and PDF. The WhatsApp action is intentionally disabled for Phase 5; billing never depends on communications. Payment modes are recorded, not gateway-verified. The existing application bundle-size advisory remains. Live visual viewport verification depends on the in-app browser connection.
