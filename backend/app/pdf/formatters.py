"""Display formatting only; never changes accounting values."""
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

BUSINESS_ZONE = ZoneInfo("Asia/Kolkata")


def format_number(value, places=None):
    if value is None:
        return "-"
    number = Decimal(str(value))
    if places is not None:
        number = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    raw = format(abs(number), "f")
    whole, _, fraction = raw.partition(".")
    if places is None:
        fraction = fraction.rstrip("0")
    tail, head = whole[-3:], whole[:-3]
    groups = []
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    grouped = ",".join([*groups, tail])
    return ("-" if number < 0 else "") + grouped + ("." + fraction if fraction else "")


def format_currency(value):
    if value is None:
        return "-"
    number = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return ("-" if number < 0 else "") + "₹" + format_number(abs(number), 0 if number == number.to_integral() else 2)


def format_percentage(value):
    return "-" if value is None else format_number(value, 1) + "%"


def format_date(value):
    if not value:
        return "-"
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00")) if "T" in value else date.fromisoformat(value)
    if isinstance(value, datetime):
        value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        value = value.astimezone(BUSINESS_ZONE)
    return value.strftime("%d %b %Y")


def format_datetime(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return value.astimezone(BUSINESS_ZONE).strftime("%d %b %Y, %I:%M %p")
