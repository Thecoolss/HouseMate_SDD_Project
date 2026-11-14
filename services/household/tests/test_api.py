"""The household HTTP API: tasks, bookings, internal endpoints, health, CORS and logging."""

import logging
from datetime import timedelta

import pytest
from sqlalchemy import text

from app import db
from app.time_utils import utc_now


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _new_task(client, headers, **overrides):
    body = {"title": "Vacuum", "difficulty": "easy", **overrides}
    return client.post("/tasks", json=body, headers=headers)


# --- tasks --------------------------------------------------------------------------------


def test_task_lifecycle_over_http(client, login):
    alice, bob = login("alice"), login("bob")

    created = _new_task(client, alice, description="Kitchen", due_date="2026-12-01T18:00")
    assert created.status_code == 201
    task = created.get_json()
    assert task["status"] == "pending" and task["assigned_to"] is None
    assert task["created_by_username"] == "alice"
    # 18:00 household local time (Europe/Paris, UTC+1 in December) is stored and returned as UTC.
    assert task["due_date"] == "2026-12-01T17:00:00Z"

    claimed = client.post(f"/tasks/{task['id']}/claim", headers=bob).get_json()
    assert claimed["assigned_to_username"] == "bob"

    assert client.post(f"/tasks/{task['id']}/complete", headers=alice).status_code == 403
    done = client.post(f"/tasks/{task['id']}/complete", headers=bob).get_json()
    assert done["status"] == "done" and done["completed_at"].endswith("Z")

    listed = client.get("/tasks", headers=alice).get_json()
    assert [t["id"] for t in listed] == [task["id"]]


def test_patch_changes_only_the_fields_sent_and_null_clears(client, login):
    alice = login("alice")
    task = _new_task(client, alice, description="keep", due_date="2026-12-01T18:00").get_json()

    renamed = client.patch(f"/tasks/{task['id']}", json={"title": "Mop"}, headers=alice).get_json()
    assert renamed["title"] == "Mop" and renamed["description"] == "keep"
    assert renamed["due_date"] == "2026-12-01T17:00:00Z"

    cleared = client.patch(
        f"/tasks/{task['id']}", json={"description": None, "due_date": None}, headers=alice
    ).get_json()
    assert cleared["description"] is None and cleared["due_date"] is None
    assert cleared["title"] == "Mop"


def test_only_the_creator_can_edit_or_delete_a_task(client, login):
    alice, bob = login("alice"), login("bob")
    task_id = _new_task(client, alice).get_json()["id"]

    assert client.patch(f"/tasks/{task_id}", json={"title": "x"}, headers=bob).status_code == 403
    assert client.delete(f"/tasks/{task_id}", headers=bob).status_code == 403
    assert client.delete(f"/tasks/{task_id}", headers=alice).status_code == 204
    assert client.get("/tasks", headers=alice).get_json() == []


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"title": "  ", "difficulty": "easy"}, "title is required"),
        ({"title": "x", "difficulty": "impossible"}, "Difficulty must be"),
        ({"title": "x", "difficulty": "easy", "due_date": "not a date"}, "valid due date"),
        ({"title": "x", "difficulty": "easy", "due_date": 12345}, "valid due date"),
        ({"title": "x", "difficulty": "easy", "due_date": "2026-03-29T02:30"}, "does not exist"),
    ],
)
def test_invalid_task_input_is_a_400_with_a_message(client, login, body, message):
    response = client.post("/tasks", json=body, headers=login("alice"))

    assert response.status_code == 400
    assert message in response.get_json()["error"]


def test_missing_task_is_a_404(client, login):
    alice = login("alice")

    assert client.patch("/tasks/999", json={"title": "x"}, headers=alice).status_code == 404
    assert client.post("/tasks/999/claim", headers=alice).status_code == 404
    assert client.delete("/tasks/999", headers=alice).status_code == 404


def test_claiming_an_already_claimed_task_is_a_400(client, login):
    alice, bob = login("alice"), login("bob")
    task_id = _new_task(client, alice).get_json()["id"]
    client.post(f"/tasks/{task_id}/claim", headers=alice)

    assert client.post(f"/tasks/{task_id}/claim", headers=bob).status_code == 400


@pytest.mark.parametrize("body", [None, [], "text"])
def test_a_body_that_is_not_a_json_object_is_a_400(client, login, body):
    response = client.post("/tasks", json=body, headers=login("alice"))

    assert response.status_code == 400
    assert "JSON object" in response.get_json()["error"]


# --- bookings -----------------------------------------------------------------------------


def _booking(client, headers, resource="laundry", hours=0, length=1):
    start = utc_now() + timedelta(days=1, hours=hours)
    return client.post(
        "/bookings",
        json={"resource": resource, "start_time": _iso(start), "end_time": _iso(start + timedelta(hours=length))},
        headers=headers,
    )


def test_booking_lifecycle_over_http(client, login):
    alice, bob = login("alice"), login("bob")

    created = _booking(client, alice)
    assert created.status_code == 201
    booking = created.get_json()
    assert booking["resource"] == "laundry" and booking["created_by_username"] == "alice"

    moved = client.patch(f"/bookings/{booking['id']}", json={"resource": "kitchen"}, headers=alice)
    assert moved.get_json()["resource"] == "kitchen"

    assert client.patch(f"/bookings/{booking['id']}", json={"resource": "laundry"}, headers=bob).status_code == 403
    assert client.delete(f"/bookings/{booking['id']}", headers=bob).status_code == 403
    assert client.delete(f"/bookings/{booking['id']}", headers=alice).status_code == 204
    assert client.get("/bookings", headers=bob).get_json() == []


def test_overlapping_booking_is_rejected_and_adjacent_is_allowed(client, login):
    alice = login("alice")
    assert _booking(client, alice, hours=0, length=2).status_code == 201

    assert _booking(client, alice, hours=1, length=2).status_code == 400
    assert _booking(client, alice, hours=2, length=1).status_code == 201


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"resource": "pool", "start_time": "2026-12-01T10:00", "end_time": "2026-12-01T11:00"}, "valid household resource"),
        ({"resource": "laundry", "end_time": "2026-12-01T11:00"}, "start and end times are required"),
        ({"resource": "laundry", "start_time": "2026-12-01T11:00", "end_time": "2026-12-01T10:00"}, "after its start time"),
        ({"resource": "laundry", "start_time": "garbage", "end_time": "2026-12-01T10:00"}, "valid booking start time"),
    ],
)
def test_invalid_booking_input_is_a_400(client, login, body, message):
    response = client.post("/bookings", json=body, headers=login("alice"))

    assert response.status_code == 400
    assert message in response.get_json()["error"]


def test_missing_booking_is_a_404(client, login):
    alice = login("alice")

    assert client.patch("/bookings/999", json={"resource": "kitchen"}, headers=alice).status_code == 404
    assert client.delete("/bookings/999", headers=alice).status_code == 404


# --- internal endpoints (called by the fairness service) --------------------------------


def test_internal_endpoints_need_a_token(client):
    assert client.get("/internal/users").status_code == 401
    assert client.get("/internal/contributions").status_code == 401


def test_internal_users_lists_members_by_id(client, login):
    headers = login("alice")
    login("bob")

    assert client.get("/internal/users", headers=headers).get_json() == [
        {"id": 1, "username": "alice"},
        {"id": 2, "username": "bob"},
    ]


def test_internal_contributions_returns_the_three_lists(client, login):
    alice, bob = login("alice"), login("bob")
    done = _new_task(client, alice, difficulty="hard").get_json()["id"]
    client.post(f"/tasks/{done}/claim", headers=alice)
    client.post(f"/tasks/{done}/complete", headers=alice)
    late = _new_task(client, bob, due_date="2020-01-01T10:00").get_json()["id"]
    client.post(f"/tasks/{late}/claim", headers=bob)
    start = utc_now() + timedelta(days=1)
    client.post(
        "/bookings",
        json={"resource": "kitchen", "start_time": _iso(start), "end_time": _iso(start + timedelta(hours=1))},
        headers=bob,
    )
    now = utc_now()

    response = client.get(
        "/internal/contributions",
        query_string={
            "start": (now - timedelta(days=1)).isoformat(),
            "end": (now + timedelta(days=2)).isoformat(),
            "as_of": now.isoformat(),
        },
        headers=alice,
    )

    body = response.get_json()
    assert [(t["user_id"], t["difficulty"]) for t in body["completed_tasks"]] == [(1, "hard")]
    assert "T" in body["completed_tasks"][0]["completed_at"]
    assert body["bookings"] == [{"user_id": 2}]
    assert body["overdue"] == [{"user_id": 2, "overdue_tasks": 1}]


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"start": "2026-01-01T00:00:00", "end": "2026-02-01T00:00:00"},
        {"start": "nope", "end": "2026-02-01T00:00:00", "as_of": "2026-02-01T00:00:00"},
        {"start": "2026-03-01T00:00:00", "end": "2026-02-01T00:00:00", "as_of": "2026-02-01T00:00:00"},
    ],
)
def test_internal_contributions_rejects_bad_parameters(client, login, params):
    response = client.get("/internal/contributions", query_string=params, headers=login("alice"))

    assert response.status_code == 400
    assert "error" in response.get_json()


# --- health, CORS, errors, logging, startup -----------------------------------------------


def test_health_is_ok_and_reports_the_version(app, client):
    app.config["GIT_SHA"] = "abc1234"

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "db": "ok", "version": "abc1234"}


def test_health_is_503_when_the_database_is_not_usable(client):
    db.session.execute(text("DROP TABLE task"))
    db.session.commit()

    response = client.get("/health")

    assert response.status_code == 503
    assert response.get_json()["db"] == "error"


def test_health_does_not_change_data(client, login):
    headers = login("alice")
    _new_task(client, headers, title="Original")

    client.get("/health")

    assert client.get("/tasks", headers=headers).get_json()[0]["title"] == "Original"


def test_cors_allows_only_the_ui_origin(app, client):
    allowed = app.config["CORS_ORIGIN"]

    ok = client.options("/tasks", headers={"Origin": allowed, "Access-Control-Request-Method": "GET"})
    other = client.options(
        "/tasks", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"}
    )

    assert ok.headers["Access-Control-Allow-Origin"] == allowed
    assert "Access-Control-Allow-Origin" not in other.headers


def test_unknown_route_and_wrong_method_return_json(client):
    missing = client.get("/nope")
    assert missing.status_code == 404 and "error" in missing.get_json()
    wrong = client.put("/tasks")
    assert wrong.status_code == 405 and "error" in wrong.get_json()


def test_unexpected_error_is_a_json_500_without_a_stack_trace(app, client, login, monkeypatch):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    headers = login("alice")

    def explode(user):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("app.domain1.services.list_tasks", explode)

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error."}


def test_every_request_is_logged_with_method_path_status_and_duration(client):
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    log = logging.getLogger("housemate.requests")
    handler = Capture()
    log.addHandler(handler)
    try:
        client.get("/health")
        client.get("/tasks")
    finally:
        log.removeHandler(handler)

    assert records[0].startswith("GET /health 200 ") and records[0].endswith("ms")
    assert records[1].startswith("GET /tasks 401 ")


def test_create_app_refuses_to_start_without_a_secret(tmp_path):
    from app import create_app

    with pytest.raises(RuntimeError, match="AUTH_SECRET"):
        create_app({"AUTH_SECRET": None, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'x.db'}"})


def test_token_for_a_deleted_user_is_rejected(client, login):
    from app.models import User

    headers = login("alice")
    db.session.delete(db.session.get(User, 1))
    db.session.commit()

    assert client.get("/tasks", headers=headers).status_code == 401


def test_expired_token_is_rejected(app, client, login):
    headers = login("alice")
    app.config["TOKEN_MAX_AGE_S"] = -1

    assert client.get("/tasks", headers=headers).status_code == 401


@pytest.mark.parametrize("header", ["Token abc", "Bearer", "", "basic Zm9v"])
def test_malformed_authorization_header_is_rejected(client, header):
    assert client.get("/tasks", headers={"Authorization": header}).status_code == 401
