from app import db
from app.time_utils import utc_now


class ContributionScore(db.Model):
    __tablename__ = "contribution_score"

    id = db.Column(db.Integer, primary_key=True)
    # DAY-1 SPLIT: the user lives in the household service's database, so this is now a
    # plain id, not a foreign key across the seam (Assignment 2 §2). Referential
    # integrity is enforced in code / by the household service, not by the database.
    user_id = db.Column(db.Integer, nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    tasks_completed = db.Column(db.Integer, nullable=False, default=0)
    weighted_score = db.Column(db.Float, nullable=False, default=0.0)
    bookings_count = db.Column(db.Integer, nullable=False, default=0)
    overdue_tasks = db.Column(db.Integer, nullable=True)
    contribution_score = db.Column(db.Float, nullable=False, default=0.0)
    calculated_at = db.Column(db.DateTime, nullable=False, default=utc_now)
