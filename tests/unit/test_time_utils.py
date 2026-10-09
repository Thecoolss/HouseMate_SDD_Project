from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from flask import Flask

from app.time_utils import format_local_datetime, local_to_utc_naive, utc_to_local


@pytest.fixture()
def household_timezone():
    # A bare Flask app is enough: time_utils only reads HOUSEHOLD_TIMEZONE from current_app.
    app = Flask(__name__)
    app.config["HOUSEHOLD_TIMEZONE"] = "Europe/Paris"
    with app.app_context():
        yield app


@pytest.mark.parametrize(
    ("local_value", "expected_utc"),
    [
        # Summer time (CEST, UTC+2)
        (datetime(2026, 7, 1, 12, 0), datetime(2026, 7, 1, 10, 0)),
        # Winter time (CET, UTC+1)
        (datetime(2026, 1, 15, 12, 0), datetime(2026, 1, 15, 11, 0)),
        # Local evening that falls on the previous UTC day boundary
        (datetime(2026, 7, 2, 0, 30), datetime(2026, 7, 1, 22, 30)),
    ],
)
def test_local_to_utc_naive_converts_household_time(household_timezone, local_value, expected_utc):
    result = local_to_utc_naive(local_value)

    assert result == expected_utc
    assert result.tzinfo is None


def test_local_to_utc_naive_returns_none_for_missing_value(household_timezone):
    assert local_to_utc_naive(None) is None


def test_local_to_utc_naive_converts_aware_values_without_using_household_timezone(household_timezone):
    aware_value = datetime(2026, 7, 1, 12, 0, tzinfo=timezone(timedelta(hours=5)))

    result = local_to_utc_naive(aware_value)

    assert result == datetime(2026, 7, 1, 7, 0)
    assert result.tzinfo is None


def test_local_to_utc_naive_rejects_time_skipped_by_clock_change(household_timezone):
    # Clocks in Europe/Paris jump from 02:00 to 03:00 on 2026-03-29, so 02:30 never exists.
    with pytest.raises(ValueError, match="does not exist"):
        local_to_utc_naive(datetime(2026, 3, 29, 2, 30))


def test_local_to_utc_naive_uses_configured_timezone(household_timezone):
    household_timezone.config["HOUSEHOLD_TIMEZONE"] = "UTC"

    assert local_to_utc_naive(datetime(2026, 7, 1, 12, 0)) == datetime(2026, 7, 1, 12, 0)


def test_utc_to_local_returns_none_for_missing_value(household_timezone):
    assert utc_to_local(None) is None


@pytest.mark.parametrize(
    ("utc_value", "expected_local"),
    [
        (datetime(2026, 7, 1, 10, 0), datetime(2026, 7, 1, 12, 0)),
        (datetime(2026, 1, 15, 11, 0), datetime(2026, 1, 15, 12, 0)),
        (datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc), datetime(2026, 7, 1, 12, 0)),
    ],
)
def test_utc_to_local_converts_to_household_timezone(household_timezone, utc_value, expected_local):
    result = utc_to_local(utc_value)

    assert result.replace(tzinfo=None) == expected_local
    assert result.tzinfo == ZoneInfo("Europe/Paris")


def test_local_and_utc_conversions_round_trip(household_timezone):
    local_value = datetime(2026, 10, 9, 18, 45)

    assert utc_to_local(local_to_utc_naive(local_value)).replace(tzinfo=None) == local_value


def test_format_local_datetime_formats_in_household_timezone(household_timezone):
    assert format_local_datetime(datetime(2026, 7, 1, 10, 0), "%Y-%m-%d %H:%M") == "2026-07-01 12:00"


def test_format_local_datetime_returns_empty_string_for_missing_value(household_timezone):
    assert format_local_datetime(None, "%Y-%m-%d %H:%M") == ""
