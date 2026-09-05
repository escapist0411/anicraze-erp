# ANICRAZE Temporary Online Demo Deployment

This environment is for the pre-client operational demo only. It must use a separate Neon database and simulated communications. It is not the Phase 8 production deployment.

## Architecture

`Netlify HTTPS frontend → Render HTTPS API → Neon PostgreSQL`

The repository contains `netlify.toml` for the Vite build and SPA rewrite, plus `render.yaml` for one Docker web instance and `/health` monitoring. Render runs the current Alembic migration before starting `main:app`. Keep a single instance so migrations cannot race.

## Neon

1. Create a separate Neon project/database named `anicraze_demo`.
2. Copy its pooled PostgreSQL connection string and change the scheme to `postgresql+asyncpg://` if Neon displays `postgresql://`.
3. Preserve Neon's required SSL parameters in the URL.
4. Set this URL only as Render's `DATABASE_URL`; never commit it.
5. From a trusted shell using the demo environment, run `alembic upgrade head` and verify `alembic current` reports `20260831_0015`.

The demo pool is intentionally small: `DATABASE_POOL_SIZE=3`, `DATABASE_MAX_OVERFLOW=2`, with connection recycling and pre-ping enabled.

## Render backend

Create a Blueprint from `render.yaml` or an equivalent Docker service rooted at `backend`. Configure:

```text
APP_ENV=demo
DATABASE_URL=<Neon pooled asyncpg URL>
SECRET_KEY=<random value of at least 32 characters>
CORS_ORIGINS=https://<exact-netlify-domain>
FRONTEND_URL=https://<exact-netlify-domain>
REDIS_ENABLED=false
WHATSAPP_ENABLED=false
WHATSAPP_PROVIDER=development
MAIL_ENABLED=false
MULTI_WAREHOUSE_ENABLED=false
DATABASE_POOL_SIZE=3
DATABASE_MAX_OVERFLOW=2
DEMO_OWNER_PASSWORD=<temporary strong password, 12+ characters>
DEMO_EMPLOYEE_PASSWORD=<temporary strong password, 12+ characters>
DEMO_MANAGER_PASSWORD=<temporary strong password, 12+ characters>
```

Do not configure Meta, SMTP, payment-gateway, or production credentials. After the first deploy, run the seed command from a Render shell:

```bash
PYTHONPATH=. python -m app.scripts.seed_demo
```

Run it twice: each run must report the same three users, one store, one warehouse, nine products, and 18 zero-stock location rows. It updates demo passwords from the environment without duplicating records.

Health check: `https://<render-domain>/health` must return `{"status":"ok"}`.

## Netlify frontend

Netlify uses base directory `frontend`, build command `npm run build`, and publish directory `dist`. Configure one public variable:

```text
VITE_API_URL=https://<render-domain>
```

`VITE_API_URL` is normalized to the existing `/api/v1` API. Do not put database, JWT, WhatsApp, mail, or password values in any `VITE_*` variable. The SPA rewrite in `netlify.toml` supports refreshes on `/owner/*` and `/employee/*` routes.

After the final Netlify URL is known, update Render's `CORS_ORIGINS` and `FRONTEND_URL` to that exact HTTPS origin and redeploy the API.

## Demo identities and locations

- Owner: `owner.demo@anicraze.in` (`OWNER`)
- Employee: `employee.demo@anicraze.in` (`SALES`), assigned to ANICRAZE Demo Shop
- Store manager: `manager.demo@anicraze.in` (`MANAGER`), assigned to ANICRAZE Demo Shop; needed for the existing transfer-receiving permission
- Store: ANICRAZE Demo Shop
- Warehouse: ANICRAZE Central Warehouse

Passwords exist only in Render environment variables. The nine selected final-catalog products are Naruto Rasengan, Kakashi Chidori, Tanjiro Standing, Luffy Sitting — Variant 1, Gojo Standing — Variant 1, Qposket Elsa, Rubber Keychain, UNO No Mercy, and Katana. Seeded inventory is zero at both locations; costs enter only through genuine receiving.

## Safe reset

Only against the isolated demo database:

```bash
APP_ENV=demo PYTHONPATH=. python -m app.scripts.reset_demo
```

The command refuses any environment other than `demo`. It clears operational demo transactions, sessions, customers, invoices, payments, returns, procurement, transfers, ledger entries, notifications, reports, and audits; resets inventory quantities/costs to zero; then restores the idempotent demo seed. It preserves migrations, final product/category/series masters, roles, users, the demo store, and the warehouse.

## iPhone scanner

The POS scanner uses ZXing's cross-browser multi-format reader instead of depending on native `BarcodeDetector`. It requests `{facingMode: {ideal: "environment"}}`, falls back to `video: true`, and never requires a device ID or pre-permission camera label. The video uses `muted`, `autoPlay`, and `playsInline`.

Camera startup follows a user tap on **Open camera / Start scanner**. Denial shows the required permission message and a **Try again** action. Barcode/SKU/product search remains available. Closing the scanner, navigating away, or unmounting stops scanner controls and every media track. Mobile sheets and fixed checkout controls include iPhone safe-area padding.

Test on the deployed HTTPS URL—not a LAN HTTP address. Safari: open the POS, tap Scan, allow camera, confirm rear camera, scan Code128, close and reopen. If denied, use Safari site settings or Settings → Safari → Camera. Repeat in Chrome on iOS, remembering it also uses WebKit. Test EAN-13, manual input, duplicate scan, unknown input, poor light, denial, close, and reopen.

## Manual end-to-end run

1. Run the reset command and confirm both locations are zero.
2. Owner logs in, searches Naruto Rasengan, and confirms ₹800.
3. Use existing procurement/GRN or receiving to receive 10 at ₹400 and another 10 at ₹440. Confirm warehouse quantity 20, average cost ₹420, and selling price unchanged.
4. Generate Naruto's internal Code128 in Barcode Centre; verify persistence, lookup, display, download, and print.
5. Create a multi-product transfer to ANICRAZE Demo Shop: Naruto 5, Tanjiro 3, Gojo Variant 1 quantity 2. Submit, approve, pick, pack, and dispatch without skipping existing states.
6. Manager logs in, receives all quantities, and confirms COMPLETED plus shop quantities 5/3/2.
7. Employee logs in on iPhone, scans Naruto twice, adds Tanjiro once, creates Demo Customer with a clearly fictional number, selects UPI, and completes the invoice.
8. Verify invoice/PDF and database state: Naruto 3 and Tanjiro 2; exactly one invoice/payment/communication/loyalty action and matching SALE movements.
9. Owner verifies dashboard, finance, inventory, customer history, payment breakdown, notification, and weekly/manual report data.
10. Create a second transfer and receive one item short; confirm DISCREPANCY and the owner notification.
11. Create a cash invoice and verify change, then a split Cash + UPI invoice and exact payment total enforcement.
12. During an additional POS attempt, disable networking before submit. Confirm no success is shown, reconnect, retry with the same idempotency key, and confirm only one invoice.

The purchase-cost examples are demo costs, not product-master values. Never insert them through the seed or overwrite selling prices.

## PostgreSQL acceptance checks

After the manual flow inspect products, inventory, inventory transactions/ledger, reservations, transfers/items, invoices/items, payments, customers, loyalty transactions, communications, notifications, report history, and audit logs. For the first sale confirm one invoice, correct item/payment rows, one SALE movement per item, one stock decrement, no duplicate loyalty earn, and no duplicate communication.

## Operational limitations

- Free Render services may sleep; open `/health` before the meeting and wait for `ok` before starting.
- Render's local filesystem is ephemeral. Generated invoices, barcodes, and reports may disappear after a restart/redeploy. This is acceptable only for this temporary demo; production requires persistent object storage.
- Camera permission and physical barcode reading must be verified on the developer's real iPhone after deployment.
- No PWA is added or required.
- The existing Vite bundle-size warning remains.
