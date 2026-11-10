from datetime import datetime, timezone


def utc_now():
    # Timestamps are stored as naive UTC values, so drop tzinfo after reading the aware UTC time.
    return datetime.now(timezone.utc).replace(tzinfo=None)
