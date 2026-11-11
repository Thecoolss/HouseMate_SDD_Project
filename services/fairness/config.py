import os
from pathlib import Path


def _database_url():
    # In compose and on Azure, DATABASE_URL points at this service's SQL Server database,
    # e.g. mssql+pymssql://fairness_user:<password>@sqlserver:1433/fairness.
    # Without it (running the service on its own), fall back to a SQLite file in DATA_DIR.
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    data_dir = Path(os.environ.get("DATA_DIR", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'app.db'}"


class Config:
    PORT = int(os.environ.get("PORT", 5001))

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Test each pooled connection before use, so a connection dropped by the database
    # (restart, idle timeout) is replaced instead of failing the request.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Verifies the bearer tokens household issues. Must equal household's AUTH_SECRET.
    # It is a secret, so it has no default.
    AUTH_SECRET = os.environ.get("AUTH_SECRET")
    TOKEN_MAX_AGE_S = int(os.environ.get("TOKEN_MAX_AGE_S", 3 * 24 * 60 * 60))

    # Location of the household service for cross-seam calls (no hardcoded host or port).
    HOUSEHOLD_URL = os.environ.get("HOUSEHOLD_URL", "http://localhost:5000")
    HOUSEHOLD_TIMEOUT_S = float(os.environ.get("HOUSEHOLD_TIMEOUT_S", 5.0))

    # The only browser origin allowed to call this service (the static UI).
    CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:8080")

    # Reported by /health so a deployment can be traced to a commit.
    GIT_SHA = os.environ.get("GIT_SHA", "dev")
