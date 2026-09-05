# Phase 6 — Owner Command Center, Finance, GST and BI

## Delivered

- Owner/management command center backed by live PostgreSQL aggregates.
- Date preset, custom date, timezone, store and warehouse-aware reporting foundation.
- GST-exclusive taxable sales, completed-return adjustment, net GST, estimated COGS,
  gross profit, approved expenses and estimated operating profit.
- Inventory valuation and health, shop/godown/in-transit distribution, store ranking,
  top products, payment-method mix, attendance, alerts and deterministic insights.
- CSV, PDF and Excel-readable SpreadsheetML exports with export history and audit logs.
- Weekly business summary and report schedule CRUD/run-now APIs.
- Store-scoped reporting and expense mutations. Owner reports and exports enforce the
  requested domain permission; operational employees cannot access management finance.
- Responsive management dashboard with explicit financial definitions and a safe
  non-financial employee landing page.

## Financial definitions

- **Net sales:** invoice taxable amount (GST excluded), less the taxable portion of
  completed returns in the selected period.
- **COGS:** sold quantity at the inventory record's current moving-average cost, less
  returned quantity at that cost.
- **Gross profit:** net sales less estimated COGS.
- **Estimated operating profit:** gross profit less approved expenses. It is deliberately
  not labelled accounting net profit because payroll, depreciation, interest and income
  tax are excluded unless entered as approved expenses.
- **GST collected:** invoice GST less the GST portion of completed returns.
- **Inventory value:** current quantities valued at current average cost.

## Known accounting boundary

Invoice items do not currently store an immutable cost-at-sale snapshot. Historical COGS
therefore uses the inventory row's current moving-average cost. For audited accounting,
add an immutable `unit_cost_at_sale` to invoice items and post inventory/finance journal
entries. Report schedules record timing and support manual execution; external email or
WhatsApp delivery still requires a configured worker and provider.

## Verification

- Backend contract suite: 63 tests passed.
- Frontend TypeScript and production Vite build passed.
- PostgreSQL reconciliation for the current sample period: taxable sales ₹1,847.00,
  completed return ₹118.00 (₹100 taxable), net sales ₹1,747.00, net GST ₹126.35,
  estimated COGS ₹6,130.00 and estimated operating profit -₹4,383.00.
- Payment reconciliation: UPI ₹1,586.00 (79.70%), cash ₹404.00 (20.30%).

The negative sample margin reflects seeded inventory average costs and is intentionally
shown rather than hidden or converted into a mock positive KPI.
