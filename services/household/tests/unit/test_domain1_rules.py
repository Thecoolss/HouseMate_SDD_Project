from datetime import datetime, timedelta

import pytest

from app.domain1.rules import (
    validate_booking,
    validate_difficulty,
    validate_title,
)


@pytest.mark.parametrize(
    ("title", "expected"),
    [(" Wash dishes ", "Wash dishes"), ("Vacuum", "Vacuum")],
)
def test_validate_title_returns_trimmed_title(title, expected):
    assert validate_title(title) == expected


@pytest.mark.parametrize("title", ["", "  ", None, 123])
def test_validate_title_rejects_empty_or_non_string_values(title):
    with pytest.raises(ValueError, match="Task title is required"):
        validate_title(title)


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_validate_difficulty_accepts_supported_values(difficulty):
    validate_difficulty(difficulty)


@pytest.mark.parametrize("difficulty", ["impossible", "", None])
def test_validate_difficulty_rejects_unsupported_values(difficulty):
    with pytest.raises(ValueError, match="Difficulty must be"):
        validate_difficulty(difficulty)


def test_validate_booking_returns_trimmed_valid_resource():
    start_time = datetime(2026, 10, 2, 9)

    assert validate_booking(
        " laundry ",
        start_time,
        start_time + timedelta(hours=1),
    ) == "laundry"


@pytest.mark.parametrize(
    ("resource", "start_time", "end_time", "message"),
    [
        (" ", datetime(2026, 10, 2, 9), datetime(2026, 10, 2, 10), "Resource is required"),
        ("pool", datetime(2026, 10, 2, 9), datetime(2026, 10, 2, 10), "valid household resource"),
        ("laundry", None, datetime(2026, 10, 2, 10), "start and end times are required"),
        ("laundry", datetime(2026, 10, 2, 9), datetime(2026, 10, 2, 9), "after its start time"),
        ("laundry", datetime(2026, 10, 2, 10), datetime(2026, 10, 2, 9), "after its start time"),
    ],
)
def test_validate_booking_rejects_invalid_inputs(resource, start_time, end_time, message):
    with pytest.raises(ValueError, match=message):
        validate_booking(resource, start_time, end_time)
