from datetime import datetime, timedelta

import pytest

from app import db
from app.domain1 import services
from app.models import User


def _make_user(app, username):
    with app.app_context():
        user = User(username=username)
        user.set_password("test-password-123")
        db.session.add(user)
        db.session.commit()
        return user.id


def test_create_valid_booking(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        start = datetime.utcnow()
        end = start + timedelta(hours=2)
        booking = services.create_booking(user, "laundry", start, end)

        assert booking.resource == "laundry"
        assert booking.created_by == user.id
        assert booking.end_time > booking.start_time


def test_invalid_booking_time_range_rejected(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        start = datetime.utcnow()
        end = start

        with pytest.raises(ValueError):
            services.create_booking(user, "laundry", start, end)


def test_overlapping_booking_rejected(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        start = datetime.utcnow()
        end = start + timedelta(hours=2)
        services.create_booking(user, "laundry", start, end)

        with pytest.raises(ValueError):
            services.create_booking(user, "laundry", start + timedelta(hours=1), end + timedelta(hours=1))


def test_adjacent_bookings_allowed(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        start = datetime.utcnow()
        end = start + timedelta(hours=1)
        services.create_booking(user, "laundry", start, end)

        next_start = end
        next_end = next_start + timedelta(hours=1)
        booking = services.create_booking(user, "laundry", next_start, next_end)

        assert booking.resource == "laundry"


def test_creator_can_update_booking(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        start = datetime.utcnow()
        end = start + timedelta(hours=1)
        booking = services.create_booking(user, "laundry", start, end)

        new_start = start + timedelta(hours=2)
        new_end = new_start + timedelta(hours=1)
        updated = services.update_booking(user, booking.id, resource="kitchen", start_time=new_start, end_time=new_end)

        assert updated.resource == "kitchen"
        assert updated.start_time == new_start
        assert updated.end_time == new_end


def test_non_creator_cannot_update_booking(app):
    creator_id = _make_user(app, "alice")
    other_user_id = _make_user(app, "bob")

    with app.app_context():
        creator = db.session.get(User, creator_id)
        other_user = db.session.get(User, other_user_id)
        start = datetime.utcnow()
        end = start + timedelta(hours=1)
        booking = services.create_booking(creator, "laundry", start, end)

        with pytest.raises(PermissionError):
            services.update_booking(other_user, booking.id, resource="kitchen", start_time=start, end_time=end)


def test_creator_can_delete_booking(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        start = datetime.utcnow()
        end = start + timedelta(hours=1)
        booking = services.create_booking(user, "laundry", start, end)
        services.delete_booking(user, booking.id)

        assert services.list_bookings(user) == []


def test_non_creator_cannot_delete_booking(app):
    creator_id = _make_user(app, "alice")
    other_user_id = _make_user(app, "bob")

    with app.app_context():
        creator = db.session.get(User, creator_id)
        other_user = db.session.get(User, other_user_id)
        start = datetime.utcnow()
        end = start + timedelta(hours=1)
        booking = services.create_booking(creator, "laundry", start, end)

        with pytest.raises(PermissionError):
            services.delete_booking(other_user, booking.id)
