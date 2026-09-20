from app.config.settings import get_settings
from app.main import app
from app.models.notifications import Notification, NotificationCategory, NotificationSeverity


def test_phase7_notification_routes_are_registered():
    paths={route.path for route in app.routes}
    assert {"/api/v1/notifications","/api/v1/notifications/summary","/api/v1/notifications/{id}/read","/api/v1/notifications/mark-all-read","/api/v1/reports/history/{id}/download"} <= paths


def test_notification_model_has_stable_per_user_deduplication():
    constraints={constraint.name for constraint in Notification.__table__.constraints}
    assert "uq_notification_user_dedupe" in constraints


def test_phase7_uses_small_consistent_taxonomy_and_configured_threshold():
    assert {x.value for x in NotificationSeverity} == {"INFO","WARNING","HIGH","CRITICAL"}
    assert {x.value for x in NotificationCategory} == {"INVENTORY","TRANSFER","PROCUREMENT","PAYMENT","COMMUNICATION","REPORT","SYSTEM"}
    assert get_settings().large_stock_adjustment_threshold > 0
