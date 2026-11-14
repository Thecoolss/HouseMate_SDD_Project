"""Starts the real household and fairness services as separate processes.

Each service gets its own SQLite file (one database per service, as in production), a free
port, and the same AUTH_SECRET. Fairness is pointed at household through HOUSEHOLD_URL, so
the calls in these tests cross the real HTTP seam. No Docker is needed.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
SECRET = "integration-test-secret"


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Service:
    """One running service process."""

    def __init__(self, name, port, env):
        self.name = name
        self.port = port
        self.url = f"http://127.0.0.1:{port}"
        self.process = subprocess.Popen(
            [sys.executable, "-m", "gunicorn", "--bind", f"127.0.0.1:{port}", "app:create_app()"],
            cwd=ROOT / "services" / name,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def wait_until_healthy(self, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"{self.name} exited early:\n{self.output()}")
            try:
                if httpx.get(f"{self.url}/health", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise RuntimeError(f"{self.name} did not become healthy:\n{self.output()}")

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def output(self):
        if self.process.poll() is None:
            return "(still running)"
        return (self.process.stdout.read() or b"").decode(errors="replace")


class Stack:
    def __init__(self, household, fairness, household_db, fairness_db):
        self.household = household
        self.fairness = fairness
        self.household_db = household_db
        self.fairness_db = fairness_db

    def register(self, username):
        """Create a user in household and return (auth headers, user id)."""
        response = httpx.post(
            f"{self.household.url}/register", json={"username": username, "password": "pw"}
        )
        response.raise_for_status()
        body = response.json()
        return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


@pytest.fixture()
def stack(tmp_path):
    household_db = tmp_path / "household.db"
    fairness_db = tmp_path / "fairness.db"
    household_port, fairness_port = _free_port(), _free_port()
    base = {**os.environ, "AUTH_SECRET": SECRET, "GIT_SHA": "integration"}

    household = Service(
        "household",
        household_port,
        {**base, "DATABASE_URL": f"sqlite:///{household_db}", "PORT": str(household_port)},
    )
    fairness = Service(
        "fairness",
        fairness_port,
        {
            **base,
            "DATABASE_URL": f"sqlite:///{fairness_db}",
            "PORT": str(fairness_port),
            "HOUSEHOLD_URL": household.url,
            "HOUSEHOLD_TIMEOUT_S": "2",
        },
    )
    try:
        household.wait_until_healthy()
        fairness.wait_until_healthy()
        yield Stack(household, fairness, household_db, fairness_db)
    finally:
        household.stop()
        fairness.stop()
