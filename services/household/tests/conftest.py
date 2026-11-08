import pytest
from sqlalchemy.pool import StaticPool

from app import create_app, db


@pytest.fixture()
def app(tmp_path):
    test_db = tmp_path / "test_app.db"
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{test_db}",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
        }
    )

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
