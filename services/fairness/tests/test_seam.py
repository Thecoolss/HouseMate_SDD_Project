"""The seam's HTTP client, with httpx.get replaced so no real request is made."""

from datetime import datetime

import httpx
import pytest

from app import seam
from app.seam import HouseholdUnavailable


def _response(status, payload=None):
    return httpx.Response(status, json=payload, request=httpx.Request("GET", "http://household"))


@pytest.fixture()
def fake_get(app, monkeypatch):
    """Record the call and answer with whatever the test sets on `.result`."""

    class Fake:
        result = _response(200, [])
        calls = []

        def __call__(self, url, params=None, headers=None, timeout=None):
            self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
            if isinstance(self.result, Exception):
                raise self.result
            return self.result

    fake = Fake()
    fake.calls = []
    monkeypatch.setattr(httpx, "get", fake)
    return fake


def test_get_members_calls_household_with_the_forwarded_token(app, fake_get):
    fake_get.result = _response(200, [{"id": 1, "username": "alice"}])

    members = seam.get_members("tok-abc")

    assert members == [{"id": 1, "username": "alice"}]
    call = fake_get.calls[0]
    assert call["url"] == app.config["HOUSEHOLD_URL"] + "/internal/users"
    assert call["headers"] == {"Authorization": "Bearer tok-abc"}
    assert call["timeout"] == app.config["HOUSEHOLD_TIMEOUT_S"]


def test_get_contributions_sends_the_period_and_parses_completion_times(app, fake_get):
    fake_get.result = _response(
        200,
        {
            "completed_tasks": [
                {"user_id": 1, "difficulty": "easy", "completed_at": "2026-11-10T10:00:00"}
            ],
            "bookings": [],
            "overdue": [],
        },
    )
    start, end, as_of = datetime(2026, 10, 11), datetime(2026, 11, 10), datetime(2026, 11, 10, 12)

    data = seam.get_contributions("tok", start, end, as_of)

    assert fake_get.calls[0]["params"] == {
        "start": "2026-10-11T00:00:00",
        "end": "2026-11-10T00:00:00",
        "as_of": "2026-11-10T12:00:00",
    }
    assert data["completed_tasks"][0]["completed_at"] == datetime(2026, 11, 10, 10, 0)


def test_unreachable_household_becomes_household_unavailable(app, fake_get):
    fake_get.result = httpx.ConnectError("connection refused")

    with pytest.raises(HouseholdUnavailable, match="unavailable"):
        seam.get_members("tok")


def test_timeout_becomes_household_unavailable(app, fake_get):
    fake_get.result = httpx.ReadTimeout("too slow")

    with pytest.raises(HouseholdUnavailable):
        seam.get_members("tok")


@pytest.mark.parametrize("status", [401, 500, 503])
def test_error_status_becomes_household_unavailable(app, fake_get, status):
    fake_get.result = _response(status, {"error": "nope"})

    with pytest.raises(HouseholdUnavailable, match=str(status)):
        seam.get_members("tok")
