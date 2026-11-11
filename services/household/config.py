import os
from pathlib import Path


class Config:
    PORT = int(os.environ.get("PORT", 5000))
    DATA_DIR = Path(os.environ.get("DATA_DIR", "./data")).resolve()
    HOUSEHOLD_TIMEZONE = os.environ.get("HOUSEHOLD_TIMEZONE", "Europe/Paris")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATA_DIR / 'app.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Signs the bearer tokens household issues at login. Fairness verifies them with the same
    # secret, so both services must get the same value. It is a secret, so it has no default.
    AUTH_SECRET = os.environ.get("AUTH_SECRET")
    TOKEN_MAX_AGE_S = int(os.environ.get("TOKEN_MAX_AGE_S", 3 * 24 * 60 * 60))

    # The only browser origin allowed to call this service (the static UI).
    CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:8080")

    # Reported by /health so a deployment can be traced to a commit.
    GIT_SHA = os.environ.get("GIT_SHA", "dev")
