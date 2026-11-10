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
    from app import models  # noqa: F401
    from app.domain2 import bp as domain2_bp
    from app.observability import init_request_logging, register_health

    app.register_blueprint(domain2_bp)

    init_request_logging(app)
    register_health(app, db, models.ContributionScore, "user_id")

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Unhandled error")
        return jsonify(error="Internal server error."), 500

    with app.app_context():
        db.create_all()

    return app
