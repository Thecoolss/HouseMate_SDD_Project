from datetime import datetime

from app import db


class ContributionScore(db.Model):
    __tablename__ = "contribution_score"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    tasks_completed = db.Column(db.Integer, nullable=False, default=0)
    weighted_score = db.Column(db.Float, nullable=False, default=0.0)
    bookings_count = db.Column(db.Integer, nullable=False, default=0)
    contribution_score = db.Column(db.Float, nullable=False, default=0.0)
    calculated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
