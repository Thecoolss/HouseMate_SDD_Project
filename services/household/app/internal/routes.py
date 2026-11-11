from datetime import datetime

from flask import jsonify, request

from app import db
from app.domain1.services import (
    get_booking_contributions,
    get_completed_task_contributions,
    get_overdue_task_counts,
)
from app.internal import bp
from app.models import User
from app.tokens import require_auth

# Called by the fairness service, which forwards the logged-in user's bearer token.


@bp.get("/contributions")
@require_auth
def contributions():
    """Contribution data the fairness service needs, in one response.

    Query parameters (ISO 8601, naive UTC): start and end bound the period, as_of is
    the time overdue tasks are measured against.
    """
    try:
        period_start = datetime.fromisoformat(request.args["start"])
        period_end = datetime.fromisoformat(request.args["end"])
        calculated_at = datetime.fromisoformat(request.args["as_of"])
    except (KeyError, ValueError):
        return jsonify({"error": "start, end and as_of must be ISO 8601 datetimes."}), 400

    try:
        completed_tasks = get_completed_task_contributions(period_start, period_end)
        bookings = get_booking_contributions(period_start, period_end)
        overdue = get_overdue_task_counts(calculated_at)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    for task in completed_tasks:
        task["completed_at"] = task["completed_at"].isoformat()

    return jsonify(
        {"completed_tasks": completed_tasks, "bookings": bookings, "overdue": overdue}
    )


@bp.get("/users")
@require_auth
def users():
    """Household members, as [{id, username}]."""
    rows = db.session.execute(db.select(User.id, User.username).order_by(User.id.asc()))
    return jsonify([{"id": user_id, "username": username} for user_id, username in rows])
