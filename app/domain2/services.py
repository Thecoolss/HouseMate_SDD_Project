from datetime import datetime

from app import db
from app.domain1.services import (
    get_booking_contributions,
    get_completed_task_contributions,
    get_overdue_task_counts,
)
from app.models import ContributionScore, User


TASK_WEIGHTS = {"easy": 1, "medium": 2, "hard": 3}


def calculate_fairness(period_start, period_end, calculated_at=None):
    if not isinstance(period_start, datetime) or not isinstance(period_end, datetime):
        raise ValueError("The contribution period must use datetime values.")
    if period_start > period_end:
        raise ValueError("The contribution period is invalid.")

    calculated_at = calculated_at or datetime.utcnow()
    if not isinstance(calculated_at, datetime):
        raise ValueError("The calculation time is invalid.")

    users = User.query.order_by(User.id.asc()).all()
    task_counts = {user.id: 0 for user in users}
    weighted_scores = {user.id: 0 for user in users}
    bookings_counts = {user.id: 0 for user in users}
    overdue_counts = {user.id: 0 for user in users}

    for contribution in get_completed_task_contributions(period_start, period_end):
        user_id = contribution["user_id"]
        task_counts[user_id] += 1
        weighted_scores[user_id] += TASK_WEIGHTS[contribution["difficulty"]]

    for contribution in get_booking_contributions(period_start, period_end):
        bookings_counts[contribution["user_id"]] += 1

    for contribution in get_overdue_task_counts(calculated_at):
        overdue_counts[contribution["user_id"]] = contribution["overdue_tasks"]

    total_contribution = sum(
        weighted_scores[user.id] + bookings_counts[user.id]
        for user in users
    )

    scores = []
    for user in users:
        user_contribution = weighted_scores[user.id] + bookings_counts[user.id]
        contribution_score = (
            user_contribution / total_contribution * 100
            if total_contribution
            else 0.0
        )
        score = ContributionScore(
            user_id=user.id,
            period_start=period_start.date(),
            period_end=period_end.date(),
            tasks_completed=task_counts[user.id],
            weighted_score=weighted_scores[user.id],
            bookings_count=bookings_counts[user.id],
            overdue_tasks=overdue_counts[user.id],
            contribution_score=contribution_score,
            calculated_at=calculated_at,
        )
        db.session.add(score)
        scores.append(score)

    db.session.commit()
    return scores