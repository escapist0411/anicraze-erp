# Phase 7 — Operational Alerts, Notifications and Owner Reporting

## Delivered

- A single persisted notification source with per-user stable deduplication, read state,
  resolution state, severity, category, source entity and actionable route.
- Reconciliation of existing live ERP conditions: low/out-of-stock, transfer discrepancy,
  aggregated transfer approval queue, failed WhatsApp invoices, submitted purchase orders,
  and stock adjustments exceeding `LARGE_STOCK_ADJUSTMENT_THRESHOLD`.
- Resolved source conditions automatically resolve their corresponding active notification.
- Real header unread badge and recent-notification panel.
- Responsive Notification Center with All, Unread, Inventory, Transfers,
  Communications and Reports filters; mark-read and mark-all-read actions.
- Phase 6 dashboard alerts now consume the same notification source.
- Existing report schedule `run-now` now generates and stores an authoritative weekly PDF,
  records export history, attempts configured email delivery, records every recipient attempt,
  and creates report-ready or report-failed notifications.
- Predictable weekly filename such as
  `ANICRAZE_Weekly_Report_24-30_Aug_2026.pdf`.
- SMTP configuration through environment variables only. A disabled/missing mail provider does
  not invalidate a successfully generated report.
- Reports UI shows configured schedules and exposes **Generate & send now** with separate
  report and email status.

## Deployment boundary

No production schedule was invented. There are currently zero configured report schedules.
Owner/Admin must configure day, time, timezone and recipients. Phase 8 must connect the
existing due-schedule job entry point to the production scheduler. `MAIL_ENABLED` defaults to
false; SMTP credentials and the intended recipient must be configured before email delivery.

## Verification

- PostgreSQL schema upgraded to `20260831_0015`.
- 66 backend tests pass.
- Python module compilation passes.
- Frontend TypeScript and production Vite build pass.
- Live reconciliation created two current owner notifications from real data: one inventory
  warning and one failed invoice communication. Both are unread and deduplicated.
- In-app responsive browser verification could not start because the browser integration
  failed during initialization. No visual pass is claimed.

The existing Vite bundle-size warning remains for Phase 8 code splitting; it does not fail the
production build.
