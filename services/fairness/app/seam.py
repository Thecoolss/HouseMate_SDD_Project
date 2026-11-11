"""Seam between the fairness service and the household service (ADR-2, ADR-6).

Fairness never touches household's database. Everything it needs from the household
domain comes through the two functions below. They call household's internal HTTP
endpoints with the logged-in user's bearer token and a timeout, and turn any transport
or HTTP failure into HouseholdUnavailable.
"""

from datetime import datetime

import httpx
from flask import current_app


class HouseholdUnavailable(RuntimeError):
    """The household service could not be reached or returned an error."""


def _get_json(path, token, params=None):
    try:
        response = httpx.get(
            current_app.config["HOUSEHOLD_URL"] + path,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=current_app.config["HOUSEHOLD_TIMEOUT_S"],
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as error:
        raise HouseholdUnavailable(
            f"The household service returned status {error.response.status_code}."
        ) from error
    except httpx.HTTPError as error:
        raise HouseholdUnavailable("The household service is unavailable.") from error


def get_members(token):
    """Household members as [{id, username}]."""
    return _get_json("/internal/users", token)


def get_contributions(token, period_start, period_end, calculated_at):
    """Contribution data for the period, as one dict with three lists.

    completed_tasks: [{user_id, difficulty, completed_at}]
    bookings:        [{user_id}]
    overdue:         [{user_id, overdue_tasks}]
    """
    data = _get_json(
        "/internal/contributions",
        token,
        params={
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "as_of": calculated_at.isoformat(),
        },
    )
    for task in data["completed_tasks"]:
        task["completed_at"] = datetime.fromisoformat(task["completed_at"])
    return data
