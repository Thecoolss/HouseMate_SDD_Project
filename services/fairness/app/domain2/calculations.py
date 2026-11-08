from collections.abc import Mapping


TASK_WEIGHTS = {"easy": 1, "medium": 2, "hard": 3}


def task_weight(difficulty):
    try:
        return TASK_WEIGHTS[difficulty]
    except KeyError:
        raise ValueError("Difficulty must be easy, medium, or hard.") from None


def calculate_contribution_percentages(
    weighted_scores: Mapping[int, int],
    bookings_counts: Mapping[int, int],
) -> dict[int, float]:
    total_contribution = sum(
        weighted_score + bookings_counts[user_id]
        for user_id, weighted_score in weighted_scores.items()
    )

    return {
        user_id: (
            (weighted_score + bookings_counts[user_id]) / total_contribution * 100
            if total_contribution
            else 0.0
        )
        for user_id, weighted_score in weighted_scores.items()
    }
