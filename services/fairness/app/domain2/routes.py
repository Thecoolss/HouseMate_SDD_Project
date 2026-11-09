from datetime import timedelta

from flask import flash, redirect, render_template, url_for
from flask_login import login_required

from app import db
from app.domain2 import bp
from app.domain2.services import calculate_fairness
from app.models import ContributionScore
from app.seam import HouseholdUnavailable, get_members
from app.time_utils import utc_now


@bp.get("/fairness")
@login_required
def fairness():
    """Show the latest contribution snapshot for each household member."""
    # Fetch users from household service instead of joining User table.
    try:
        users = get_members()
    except HouseholdUnavailable:
        flash("Household members are unavailable right now.", "error")
        users = []

    user_map = {u["id"]: u["username"] for u in users}

    latest_snapshots = db.select(
        ContributionScore.user_id.label("user_id"),
        ContributionScore.id.label("snapshot_id"),
        db.func.row_number()
        .over(
            partition_by=ContributionScore.user_id,
            order_by=(ContributionScore.calculated_at.desc(), ContributionScore.id.desc()),
        )
        .label("snapshot_rank"),
    ).subquery()

    # Build rows manually since we can't join User anymore.
    statement = (
        db.select(ContributionScore)
        .join(
            latest_snapshots,
            db.and_(
                latest_snapshots.c.user_id == ContributionScore.user_id,
                latest_snapshots.c.snapshot_rank == 1,
            ),
        )
        .order_by(ContributionScore.user_id.asc())
    )
    snapshots = db.session.execute(statement).scalars().all()

    # Build rows as (user_dict, snapshot) pairs for template compatibility.
    rows = []
    for snapshot in snapshots:
        user_dict = {"id": snapshot.user_id, "username": user_map.get(snapshot.user_id, "Unknown")}
        rows.append((user_dict, snapshot))

    # Add users without snapshots.
    snapshot_user_ids = {s.user_id for s in snapshots}
    for user in users:
        if user["id"] not in snapshot_user_ids:
            rows.append((user, None))

    return render_template("fairness/index.html", rows=rows)


@bp.post("/fairness/recalculate")
@login_required
def recalculate_fairness():
    calculated_at = utc_now()
    period_start = calculated_at - timedelta(days=30)
    try:
        scores = calculate_fairness(period_start, calculated_at, calculated_at=calculated_at)
        flash(f"Contribution snapshots recalculated for {len(scores)} household members.", "success")
    except HouseholdUnavailable as error:
        flash(f"Could not recalculate: {error}", "error")
    return redirect(url_for("domain2.fairness"))
