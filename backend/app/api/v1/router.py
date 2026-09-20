from fastapi import APIRouter

from app.api.v1 import auth, billing, catalog, crm, health, hr, inventory, management, notifications, payables, procurement, reports

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(management.router)
api_router.include_router(catalog.router)
api_router.include_router(inventory.router)
api_router.include_router(crm.router)
api_router.include_router(billing.router)
api_router.include_router(procurement.router)
api_router.include_router(hr.router)
api_router.include_router(reports.dashboard_router)
api_router.include_router(reports.reports_router)
api_router.include_router(reports.expenses_router)
api_router.include_router(reports.schedules_router)
api_router.include_router(notifications.router)
api_router.include_router(payables.router)
