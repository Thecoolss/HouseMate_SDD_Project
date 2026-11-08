from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from app.time_utils import format_local_datetime
from config import Config


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


@login_manager.user_loader
def load_user(user_id):
    from app.models import User

    return db.session.get(User, int(user_id))




def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config is not None:
        app.config.from_mapping(test_config)
    login_manager.login_view = "auth.login"

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Importing the models package registers every model with SQLAlchemy before create_all().
    # "import app.models" is not used here because it would rebind the local name "app"
    # (the Flask instance) to the app package.
    from app import models  # noqa: F401
    from app.auth import bp as auth_bp
    from app.domain1 import bp as domain1_bp
    from app.domain2 import bp as domain2_bp

    app.register_blueprint(auth_bp, url_prefix="")
    app.register_blueprint(domain1_bp, url_prefix="")
    app.register_blueprint(domain2_bp, url_prefix="")

    @app.get("/")
    def home():
        from flask_login import current_user

        if current_user.is_authenticated:
            return redirect(url_for("domain1.list_tasks"))
        return redirect(url_for("auth.login"))
    app.add_template_filter(format_local_datetime, "localdatetime")

    with app.app_context():
        db.create_all()

    return app
