from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from config import Config


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


@login_manager.user_loader
def load_user(user_id):
    from app.models import User

    return db.session.get(User, int(user_id))


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    login_manager.login_view = "auth.login"

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # These imports register the packages so SQLAlchemy and the auth blueprint are available.
    from app.models import __init__
    from app.auth import bp as auth_bp
    from app.domain1 import __init__
    from app.domain2 import __init__

    app.register_blueprint(auth_bp, url_prefix="")

    with app.app_context():
        db.create_all()

    return app
