# Production action audit

Last verified: 2026-08-07

## Contract

Every visible control on a routed production page must do one of the following: navigate to a real route, execute a real API/client operation with feedback, submit a validated form, or be disabled with a visible/native-tooltip reason. Unsupported features are not represented by enabled controls. Mutations remain protected by backend permissions; the frontend permission helper is only a presentation layer.

## Routed surfaces

| Surface | Control | Result | Status |
|---|---|---|---|
| Login | Sign in | Validated login request, loading lock, API error, role redirect | Working |
| Login | Forgot password | Validates entered email and calls `/auth/forgot-password` with neutral success feedback | Working |
| Login | Password visibility | Toggles the password field and accessible label | Working |
| Global navigation | Sidebar links/mobile menu/logout/theme | Navigate, close drawer, revoke session, or toggle persisted theme | Working |
| Global navigation | Notification bell | Navigates to the current role's notifications route | Working |
| Global navigation | Search | Disabled with deployment explanation | Explicitly unavailable |
| Dashboard | Products / reports | Navigate to the real role-scoped routes | Working |
| Dashboard | Create invoice | Disabled with deployment explanation | Explicitly unavailable |
| Dashboard | Retry | Re-runs failed dashboard query | Working |
| Inventory | Search/filter/sort/pagination/selection | Updates query/view state and visible result set | Working |
| Inventory | Refresh/retry | Invalidates or re-runs server queries | Working |
| Inventory | CSV export | Downloads current authorized inventory results | Working |
| Inventory | Barcode view/download/print | Uses backend barcode assets and browser download/print | Working |
| Inventory | Stock audit / label PDF | Disabled or explanatory UI where backend capability is absent | Explicitly unavailable |
| Products | Catalogue controls and retry | Filter/detail interaction or query retry | Working |
| Products | Add product | Permission-aware validated modal, real create API, optional image upload, catalogue refresh and details handoff | Working |
| Products | Product row / view details | Loads the complete product master in a responsive details dialog | Working |
| Categories | Retry | Re-runs failed category query | Working |
| Suppliers | Retry | Re-runs failed supplier query | Working |
| Analytics / Finance | Live query and retry controls | Server-backed dashboard/report refresh | Working |
| Reports | Report/period selectors and refresh | Re-fetch selected server report | Working |
| Reports | PDF/XLSX/CSV | Authenticated download with busy lock and feedback | Working |
| Reports | Print | Opens the browser print workflow | Working |
| Stores | Retry | Re-fetches stores and warehouses | Working |
| Stores | Add store | Disabled with deployment explanation | Explicitly unavailable |
| Employees | CSV export | Generates and downloads the loaded authorized directory | Working |
| Employees | Retry | Re-runs employee query | Working |
| Employees | Add employee | Disabled with deployment explanation | Explicitly unavailable |
| Notifications | Retry | Re-runs alert query | Working |
| Settings | Informational cards | No false edit affordances are rendered | Working |

## Legacy/unrouted UI

The repository contains prototype component groups for POS/billing, customer CRM, procurement, transfers, warehouse operations, HR operations, and older report/inventory dashboards. They are not imported by the production route table and contain mock data or prototype controls. They must not be mounted without a separate API wiring and action audit. Their presence is tracked as technical debt, not as a deployable feature.

## Verification

- Frontend TypeScript and production bundle: `npm run build`
- Backend regression suite: `backend/.venv/bin/pytest`
- Manual browser smoke targets: login, dashboard, inventory, reports, stores, employees, notifications, settings at desktop and mobile widths.

Known build advisory: the current main bundle exceeds Vite's 500 kB advisory threshold. This is a performance follow-up, not an action-integrity failure.
