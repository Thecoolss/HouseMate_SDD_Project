"""Integration tests across the household/fairness seam, against two real services."""

import sqlite3
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest


def _complete_task(stack, headers, difficulty):
    base = stack.household.url
    task = httpx.post(f"{base}/tasks", json={"title": "t", "difficulty": difficulty}, headers=headers).json()
    httpx.post(f"{base}/tasks/{task['id']}/claim", headers=headers).raise_for_status()
    httpx.post(f"{base}/tasks/{task['id']}/complete", headers=headers).raise_for_status()


def _book(stack, headers, hours_ago):
    start = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    response = httpx.post(
        f"{stack.household.url}/bookings",
        json={
            "resource": "laundry",
            "start_time": start.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "end_time": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        },
        headers=headers,
    )
    response.raise_for_status()


def _tables(db_path):
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        return {name for (name,) in rows if not name.startswith("sqlite_")}


def test_recalculation_across_the_seam_gives_the_assignment_1_worked_example(stack):
    alice, _ = stack.register("alice")
    bob, bob_id = stack.register("bob")
    stack.register("charlie")
    _complete_task(stack, alice, "easy")
    _complete_task(stack, alice, "hard")
    _complete_task(stack, bob, "medium")
    _book(stack, bob, hours_ago=2)

    response = httpx.post(f"{stack.fairness.url}/fairness/recalculate", headers=alice)

    assert response.status_code == 201
    scores = {row["user_id"]: row for row in response.json()["scores"]}
    assert len(scores) == 3
    assert scores[1]["weighted_score"] == 4 and scores[1]["tasks_completed"] == 2
    assert scores[1]["contribution_score"] == pytest.approx(4 / 7 * 100)
    assert scores[bob_id]["weighted_score"] == 2 and scores[bob_id]["bookings_count"] == 1
    assert scores[bob_id]["contribution_score"] == pytest.approx(3 / 7 * 100)
    assert scores[3]["contribution_score"] == 0


def test_the_fairness_page_shows_member_names_fetched_from_household(stack):
    alice, _ = stack.register("alice")
    stack.register("bob")
    httpx.post(f"{stack.fairness.url}/fairness/recalculate", headers=alice).raise_for_status()

    body = httpx.get(f"{stack.fairness.url}/fairness", headers=alice).json()

    assert body["household_available"] is True
    assert [row["username"] for row in body["rows"]] == ["alice", "bob"]
    assert all(row["snapshot"] is not None for row in body["rows"])


def test_the_token_household_issued_is_accepted_by_fairness_without_household(stack):
    alice, _ = stack.register("alice")
    stack.household.stop()

    response = httpx.get(f"{stack.fairness.url}/fairness", headers=alice)

    assert response.status_code == 200


def test_a_token_signed_with_another_secret_is_rejected_by_both_services(stack):
    from itsdangerous import URLSafeTimedSerializer

    forged = URLSafeTimedSerializer("someone-elses-secret", salt="housemate-auth").dumps(
        {"user_id": 1, "username": "mallory"}
    )
    headers = {"Authorization": f"Bearer {forged}"}

    assert httpx.get(f"{stack.fairness.url}/fairness", headers=headers).status_code == 401
    assert httpx.get(f"{stack.household.url}/tasks", headers=headers).status_code == 401


def test_household_rejecting_the_forwarded_token_is_a_503_not_a_crash(stack):
    from itsdangerous import URLSafeTimedSerializer

    # Valid for fairness (right secret) but for a user household has never heard of.
    ghost = URLSafeTimedSerializer("integration-test-secret", salt="housemate-auth").dumps(
        {"user_id": 999, "username": "ghost"}
    )

    response = httpx.post(
        f"{stack.fairness.url}/fairness/recalculate", headers={"Authorization": f"Bearer {ghost}"}
    )

    assert response.status_code == 503
    assert "401" in response.json()["error"]


class TestWithHouseholdDown:
    """Stop household and check that each side behaves as designed."""

    def test_fairness_keeps_serving_stored_snapshots_and_reports_the_outage(self, stack):
        alice, _ = stack.register("alice")
        _complete_task(stack, alice, "hard")
        httpx.post(f"{stack.fairness.url}/fairness/recalculate", headers=alice).raise_for_status()
        stack.household.stop()

        health = httpx.get(f"{stack.fairness.url}/health")
        page = httpx.get(f"{stack.fairness.url}/fairness", headers=alice)

        assert health.status_code == 200
        assert page.status_code == 200
        body = page.json()
        assert body["household_available"] is False
        assert body["rows"][0]["username"] is None
        assert body["rows"][0]["snapshot"]["contribution_score"] == 100.0

    def test_recalculation_fails_fast_with_a_clear_503_and_stores_nothing(self, stack):
        alice, _ = stack.register("alice")
        stack.household.stop()

        started = time.monotonic()
        response = httpx.post(f"{stack.fairness.url}/fairness/recalculate", headers=alice)
        elapsed = time.monotonic() - started

        assert response.status_code == 503
        assert "household service is unavailable" in response.json()["error"]
        assert elapsed < 5, "the outbound call must time out instead of hanging"
        assert "contribution_score" in _tables(stack.fairness_db)
        with sqlite3.connect(stack.fairness_db) as connection:
            assert connection.execute("SELECT COUNT(*) FROM contribution_score").fetchone() == (0,)


class TestWithFairnessDown:
    def test_household_keeps_serving_its_own_domain(self, stack):
        alice, _ = stack.register("alice")
        stack.fairness.stop()

        created = httpx.post(
            f"{stack.household.url}/tasks", json={"title": "Mop", "difficulty": "easy"}, headers=alice
        )
        health = httpx.get(f"{stack.household.url}/health")

        assert created.status_code == 201
        assert health.status_code == 200


def test_each_service_owns_only_its_own_tables(stack):
    stack.register("alice")

    assert _tables(stack.household_db) == {"user", "task", "booking", "schema_migrations"}
    assert _tables(stack.fairness_db) == {"contribution_score", "schema_migrations"}


def test_health_reports_the_deployed_version_for_each_service(stack):
    for service in (stack.household, stack.fairness):
        body = httpx.get(f"{service.url}/health").json()
        assert body == {"status": "ok", "db": "ok", "version": "integration"}
