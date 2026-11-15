"""Retry only transient SQL connection failures, never a transaction or migration."""

import re
import time

from sqlalchemy import event

# Azure SQL paused/resuming, temporary service errors and network connection failures.
_TRANSIENT = {40613, 40197, 40501, 10928, 10929, 49918, 49919, 49920, 20002, 20003, 20009}


def connect_with_retry(connect, timeout_s, *, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + timeout_s
    delay = 1
    while True:
        try:
            return connect()
        except Exception as error:
            codes = {int(value) for value in re.findall(r"\b\d{4,5}\b", str(error))}
            remaining = deadline - clock()
            if codes.intersection({18456, 4060, 916}) or not codes.intersection(_TRANSIENT) or remaining <= 0:
                raise
            # Never log the exception/connection parameters: they may contain credentials.
            print("Database connection temporarily unavailable; retrying", flush=True)
            sleep(min(delay, remaining))
            delay = min(delay * 2, 10)


def install_connection_retry(engine, timeout_s):
    if engine.dialect.name != "mssql":
        return

    @event.listens_for(engine, "do_connect")
    def connect(dialect, connection_record, args, kwargs):
        return connect_with_retry(lambda: dialect.dbapi.connect(*args, **kwargs), timeout_s)
