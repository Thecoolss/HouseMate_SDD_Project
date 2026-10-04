import pytest

from app.domain2.calculations import (
    calculate_contribution_percentages,
    task_weight,
)


@pytest.mark.parametrize(
    ("difficulty", "expected_weight"),
    [("easy", 1), ("medium", 2), ("hard", 3)],
)
def test_task_weight_matches_difficulty(difficulty, expected_weight):
    assert task_weight(difficulty) == expected_weight


def test_task_weight_rejects_unknown_difficulty():
    with pytest.raises(ValueError, match="Difficulty must be"):
        task_weight("impossible")


def test_calculate_contribution_percentages_combines_tasks_and_bookings():
    percentages = calculate_contribution_percentages(
        weighted_scores={1: 4, 2: 2, 3: 0},
        bookings_counts={1: 0, 2: 1, 3: 0},
    )

    assert percentages == pytest.approx(
        {1: (4 / 7) * 100, 2: (3 / 7) * 100, 3: 0.0}
    )
    assert sum(percentages.values()) == pytest.approx(100)


def test_calculate_contribution_percentages_returns_zero_for_no_contributions():
    percentages = calculate_contribution_percentages(
        weighted_scores={1: 0, 2: 0},
        bookings_counts={1: 0, 2: 0},
    )

    assert percentages == {1: 0.0, 2: 0.0}
