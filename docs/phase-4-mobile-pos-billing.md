# Phase 4 — Mobile Shop POS and Billing

The current POS reuses the shared billing, inventory, CRM, payment, return/refund and branded PDF services. The mobile UI is mounted at `/{role}/pos` and invoice history at `/{role}/invoices`; permissions determine visibility and backend access.

The authenticated profile supplies `assigned_store_id`. Employees do not receive a shop picker. Product search, barcode lookup, invoice access, PDF download, cancellation and return are scoped to the authenticated employee's assigned store. Owners and administrators may select an authorized operating store.

Cash, UPI, card and split payments are recorded. The backend uses catalogue prices, applies discounts and calculates the final billed total. Payment components must exactly settle that total. Browser and PDF invoices display Subtotal, Discount and Total only.

Returns enforce cumulative quantities against the source invoice, restore inventory through the ledger, and refund the actual amount attributable to the returned sold line.
