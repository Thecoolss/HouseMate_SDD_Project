"""The fairness HTTP API: auth, the two routes, health, CORS, logging and error shape."""

import logging
from datetime import date, datetime

import pytest
from sqlalchemy import text

from app import db, seam
from app.domain2 import services
from app.models import ContributionScore
from app.seam import HouseholdUnavailable

NOW = datetime(2026, 11, 10, 12, 0)


def _score(user_id, calculated_at, percent):
    return ContributionScore(
        user_id=user_id,
        period_start=date(2026, 10, 11),
        period_end=date(2026, 11, 10),
        tasks_completed=1,
        weighted_score=3.0,
        bookings_count=0,
        overdue_tasks=0,
        contribution_score=percent,
        calculated_at=calculated_at,
    )


def _household_up(monkeypatch, members):
    monkeypatch.setattr("app.domain2.routes.get_members", lambda token: members)
    monkeypatch.setattr(services, "get_members", lambda token: members)
    monkeypatch.setattr(
        services,
        "get_contributions",
        lambda token, start, end, as_of: {
            "completed_tasks": [{"user_id": 1, "difficulty": "hard", "completed_at": NOW}],
            "bookings": [],
            "overdue": [],
        },
    )


def _household_down(monkeypatch):
    def down(token):
        raise HouseholdUnavailable("The household service is unavailable.")

    monkeypatch.setattr("app.domain2.routes.get_members", down)
    monkeypatch.setattr(services, "get_members", down)


# --- authentication -----------------------------------------------------------------------


def test_routes_require_a_token(client):
    assert client.get("/fairness").status_code == 401
    assert client.post("/fairness/recalculate").status_code == 401


@pytest.mark.parametrize("header", ["Token abc", "Bearer", "Bearer ", "basic Zm9v", ""])
def test_malformed_authorization_header_is_rejected(client, header):
    response = client.get("/fairness", headers={"Authorization": header})

    assert response.status_code == 401
    assert response.get_json() == {"error": "Authentication required."}


def test_tampered_token_is_rejected(client, make_token):
    response = client.get("/fairness", headers={"Authorization": f"Bearer {make_token()}x"})

    assert response.status_code == 401


def test_token_signed_with_another_secret_is_rejected(client, make_token):
    forged = make_token(secret="not-the-shared-secret")

    assert client.get("/fairness", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_expired_token_is_rejected(app, client, auth):
    app.config["TOKEN_MAX_AGE_S"] = -1

    response = client.get("/fairness", headers=auth)

    assert response.status_code == 401
    assert "expired" in response.get_json()["error"].lower()


# --- GET /fairness ------------------------------------------------------------------------


def test_fairness_lists_each_member_with_their_latest_snapshot(app, client, auth, monkeypatch):
    db.session.add_all(
        [
            _score(1, datetime(2026, 11, 1), 10.0),
            _score(1, datetime(2026, 11, 9), 60.0),
            _score(2, datetime(2026, 11, 9), 40.0),
        ]
    )
    db.session.commit()
    _household_up(monkeypatch, [{"id": 2, "username": "bob"}, {"id": 1, "username": "alice"}, {"id": 3, "username": "cy"}])

    body = client.get("/fairness", headers=auth).get_json()

    assert body["household_available"] is True
    assert [row["username"] for row in body["rows"]] == ["alice", "bob", "cy"]
    assert body["rows"][0]["snapshot"]["contribution_score"] == 60.0
    assert body["rows"][1]["snapshot"]["contribution_score"] == 40.0
    assert body["rows"][2]["snapshot"] is None


def test_fairness_still_answers_when_household_is_down(app, client, auth, monkeypatch):
    db.session.add_all([_score(1, datetime(2026, 11, 9), 60.0), _score(2, datetime(2026, 11, 9), 40.0)])
    db.session.commit()
    _household_down(monkeypatch)

    response = client.get("/fairness", headers=auth)

    assert response.status_code == 200
    body = response.get_json()
    assert body["household_available"] is False
    assert [(row["user_id"], row["username"]) for row in body["rows"]] == [(1, None), (2, None)]
    assert body["rows"][0]["snapshot"]["contribution_score"] == 60.0


def test_fairness_with_no_data_and_household_down_is_empty(client, auth, monkeypatch):
    _household_down(monkeypatch)

    body = client.get("/fairness", headers=auth).get_json()

    assert body == {"household_available": False, "rows": []}


# --- POST /fairness/recalculate -----------------------------------------------------------


def test_recalculate_stores_and_returns_snapshots(client, auth, monkeypatch):
    _household_up(monkeypatch, [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}])

    response = client.post("/fairness/recalculate", headers=auth)

    assert response.status_code == 201
    scores = {row["user_id"]: row for row in response.get_json()["scores"]}
    assert scores[1]["contribution_score"] == 100.0
    assert scores[2]["contribution_score"] == 0.0
    assert ContributionScore.query.count() == 2


def test_recalculate_returns_503_and_stores_nothing_when_household_is_down(client, auth, monkeypatch):
    _household_down(monkeypatch)

    response = client.post("/fairness/recalculate", headers=auth)

    assert response.status_code == 503
    assert "household service is unavailable" in response.get_json()["error"]
    assert ContributionScore.query.count() == 0


def test_recalculate_forwards_the_callers_token_to_household(client, make_token, monkeypatch):
    seen = []
    monkeypatch.setattr(services, "get_members", lambda token: seen.append(token) or [])
    monkeypatch.setattr(
        services,
        "get_contributions",
        lambda token, *a: seen.append(token) or {"completed_tasks": [], "bookings": [], "overdue": []},
    )
    token = make_token(user_id=7, username="gus")

    client.post("/fairness/recalculate", headers={"Authorization": f"Bearer {token}"})

    assert seen == [token, token]


# --- /health ------------------------------------------------------------------------------


def test_health_is_ok_and_reports_the_version(app, client):
    app.config["GIT_SHA"] = "abc1234"

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "db": "ok", "version": "abc1234"}


def test_health_needs_no_token(client):
    assert client.get("/health").status_code == 200


def test_health_is_503_when_the_database_is_not_usable(client):
    db.session.execute(text("DROP TABLE contribution_score"))
    db.session.commit()

    response = client.get("/health")

    assert response.status_code == 503
    assert response.get_json()["status"] == "error"
    assert response.get_json()["db"] == "error"


def test_health_does_not_depend_on_household(client, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("health must not call the household service")

    monkeypatch.setattr(seam.httpx, "get", boom)

    assert client.get("/health").status_code == 200


def test_health_does_not_change_data(client):
    db.session.add(_score(1, NOW, 50.0))
    db.session.commit()

    client.get("/health")

    assert ContributionScore.query.one().contribution_score == 50.0


# --- CORS, errors, request log -----------------------------------------------------------


def test_cors_allows_only_the_ui_origin(app, client):
    allowed = app.config["CORS_ORIGIN"]

    ok = client.options(
        "/fairness",
        headers={"Origin": allowed, "Access-Control-Request-Method": "GET"},
    )
    other = client.options(
        "/fairness",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert ok.headers["Access-Control-Allow-Origin"] == allowed
    assert "Access-Control-Allow-Origin" not in other.headers


def test_unknown_route_returns_json(client):
    response = client.get("/nope")

    assert response.status_code == 404
    assert "error" in response.get_json()


def test_unexpected_error_is_a_json_500_without_a_stack_trace(app, client, auth, monkeypatch):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    def explode():
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("app.domain2.routes._latest_snapshots", explode)

    response = client.get("/fairness", headers=auth)

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
        client.get("/nope")
    finally:
        log.removeHandler(handler)

    assert records[0].startswith("GET /health 200 ") and records[0].endswith("ms")
    assert records[1].startswith("GET /nope 404 ")


def test_create_app_refuses_to_start_without_a_secret(tmp_path):
    from app import create_app

    with pytest.raises(RuntimeError, match="AUTH_SECRET"):
        create_app({"AUTH_SECRET": None, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'x.db'}"})
