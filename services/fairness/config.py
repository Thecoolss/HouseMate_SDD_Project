import os
from datetime import timedelta
from pathlib import Path


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    PORT = int(os.environ.get("PORT", 5000))
    DATA_DIR = Path(os.environ.get("DATA_DIR", "./data")).resolve()
    HOUSEHOLD_TIMEZONE = os.environ.get("HOUSEHOLD_TIMEZONE", "Europe/Paris")
    # Location of the household service for cross-seam calls (Assignment 2 §1a).
    HOUSEHOLD_URL = os.environ.get("HOUSEHOLD_URL", "http://localhost:5000")
    # Timeout for HTTP calls to household (seconds).
    HOUSEHOLD_TIMEOUT_S = float(os.environ.get("HOUSEHOLD_TIMEOUT_S", 5.0))
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATA_DIR / 'app.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True

    PERMANENT_SESSION_LIFETIME = timedelta(days=3)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
