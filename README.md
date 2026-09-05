# Anicraze ERP

Anicraze ERP is a multi-module business system for inventory, warehouse operations, and administration.

## Repository structure
- frontend/: React + TypeScript + Tailwind
- backend/: FastAPI services
- desktop-app/: Warehouse desktop application (future)
- database/: SQL schema, seed data, and migrations
- docs/: Project documentation
- assets/: Logos, icons, and images
- docker/: Container configuration

## Status
Project scaffolding has been initialized.
# ANICRAZE ERP local development

```bash
cd backend && .venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

The frontend reads `VITE_API_BASE_URL` from `frontend/.env`. See `docs/frontend-backend-integration.md` for authentication, refresh, query-cache, file-download, and module integration details.

## Demo deployment

The temporary pre-client demo uses Netlify for the frontend, Render for the FastAPI backend, and a separate Neon PostgreSQL database. See [docs/demo-deployment.md](docs/demo-deployment.md) for environment variables, migrations, safe demo seed/reset commands, iPhone testing, and known limitations. Never commit provider credentials or demo passwords.
