from datetime import datetime, timedelta

from app import db
from app.domain1 import services
from app.domain2.services import calculate_fairness
from app.models import ContributionScore, User


def _make_user(app, username):
    with app.app_context():
        user = User(username=username)
        user.set_password("test-password-123")
        db.session.add(user)
        db.session.commit()
        return user.id


def test_calculate_fairness_and_keep_historical_snapshots(app):
    alice_id = _make_user(app, "alice")
    bob_id = _make_user(app, "bob")
    charlie_id = _make_user(app, "charlie")

    with app.app_context():
        alice = db.session.get(User, alice_id)
        bob = db.session.get(User, bob_id)
        charlie = db.session.get(User, charlie_id)
        now = datetime.utcnow()
        period_start = now - timedelta(days=10)
        period_end = now + timedelta(days=10)

        task_a1 = services.create_task(alice, "Task A1", "", "easy")
        services.claim_task(alice, task_a1.id)
        services.mark_complete(alice, task_a1.id)

        task_a2 = services.create_task(alice, "Task A2", "", "hard")
        services.claim_task(alice, task_a2.id)
        services.mark_complete(alice, task_a2.id)

        task_b1 = services.create_task(bob, "Task B1", "", "medium")
        services.claim_task(bob, task_b1.id)
        services.mark_complete(bob, task_b1.id)

        services.create_booking(
            bob,
            "laundry",
            now + timedelta(hours=1),
            now + timedelta(hours=2),
        )

        first_scores = calculate_fairness(
            period_start,
            period_end,
            calculated_at=now + timedelta(minutes=5),
        )

        by_user = {score.user_id: score for score in first_scores}

        assert by_user[alice.id].weighted_score == 4
        assert by_user[alice.id].tasks_completed == 2
        assert by_user[alice.id].bookings_count == 0
        assert by_user[alice.id].contribution_score == (4 / 7) * 100

        assert by_user[bob.id].weighted_score == 2
        assert by_user[bob.id].tasks_completed == 1
        assert by_user[bob.id].bookings_count == 1
        assert by_user[bob.id].contribution_score == (3 / 7) * 100

        assert by_user[charlie.id].weighted_score == 0
        assert by_user[charlie.id].tasks_completed == 0
        assert by_user[charlie.id].bookings_count == 0
        assert by_user[charlie.id].contribution_score == 0

        calculate_fairness(
            period_start,
            period_end,
            calculated_at=now + timedelta(minutes=15),
        )

        rows = ContributionScore.query.order_by(ContributionScore.user_id.asc(), ContributionScore.id.asc()).all()
        assert len(rows) == 6
        alice_rows = [row for row in rows if row.user_id == alice.id]
        bob_rows = [row for row in rows if row.user_id == bob.id]
        charlie_rows = [row for row in rows if row.user_id == charlie.id]

        assert len(alice_rows) == 2
        assert len(bob_rows) == 2
        assert len(charlie_rows) == 2
        assert alice_rows[0].weighted_score == 4
        assert bob_rows[0].weighted_score == 2
        assert charlie_rows[0].weighted_score == 0
