from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from config import Config


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import __init__  # noqa: F401
    from app.auth import __init__  # noqa: F401
    from app.domain1 import __init__  # noqa: F401
    from app.domain2 import __init__  # noqa: F401

    with app.app_context():
        db.create_all()

    return app
