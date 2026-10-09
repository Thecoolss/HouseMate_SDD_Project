from app import create_app, db
from app.models import User


def test_create_app_allows_test_database_override(tmp_path):
    test_db = tmp_path / "isolated_test.db"
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{test_db}",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": __import__("sqlalchemy.pool").pool.StaticPool,
                "connect_args": {"check_same_thread": False},
            },
        }
    )

    with app.app_context():
        assert app.config["SQLALCHEMY_DATABASE_URI"] == f"sqlite:///{test_db}"
        assert "data/app.db" not in app.config["SQLALCHEMY_DATABASE_URI"]


def _register(client, username, password="secret123"):
    return client.post(
        "/register",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def _create_user(app, username, password="secret123"):
    with app.app_context():
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


def test_successful_registration(client, app):
    response = _register(client, "alice")

    assert response.status_code == 200
    assert "create the first task" in response.get_data(as_text=True).lower()

    with app.app_context():
        assert User.query.filter_by(username="alice").count() == 1


def test_empty_password_registration_rejected(client, app):
    # Regression test: a direct POST bypasses the form's "required" attribute.
    response = _register(client, "alice", password="")

    assert response.status_code == 200
    assert "password is required" in response.get_data(as_text=True).lower()

    with app.app_context():
        assert User.query.filter_by(username="alice").count() == 0

    with client.session_transaction() as session:
        assert "_user_id" not in session


def test_duplicate_username_rejection(client, app):
    _create_user(app, "alice", "secret123")

    with client.session_transaction() as session:
        session.clear()

    response = _register(client, "alice")

    assert response.status_code == 200
    assert "already taken" in response.get_data(as_text=True).lower()


def test_successful_login(client, app):
    _create_user(app, "alice", "secret123")

    response = client.post(
        "/login",
        data={"username": "alice", "password": "secret123"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "create the first task" in response.get_data(as_text=True).lower()


def test_wrong_password_rejection(client, app):
    _create_user(app, "alice", "secret123")

    response = client.post(
        "/login",
        data={"username": "alice", "password": "wrong-password"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "invalid username or password" in response.get_data(as_text=True).lower()


def test_logout(client, app):
    _create_user(app, "alice", "secret123")
    client.post(
        "/login",
        data={"username": "alice", "password": "secret123"},
        follow_redirects=True,
    )

    response = client.post("/logout", follow_redirects=True)

    assert response.status_code == 200
    assert "login" in response.get_data(as_text=True).lower()

    with client.session_transaction() as session:
        assert "_user_id" not in session


def test_authenticated_session_behavior(client, app):
    _create_user(app, "alice", "secret123")
    client.post(
        "/login",
        data={"username": "alice", "password": "secret123"},
        follow_redirects=True,
    )

    login_response = client.get("/login")
    register_response = client.get("/register")

    assert login_response.status_code == 302
    assert login_response.headers["Location"].endswith("/tasks")

    assert register_response.status_code == 302
    assert register_response.headers["Location"].endswith("/tasks")
