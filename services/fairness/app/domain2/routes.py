from datetime import timedelta

from flask import g, jsonify

from app import db
from app.domain2 import bp
from app.domain2.services import calculate_fairness
from app.models import ContributionScore
from app.seam import HouseholdUnavailable, get_members
from app.time_utils import utc_now
from app.tokens import require_auth


def _iso_utc(value):
    return value.isoformat() + "Z" if value is not None else None


def _score_json(score):
    return {
        "period_start": score.period_start.isoformat(),
        "period_end": score.period_end.isoformat(),
        "tasks_completed": score.tasks_completed,
        "weighted_score": score.weighted_score,
        "bookings_count": score.bookings_count,
        "overdue_tasks": score.overdue_tasks,
        "contribution_score": score.contribution_score,
        "calculated_at": _iso_utc(score.calculated_at),
    }


def _latest_snapshots():
    """The most recent ContributionScore per user, keyed by user_id."""
    ranked = db.select(
        ContributionScore.id.label("snapshot_id"),
        db.func.row_number()
        .over(
            partition_by=ContributionScore.user_id,
            order_by=(ContributionScore.calculated_at.desc(), ContributionScore.id.desc()),
        )
        .label("snapshot_rank"),
    ).subquery()
    statement = db.select(ContributionScore).join(
        ranked,
        db.and_(ranked.c.snapshot_id == ContributionScore.id, ranked.c.snapshot_rank == 1),
    )
    return {score.user_id: score for score in db.session.execute(statement).scalars()}


@bp.get("/fairness")
@require_auth
def fairness():
    """Latest snapshot per member.

    If household is down this still answers 200 from fairness's own data: members without
    a snapshot are missing, usernames are null, and household_available is false.
    """
    snapshots = _latest_snapshots()
    try:
        members = get_members(g.token)
        household_available = True
    except HouseholdUnavailable:
        members = [{"id": user_id, "username": None} for user_id in snapshots]
        household_available = False

    rows = [
        {
            "user_id": member["id"],
            "username": member["username"],
            "snapshot": _score_json(snapshots[member["id"]]) if member["id"] in snapshots else None,
        }
        for member in members
    ]
    rows.sort(key=lambda row: (row["username"] is None, row["username"] or "", row["user_id"]))
    return jsonify(household_available=household_available, rows=rows)


@bp.post("/fairness/recalculate")
@require_auth
def recalculate_fairness():
    calculated_at = utc_now()
    period_start = calculated_at - timedelta(days=30)
    try:
        scores = calculate_fairness(
            period_start, calculated_at, calculated_at=calculated_at, token=g.token
        )
    except HouseholdUnavailable as error:
        return jsonify(error=f"Could not recalculate: {error}"), 503
    return (
        jsonify(scores=[{"user_id": score.user_id, **_score_json(score)} for score in scores]),
        201,
    )
