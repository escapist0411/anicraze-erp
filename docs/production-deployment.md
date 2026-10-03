# ANICRAZE production deployment plan (not executed)

Target domains: `anicraze.com` public website; `erp.anicraze.com` static ERP; `api.anicraze.com` FastAPI; separate production PostgreSQL. Existing Netlify/Render/Neon demo remains untouched until a signed-off cutover and rollback window.

## Hosting fit

The purchased Hostinger **Unlimited Web Hosting** plan can be considered for the static public website and built Vite ERP, subject to HTTPS, custom subdomains and SPA rewrite support. It must **not** be assumed to run the Python 3.13/Uvicorn/FastAPI backend as a durable long-running service. The safe current recommendation is public site on Hostinger, ERP on suitable static hosting (Hostinger only if SPA behavior is verified, otherwise Netlify or equivalent), API on Render or another Python/container-capable service, and PostgreSQL on Neon or another managed PostgreSQL service. Do not purchase/configure anything in this phase.

## Demo vs production

`render.yaml` is explicitly demo-only: `APP_ENV=demo` and `dockerCommand` includes `alembic upgrade head`. Never apply it as production configuration. `backend/Dockerfile`'s default command **only starts Uvicorn**, with no migration. A production service should use that command (or equivalent) after an explicit migration release step:

1. Verify target database name, host and backup; never target `anicraze_demo` or `neondb` for final production.
2. Back up and restore-test database and storage on an isolated clone.
3. Run `alembic upgrade 20260921_0020` **once**, with a separately authorized production identity and reviewed migration plan; verify `alembic current`/`heads` match.
4. Run the guarded `scripts/bootstrap_production_users.py` only after setting the exact production DB name twice (`ANICRAZE_PRODUCTION_DATABASE`, `ANICRAZE_CONFIRM_DATABASE`). It creates missing locations/accounts only; existing users are verified and untouched. Supply secrets only for missing accounts through a secure backend environment/ignored file. Rehearse first on an isolated DB.
5. Start the API process without a migration command, verify `/health`, auth, shop-scoped endpoints and private-file retrieval. Deploy/rebuild the ERP only after the API TLS hostname and CORS are correct.

No new production database, DNS record or deployment was created in Phase 3.

## Backend production variables (names and safe examples only)

`APP_ENV=production` (or `ENVIRONMENT=production`), `DEBUG=false`, `DATABASE_URL=<secret asyncpg-compatible PostgreSQL URL with TLS>`, `SECRET_KEY=<secret of at least 32 characters>`, `CORS_ORIGINS=https://erp.anicraze.com`, `FRONTEND_URL=https://erp.anicraze.com`, `STORAGE_BACKEND=volume`, `STORAGE_ROOT=<absolute mounted persistent path>`, `WHATSAPP_ENABLED=false`, `WHATSAPP_PROVIDER=development`, `MAIL_ENABLED=false`, `EXPOSE_DEV_RESET_TOKEN=false`, `ENABLE_AUTH_TEST_ROUTES=false`, bounded `DATABASE_POOL_SIZE`/`DATABASE_MAX_OVERFLOW`, and `REDIS_ENABLED`/`REDIS_URL` according to the chosen topology. Set `PORT` according to host requirements. Do not use wildcard CORS. Backend secrets belong only in the backend secret store.

The production bootstrap also requires `ANICRAZE_PRODUCTION_DATABASE=<verified non-demo database name>` and `ANICRAZE_CONFIRM_DATABASE=<same name>` **only during provisioning**, plus passwords for missing accounts from secure environment variables. It does not log them or replace existing passwords. Never copy these values into Vite or Git.

## ERP static build

Set `VITE_API_URL=https://api.anicraze.com/api/v1` in the production build environment; the build now fails if it is absent, non-HTTPS or loopback. Vite embeds public variables into the bundle, so rebuild after changes. Publish `frontend/dist`, serve over HTTPS, and rewrite unknown client routes to `index.html` (Netlify's current `/* /index.html 200` behavior). Do not place DB/JWT/SMTP/Meta secrets in `VITE_*` variables.

## Release and rollback gates

Require automated tests, two-shop isolation acceptance, PDF/file restore drill, label-printer acceptance, backups, migration rehearsal and a deployment-specific health check before DNS switch. Keep old Netlify/Render/Neon online. Rollback must pair application image with compatible database schema and document files; reconcile any sales written after cutover. Do not auto-run Alembic on every API startup.
