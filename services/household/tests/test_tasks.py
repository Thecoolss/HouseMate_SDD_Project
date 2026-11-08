from datetime import datetime

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


def test_create_task_success(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        task = services.create_task(user, "Vacuum", "Kitchen floors", "easy")

        assert task.title == "Vacuum"
        assert task.difficulty == "easy"
        assert task.status == "pending"
        assert task.assigned_to is None


def test_invalid_task_difficulty_rejected(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        with pytest.raises(ValueError):
            services.create_task(user, "Vacuum", "Kitchen floors", "impossible")


def test_creator_can_update_task(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        task = services.create_task(user, "Vacuum", "Kitchen floors", "easy")
        updated = services.update_task(
            user,
            task.id,
            title="Wash dishes",
            difficulty="hard",
            description="fridge and sink",
        )

        assert updated.title == "Wash dishes"
        assert updated.difficulty == "hard"
        assert updated.description == "fridge and sink"


def test_non_creator_cannot_update_task(app):
    creator_id = _make_user(app, "alice")
    other_user_id = _make_user(app, "bob")

    with app.app_context():
        creator = db.session.get(User, creator_id)
        other_user = db.session.get(User, other_user_id)
        task = services.create_task(creator, "Vacuum", "Kitchen floors", "easy")

        with pytest.raises(PermissionError):
            services.update_task(other_user, task.id, title="Unauthorized")


def test_creator_can_delete_task(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        task = services.create_task(user, "Vacuum", "Kitchen floors", "easy")
        services.delete_task(user, task.id)

        assert services.list_tasks(user) == []


def test_non_creator_cannot_delete_task(app):
    creator_id = _make_user(app, "alice")
    other_user_id = _make_user(app, "bob")

    with app.app_context():
        creator = db.session.get(User, creator_id)
        other_user = db.session.get(User, other_user_id)
        task = services.create_task(creator, "Vacuum", "Kitchen floors", "easy")

        with pytest.raises(PermissionError):
            services.delete_task(other_user, task.id)


def test_claim_unclaimed_task(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        task = services.create_task(user, "Vacuum", "Kitchen floors", "easy")
        claimed = services.claim_task(user, task.id)

        assert claimed.assigned_to == user.id
        assert claimed.status == "pending"


def test_cannot_claim_already_claimed_task(app):
    user_id = _make_user(app, "alice")
    other_user_id = _make_user(app, "bob")

    with app.app_context():
        user = db.session.get(User, user_id)
        other_user = db.session.get(User, other_user_id)
        task = services.create_task(user, "Vacuum", "Kitchen floors", "easy")
        services.claim_task(other_user, task.id)

        with pytest.raises(ValueError):
            services.claim_task(user, task.id)


def test_assignee_can_complete_task(app):
    user_id = _make_user(app, "alice")

    with app.app_context():
        user = db.session.get(User, user_id)
        task = services.create_task(user, "Vacuum", "Kitchen floors", "easy")
        services.claim_task(user, task.id)
        completed = services.mark_complete(user, task.id)

        assert completed.status == "done"
        assert completed.completed_at is not None


def test_non_assignee_cannot_complete_task(app):
    creator_id = _make_user(app, "alice")
    other_user_id = _make_user(app, "bob")

    with app.app_context():
        creator = db.session.get(User, creator_id)
        other_user = db.session.get(User, other_user_id)
        task = services.create_task(creator, "Vacuum", "Kitchen floors", "easy")
        services.claim_task(creator, task.id)

        with pytest.raises(PermissionError):
            services.mark_complete(other_user, task.id)
