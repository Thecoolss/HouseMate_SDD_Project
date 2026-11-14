import pytest
from sqlalchemy.pool import StaticPool

from app import create_app, db


@pytest.fixture()
def app(tmp_path):
    test_db = tmp_path / "test_app.db"
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

    # create_app() already ran the migrations once on this fresh database. The tests
    # exercise the same migrated schema the service runs in production, not an ORM
    # create_all(), so a mismatch between the models and the migrations would fail here.
    with app.app_context():
        yield app
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def make_token(app):
    """Sign a token the way the household service does (same secret and salt)."""
    from itsdangerous import URLSafeTimedSerializer

    def make(user_id=1, username="alice", secret=None):
        serializer = URLSafeTimedSerializer(
            secret or app.config["AUTH_SECRET"], salt="housemate-auth"
        )
        return serializer.dumps({"user_id": user_id, "username": username})

    return make


@pytest.fixture()
def auth(make_token):
    return {"Authorization": f"Bearer {make_token()}"}
