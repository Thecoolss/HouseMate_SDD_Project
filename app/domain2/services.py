from datetime import datetime

from app import db
from app.domain1.services import (
    get_booking_contributions,
    get_completed_task_contributions,
    get_overdue_task_counts,
)
from app.domain2.calculations import (
    calculate_contribution_percentages,
    task_weight,
)
from app.models import ContributionScore, User


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
        weighted_scores[user_id] += task_weight(contribution["difficulty"])

    for contribution in get_booking_contributions(period_start, period_end):
        bookings_counts[contribution["user_id"]] += 1

    for contribution in get_overdue_task_counts(calculated_at):
        overdue_counts[contribution["user_id"]] = contribution["overdue_tasks"]

    percentages = calculate_contribution_percentages(weighted_scores, bookings_counts)

    scores = []
    for user in users:
        score = ContributionScore(
            user_id=user.id,
            period_start=period_start.date(),
            period_end=period_end.date(),
            tasks_completed=task_counts[user.id],
            weighted_score=weighted_scores[user.id],
            bookings_count=bookings_counts[user.id],
            overdue_tasks=overdue_counts[user.id],
            contribution_score=percentages[user.id],
            calculated_at=calculated_at,
        )
        db.session.add(score)
        scores.append(score)

    db.session.commit()
    return scores