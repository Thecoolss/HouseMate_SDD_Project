
import logging
import sys
import time

from flask import g, jsonify, request

request_log = logging.getLogger("housemate.requests")


def init_request_logging(app):
    """Log one stdout line per request: method, path, status, duration."""
    if not request_log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        request_log.addHandler(handler)
        request_log.setLevel(logging.INFO)
        request_log.propagate = False

    @app.before_request
    def _start_timer():
        g.request_started = time.perf_counter()

    @app.after_request
    def _log_request(response):
        duration_ms = (time.perf_counter() - g.get("request_started", time.perf_counter())) * 1000
        request_log.info(
            "%s %s %s %.1fms", request.method, request.path, response.status_code, duration_ms
        )
        return response


def register_health(app, db, probe_model, probe_column):
    """GET /health: 200 if this service can read and write its own database, else 503.

    The write check is an UPDATE that matches no rows on a table this service owns, run
    inside a transaction that is rolled back. It needs write permission and a write lock,
    but never changes data. probe_column must be an ordinary column, not the IDENTITY id,
    which SQL Server refuses to update. Health only reflects this service.
    """
    column = getattr(probe_model, probe_column)

    @app.get("/health")
    def health():
        version = app.config["GIT_SHA"]
        try:
            db.session.execute(db.select(db.literal(1))).scalar_one()
            db.session.execute(
                db.update(probe_model).where(db.false()).values({probe_column: column})
            )
            db.session.rollback()
        except Exception:
            db.session.rollback()
            app.logger.exception("Health check failed")
            return jsonify(status="error", db="error", version=version), 503
        return jsonify(status="ok", db="ok", version=version), 200
