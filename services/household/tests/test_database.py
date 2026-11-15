"""Connection retries cover paused SQL, bad credentials and the deadline without sleeping."""
from types import SimpleNamespace

import pytest

from app import database


class Clock:
    value = 0
    sleeps = None

    def __init__(self):
        self.sleeps = []

    def now(self):
        return self.value

    def sleep(self, duration):
        self.sleeps.append(duration)
        self.value += duration


def test_paused_database_recovers_with_backoff():
    clock = Clock()
    attempts = []
    def connect():
        attempts.append(1)
        if len(attempts) < 4:
            raise RuntimeError("40613 database is unavailable")
        return "connection"
    assert database.connect_with_retry(connect, 30, clock=clock.now, sleep=clock.sleep) == "connection"
    assert clock.sleeps == [1, 2, 4]


@pytest.mark.parametrize("message", ["18456 login failed 20002", "4060 database denied", "syntax error 102"])
def test_permanent_failure_is_not_retried(message):
    clock = Clock()
    def connect():
        raise RuntimeError(message)
    with pytest.raises(RuntimeError, match=message):
        database.connect_with_retry(connect, 90, clock=clock.now, sleep=clock.sleep)
    assert clock.sleeps == []


def test_retry_stops_at_deadline_and_backoff_is_capped():
    clock = Clock()
    def connect():
        raise RuntimeError("40613 unavailable")
    with pytest.raises(RuntimeError):
        database.connect_with_retry(connect, 30, clock=clock.now, sleep=clock.sleep)
    assert clock.value == 30
    assert max(clock.sleeps) == 10


def test_sqlite_does_not_install_retry(monkeypatch):
    def unexpected(*args):
        pytest.fail("SQLite must not install the SQL Server listener")
    monkeypatch.setattr(database.event, "listens_for", unexpected)
    database.install_connection_retry(SimpleNamespace(dialect=SimpleNamespace(name="sqlite")), 90)


def test_mssql_listener_retries_dbapi_connect(monkeypatch):
    listeners = []
    def register(engine, name):
        assert name == "do_connect"
        def decorator(fn):
            listeners.append(fn)
            return fn
        return decorator
    monkeypatch.setattr(database.event, "listens_for", register)
    engine = SimpleNamespace(dialect=SimpleNamespace(name="mssql"))
    database.install_connection_retry(engine, 90)
    calls = []
    def connect(*args, **kwargs):
        calls.append((args, kwargs))
        return "dbapi connection"
    dialect = SimpleNamespace(dbapi=SimpleNamespace(connect=connect))
    assert listeners[0](dialect, None, ["host"], {"login_timeout": 5}) == "dbapi connection"
    assert calls == [(("host",), {"login_timeout": 5})]
