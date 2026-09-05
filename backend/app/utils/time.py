from datetime import UTC, datetime, timedelta


def utc_now() -> datetime:
    return datetime.now(UTC)


def after_minutes(minutes: int) -> datetime:
    return utc_now() + timedelta(minutes=minutes)


def after_days(days: int) -> datetime:
    return utc_now() + timedelta(days=days)
