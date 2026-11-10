from datetime import datetime

from app import db
from app.seam import get_contributions, get_members
from app.domain2.calculations import (
    calculate_contribution_percentages,
    task_weight,
)
from app.models import ContributionScore
from app.time_utils import utc_now


def calculate_fairness(period_start, period_end, calculated_at=None, *, token):
    """Append one ContributionScore per household member for the period.

    token is the logged-in user's bearer token, forwarded to household by the seam.
    Raises HouseholdUnavailable if household cannot be reached.
    """
    if not isinstance(period_start, datetime) or not isinstance(period_end, datetime):
        raise ValueError("The contribution period must use datetime values.")
    if period_start > period_end:
        raise ValueError("The contribution period is invalid.")

    calculated_at = calculated_at or utc_now()
    if not isinstance(calculated_at, datetime):
        raise ValueError("The calculation time is invalid.")

    # Both reads come from the household service over HTTP (see app/seam.py).
    user_ids = [member["id"] for member in get_members(token)]
    contributions = get_contributions(token, period_start, period_end, calculated_at)

    task_counts = {user_id: 0 for user_id in user_ids}
    weighted_scores = {user_id: 0 for user_id in user_ids}
    bookings_counts = {user_id: 0 for user_id in user_ids}
    overdue_counts = {user_id: 0 for user_id in user_ids}

    for contribution in contributions["completed_tasks"]:
        user_id = contribution["user_id"]
        task_counts[user_id] += 1
        weighted_scores[user_id] += task_weight(contribution["difficulty"])

    for contribution in contributions["bookings"]:
        bookings_counts[contribution["user_id"]] += 1

    for contribution in contributions["overdue"]:
        overdue_counts[contribution["user_id"]] = contribution["overdue_tasks"]

    percentages = calculate_contribution_percentages(weighted_scores, bookings_counts)

    scores = []
    for user_id in user_ids:
        score = ContributionScore(
            user_id=user_id,
            period_start=period_start.date(),
            period_end=period_end.date(),
            tasks_completed=task_counts[user_id],
            weighted_score=weighted_scores[user_id],
            bookings_count=bookings_counts[user_id],
            overdue_tasks=overdue_counts[user_id],
            contribution_score=percentages[user_id],
            calculated_at=calculated_at,
        )
        db.session.add(score)
        scores.append(score)

    db.session.commit()
    return scores