"""Small helpers shared by the household JSON routes."""

from datetime import datetime

from flask import abort, jsonify, request

from app.time_utils import local_to_utc_naive

_NOT_FOUND_MESSAGES = {"Task not found.", "Booking not found."}


def json_body():
    """The request's JSON object, or a 400 if the body is not a JSON object."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="The request body must be a JSON object.")
    return body


def parse_datetime(value, label):
    """ISO 8601 string -> naive UTC datetime. Naive input is household local time."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"Enter a valid {label}.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Enter a valid {label}.") from None
    return local_to_utc_naive(parsed)


def iso_utc(value):
    """Stored naive UTC datetime -> ISO 8601 string with a Z suffix."""
    return value.isoformat() + "Z" if value is not None else None


def error_response(error):
    """Map service-layer exceptions to HTTP responses."""
    if isinstance(error, PermissionError):
        return jsonify(error=str(error)), 403
    if str(error) in _NOT_FOUND_MESSAGES:
        return jsonify(error=str(error)), 404
    return jsonify(error=str(error)), 400
