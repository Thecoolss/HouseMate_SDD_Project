from datetime import timezone
from zoneinfo import ZoneInfo

from flask import current_app


def local_to_utc_naive(value):
    if value is None:
        return None

    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    local_zone = ZoneInfo(current_app.config["HOUSEHOLD_TIMEZONE"])
    local_value = value.replace(tzinfo=local_zone)
    utc_value = local_value.astimezone(timezone.utc)
    if utc_value.astimezone(local_zone).replace(tzinfo=None) != value:
        raise ValueError("That local time does not exist because of a clock change.")
    return utc_value.replace(tzinfo=None)


def utc_to_local(value):
    if value is None:
        return None
    local_zone = ZoneInfo(current_app.config["HOUSEHOLD_TIMEZONE"])
    utc_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return utc_value.astimezone(local_zone)


def format_local_datetime(value, format_string):
    local_value = utc_to_local(value)
    return local_value.strftime(format_string) if local_value is not None else ""
