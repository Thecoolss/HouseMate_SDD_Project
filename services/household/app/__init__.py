from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.exceptions import HTTPException

from config import Config


db = SQLAlchemy()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config is not None:
        app.config.from_mapping(test_config)
    if not app.config.get("AUTH_SECRET"):
        raise RuntimeError("AUTH_SECRET must be set.")

    db.init_app(app)
    # Only the static UI's origin may call this service from a browser.
    CORS(app, origins=[app.config["CORS_ORIGIN"]])

    # Importing the models package registers every model with SQLAlchemy before create_all().
    # "import app.models" is not used here because it would rebind the local name "app"
    # (the Flask instance) to the app package.
    from app import models  # noqa: F401
    from app.auth import bp as auth_bp
    from app.domain1 import bp as domain1_bp
    from app.internal import bp as internal_bp
    from app.observability import init_request_logging, register_health

    app.register_blueprint(auth_bp)
    app.register_blueprint(domain1_bp)
    app.register_blueprint(internal_bp, url_prefix="/internal")

    init_request_logging(app)
    register_health(app, db, models.Task, "title")

    @app.errorhandler(HTTPException)
    def http_error(error):
        # 404, 405 and similar come back as JSON, like every other response.
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Unhandled error")
        return jsonify(error="Internal server error."), 500

    # The schema comes from the versioned migrations, not db.create_all(). The runner
    # applies any that have not run yet and records them, so a second boot does nothing.
    from app.migrations import run_migrations

    with app.app_context():
        run_migrations(db.engine)

    return app
