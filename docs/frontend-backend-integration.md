# Frontend–backend integration

The React application uses one Axios instance in `src/services/api.ts`. Its base URL is `VITE_API_BASE_URL`; local defaults belong in `.env`, while `.env.example` is the shareable template. No credentials or tokens belong in environment files.

## Authentication

Login posts to `/auth/login`. The returned roles and permissions are retained verbatim; the UI role is only a route-family adapter. Persistent sessions use local storage when “remember me” is selected and browser session storage otherwise. On startup `/auth/me` verifies the session. A single shared refresh promise rotates tokens after a 401 and queues concurrent failed requests; each request retries at most once. Refresh failure clears both stores and emits a session-expired event.

Navigation should test `user.permissions` (with `*` support) and `user.roles`; hiding an item is convenience only because FastAPI remains authoritative. Non-owner store scope always comes from the backend.

## Services and query keys

Domain services live under `src/services`; all unwrap the common `{ success, data, message }` envelope. `query-keys.ts` provides stable auth, dashboard, product, inventory, billing, CRM, procurement, HR, report, and location keys. Reads retry once and cache by filter object. Mutations should invalidate:

| Mutation | Invalidate |
|---|---|
| Product create/update | products, catalog, dashboard |
| Stock movement/transfer | inventory, products, dashboard, inventory reports |
| Invoice completion | billing, inventory, products, dashboard, reports, customer, loyalty |
| GRN completion | procurement, inventory, products, dashboard, supplier |
| Attendance check-in | attendance, employee, HR dashboard, owner dashboard |
| Customer return | returns, refunds, inventory, invoice, customer, loyalty, dashboard, reports |

## Errors, files, money, and dates

`ApiError` normalizes network and backend errors; forms can use `mapValidationErrors`. Never display stack traces. `downloadFile` requests Blob data and honors the backend filename instead of parsing files as JSON. Monetary values stay as strings until display and use `formatCurrency`; backend totals remain authoritative. Dates display in `Asia/Kolkata` while API timestamps remain ISO/UTC.

## Development

```bash
cd backend && .venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

Local demo accounts are opt-in and their passwords come from uncommitted `LOCAL_*_PASSWORD` environment variables. Demo hints remain disabled unless `VITE_SHOW_DEMO_CREDENTIALS=true`.

## Integration checklist

- [x] Central environment and API client
- [x] Login, refresh queue, logout, reload restoration, current profile
- [x] Live owner dashboard and live product/inventory listing
- [x] Typed service gateways for catalog, inventory, billing, CRM, procurement, HR, reports, stores, and warehouses
- [x] Error normalization and Blob/multipart helpers
- [ ] Replace the remaining presentation-only arrays in secondary module widgets
- [ ] Wire all existing create/edit forms and state-transition buttons to their service mutations
- [ ] Add route-level lazy loading and an automated browser E2E suite

Common failures: confirm FastAPI is on port 8000, `VITE_API_BASE_URL` includes `/api/v1`, the database migration is at head, and the user role has the relevant backend permission.
