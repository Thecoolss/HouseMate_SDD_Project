from datetime import timedelta

from flask import flash, redirect, render_template, url_for
from flask_login import login_required

from app import db
from app.domain2 import bp
from app.domain2.services import calculate_fairness
from app.models import ContributionScore, User
from app.time_utils import utc_now


@bp.get("/fairness")
@login_required
def fairness():
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

    statement = (
        db.select(User, ContributionScore)
        .outerjoin(
            latest_snapshots,
            db.and_(
                latest_snapshots.c.user_id == User.id,
                latest_snapshots.c.snapshot_rank == 1,
            ),
        )
        .outerjoin(
            ContributionScore,
            ContributionScore.id == latest_snapshots.c.snapshot_id,
        )
        .order_by(User.username.asc())
    )
    rows = db.session.execute(statement).all()
    return render_template("fairness/index.html", rows=rows)


@bp.post("/fairness/recalculate")
@login_required
def recalculate_fairness():
    calculated_at = utc_now()
    period_start = calculated_at - timedelta(days=30)
    scores = calculate_fairness(period_start, calculated_at, calculated_at=calculated_at)
    flash(f"Contribution snapshots recalculated for {len(scores)} household members.", "success")
    return redirect(url_for("domain2.fairness"))