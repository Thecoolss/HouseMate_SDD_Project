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
def login(app):
    """Create a user and return the Authorization header carrying their token."""
    from app.models import User
    from app.tokens import issue_token

    def make(username):
        user = User(username=username)
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
        return {"Authorization": f"Bearer {issue_token(user)}"}

    return make
