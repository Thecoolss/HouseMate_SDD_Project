"""Seam between the fairness service and the household service.

These three functions are the ONLY things the fairness domain needs from the
household domain (see ADR-2 and ADR-6). In the Assignment 1 monolith they lived
in ``app.domain1.services`` and ran SQL against the Task and Booking tables.

After the split those tables belong to the household service and its database,
which the fairness service cannot touch. On day 2 each function below becomes an
HTTP call to the household service (e.g. ``GET /internal/contributions``), with a
timeout and a designed failure, and the responses are plain JSON shaped exactly
like the dicts these functions used to return.

Day 1 is the mechanical split only: the functions are declared with their final
signatures so the domain2 logic and ADR-6 can reference a stable seam, but they
are not wired yet.
"""


def get_completed_task_contributions(period_start, period_end):
    """One dict per completed task in the period: {user_id, difficulty, completed_at}."""
    raise NotImplementedError(
        "Wired to the household service over HTTP on day 2 (GET /internal/contributions)."
    )


def get_booking_contributions(period_start, period_end):
    """One dict per booking that starts in the period: {user_id}."""
    raise NotImplementedError(
        "Wired to the household service over HTTP on day 2 (GET /internal/contributions)."
    )


def get_overdue_task_counts(calculated_at):
    """One dict per user with overdue pending tasks: {user_id, overdue_tasks}."""
    raise NotImplementedError(
        "Wired to the household service over HTTP on day 2 (GET /internal/contributions)."
    )
