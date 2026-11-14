"""calculate_fairness with the household service stubbed at the seam.

This is the Assignment 1 worked example. The real HTTP hop to household is covered by the
cross-seam integration test in tests/integration at the repo root.
"""

from datetime import datetime, timedelta

import pytest

from app import db
from app.domain2 import services
from app.models import ContributionScore

NOW = datetime(2026, 11, 10, 12, 0)

MEMBERS = [
    {"id": 1, "username": "alice"},
    {"id": 2, "username": "bob"},
    {"id": 3, "username": "charlie"},
]

CONTRIBUTIONS = {
    "completed_tasks": [
        {"user_id": 1, "difficulty": "easy", "completed_at": NOW},
        {"user_id": 1, "difficulty": "hard", "completed_at": NOW},
        {"user_id": 2, "difficulty": "medium", "completed_at": NOW},
    ],
    "bookings": [{"user_id": 2}],
    "overdue": [{"user_id": 3, "overdue_tasks": 1}],
}


@pytest.fixture()
def household(monkeypatch):
    calls = []

    def fake_members(token):
        calls.append(("members", token))
        return MEMBERS

    def fake_contributions(token, start, end, as_of):
        calls.append(("contributions", token, start, end, as_of))
        return CONTRIBUTIONS

    monkeypatch.setattr(services, "get_members", fake_members)
    monkeypatch.setattr(services, "get_contributions", fake_contributions)
    return calls


def test_calculate_fairness_scores_every_member(app, household):
    scores = services.calculate_fairness(
        NOW - timedelta(days=10), NOW + timedelta(days=10), calculated_at=NOW, token="tok"
    )

    by_user = {score.user_id: score for score in scores}
    assert by_user[1].weighted_score == 4
    assert by_user[1].tasks_completed == 2
    assert by_user[1].bookings_count == 0
    assert by_user[1].contribution_score == pytest.approx(4 / 7 * 100)

    assert by_user[2].weighted_score == 2
    assert by_user[2].tasks_completed == 1
    assert by_user[2].bookings_count == 1
    assert by_user[2].contribution_score == pytest.approx(3 / 7 * 100)

    assert by_user[3].weighted_score == 0
    assert by_user[3].tasks_completed == 0
    assert by_user[3].overdue_tasks == 1
    assert by_user[3].contribution_score == 0


def test_calculate_fairness_forwards_the_callers_token(app, household):
    services.calculate_fairness(NOW - timedelta(days=1), NOW, calculated_at=NOW, token="tok-123")

    assert [call[1] for call in household] == ["tok-123", "tok-123"]


def test_recalculating_keeps_historical_snapshots(app, household):
    start, end = NOW - timedelta(days=10), NOW + timedelta(days=10)
    services.calculate_fairness(start, end, calculated_at=NOW, token="t")
    services.calculate_fairness(start, end, calculated_at=NOW + timedelta(minutes=10), token="t")

    rows = ContributionScore.query.order_by(ContributionScore.id).all()
    assert len(rows) == 6
    assert [row.user_id for row in rows].count(1) == 2


def test_calculate_fairness_stores_nothing_when_household_fails(app, monkeypatch):
    from app.seam import HouseholdUnavailable

    def down(token):
        raise HouseholdUnavailable("down")

    monkeypatch.setattr(services, "get_members", down)

    with pytest.raises(HouseholdUnavailable):
        services.calculate_fairness(NOW - timedelta(days=1), NOW, calculated_at=NOW, token="t")

    assert db.session.query(ContributionScore).count() == 0


@pytest.mark.parametrize(
    ("start", "end", "calculated_at", "message"),
    [
        ("2026-01-01", NOW, NOW, "must use datetime"),
        (NOW, "2026-01-01", NOW, "must use datetime"),
        (NOW, NOW - timedelta(days=1), NOW, "period is invalid"),
        (NOW - timedelta(days=1), NOW, "yesterday", "calculation time is invalid"),
    ],
)
def test_calculate_fairness_rejects_invalid_inputs(app, household, start, end, calculated_at, message):
    with pytest.raises(ValueError, match=message):
        services.calculate_fairness(start, end, calculated_at=calculated_at, token="t")
