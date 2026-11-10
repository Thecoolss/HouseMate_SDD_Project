from sqlalchemy.pool import StaticPool

from app import create_app, db
from app.models import User


def test_create_app_allows_test_database_override(tmp_path):
    test_db = tmp_path / "isolated_test.db"
    app = create_app(
        {
            "TESTING": True,
            "AUTH_SECRET": "test-auth-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{test_db}",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
        }
    )

    with app.app_context():
        assert app.config["SQLALCHEMY_DATABASE_URI"] == f"sqlite:///{test_db}"
        assert "data/app.db" not in app.config["SQLALCHEMY_DATABASE_URI"]


def _register(client, username, password="secret123"):
    return client.post("/register", json={"username": username, "password": password})


def _login(client, username, password="secret123"):
    return client.post("/login", json={"username": username, "password": password})


def _create_user(app, username, password="secret123"):
    with app.app_context():
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


def test_successful_registration_returns_token(client, app):
    response = _register(client, "alice")

    assert response.status_code == 201
    body = response.get_json()
    assert body["token"]
    assert body["user"]["username"] == "alice"

    with app.app_context():
        assert User.query.filter_by(username="alice").count() == 1


def test_empty_password_registration_rejected(client, app):
    # Regression test: the UI marks the field required, but a direct request can still omit it.
    response = _register(client, "alice", password="")

    assert response.status_code == 400
    assert "password is required" in response.get_json()["error"].lower()

    with app.app_context():
        assert User.query.filter_by(username="alice").count() == 0


def test_duplicate_username_rejection(client, app):
    _create_user(app, "alice")

    response = _register(client, "alice")

    assert response.status_code == 409
    assert "already taken" in response.get_json()["error"].lower()


def test_successful_login_returns_token(client, app):
    _create_user(app, "alice")

    response = _login(client, "alice")

    assert response.status_code == 200
    assert response.get_json()["token"]


def test_wrong_password_rejection(client, app):
    _create_user(app, "alice")

    response = _login(client, "alice", password="wrong-password")

    assert response.status_code == 401
    assert "invalid username or password" in response.get_json()["error"].lower()


def test_protected_route_requires_token(client):
    assert client.get("/tasks").status_code == 401


def test_protected_route_rejects_tampered_token(client, app):
    _create_user(app, "alice")
    token = _login(client, "alice").get_json()["token"]

    response = client.get("/tasks", headers={"Authorization": f"Bearer {token}x"})

    assert response.status_code == 401


def test_protected_route_accepts_valid_token(client, app):
    _create_user(app, "alice")
    token = _login(client, "alice").get_json()["token"]

    response = client.get("/tasks", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.get_json() == []
