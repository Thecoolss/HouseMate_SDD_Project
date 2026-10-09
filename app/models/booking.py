from app import db
from app.time_utils import utc_now


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resource = db.Column(db.String(120), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)