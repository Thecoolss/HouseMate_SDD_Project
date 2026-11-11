import os
from pathlib import Path


class Config:
    PORT = int(os.environ.get("PORT", 5001))
    DATA_DIR = Path(os.environ.get("DATA_DIR", "./data")).resolve()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATA_DIR / 'app.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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
