from flask import g, jsonify

from app import db
from app.api_utils import error_response, iso_utc, json_body, parse_datetime
from app.domain1 import bp
from app.domain1 import services
from app.models import User
from app.tokens import require_auth


def _usernames(user_ids):
    user_ids = {user_id for user_id in user_ids if user_id is not None}
    if not user_ids:
        return {}
    rows = db.session.execute(db.select(User.id, User.username).where(User.id.in_(user_ids)))
    return dict(rows.all())


def _task_json(task, usernames):
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "difficulty": task.difficulty,
        "status": task.status,
        "created_by": task.created_by,
        "created_by_username": usernames.get(task.created_by),
        "assigned_to": task.assigned_to,
        "assigned_to_username": usernames.get(task.assigned_to),
        "due_date": iso_utc(task.due_date),
        "created_at": iso_utc(task.created_at),
        "completed_at": iso_utc(task.completed_at),
    }


def _one_task(task):
    return _task_json(task, _usernames([task.created_by, task.assigned_to]))


def _booking_json(booking, usernames):
    return {
        "id": booking.id,
        "resource": booking.resource,
        "start_time": iso_utc(booking.start_time),
        "end_time": iso_utc(booking.end_time),
        "created_by": booking.created_by,
        "created_by_username": usernames.get(booking.created_by),
        "created_at": iso_utc(booking.created_at),
    }


def _one_booking(booking):
    return _booking_json(booking, _usernames([booking.created_by]))


# --- Tasks -------------------------------------------------------------------------------


@bp.get("/tasks")
@require_auth
def list_tasks():
    tasks = services.list_tasks(g.user)
    usernames = _usernames(
        [task.created_by for task in tasks] + [task.assigned_to for task in tasks]
    )
    return jsonify([_task_json(task, usernames) for task in tasks])


@bp.post("/tasks")
@require_auth
def create_task():
    body = json_body()
    try:
        task = services.create_task(
            g.user,
            title=body.get("title"),
            description=body.get("description") or None,
            difficulty=body.get("difficulty"),
            due_date=parse_datetime(body.get("due_date"), "due date"),
        )
    except ValueError as error:
        return error_response(error)
    return jsonify(_one_task(task)), 201


@bp.patch("/tasks/<int:task_id>")
@require_auth
def update_task(task_id):
    """Fields left out of the body are unchanged; description or due_date set to null clear it."""
    body = json_body()
    changes = {"title": body.get("title"), "difficulty": body.get("difficulty")}
    try:
        if "description" in body:
            changes["description"] = body["description"] or None
        if "due_date" in body:
            changes["due_date"] = parse_datetime(body["due_date"], "due date")
        task = services.update_task(g.user, task_id, **changes)
    except (PermissionError, ValueError) as error:
        return error_response(error)
    return jsonify(_one_task(task))


@bp.delete("/tasks/<int:task_id>")
@require_auth
def delete_task(task_id):
    try:
        services.delete_task(g.user, task_id)
    except (PermissionError, ValueError) as error:
        return error_response(error)
    return "", 204


@bp.post("/tasks/<int:task_id>/claim")
@require_auth
def claim_task(task_id):
    try:
        task = services.claim_task(g.user, task_id)
    except ValueError as error:
        return error_response(error)
    return jsonify(_one_task(task))


@bp.post("/tasks/<int:task_id>/complete")
@require_auth
def complete_task(task_id):
    try:
        task = services.mark_complete(g.user, task_id)
    except (PermissionError, ValueError) as error:
        return error_response(error)
    return jsonify(_one_task(task))


# --- Bookings ----------------------------------------------------------------------------


@bp.get("/bookings")
@require_auth
def list_bookings():
    bookings = services.list_bookings(g.user)
    usernames = _usernames([booking.created_by for booking in bookings])
    return jsonify([_booking_json(booking, usernames) for booking in bookings])


@bp.post("/bookings")
@require_auth
def create_booking():
    body = json_body()
    try:
        booking = services.create_booking(
            g.user,
            resource=body.get("resource"),
            start_time=parse_datetime(body.get("start_time"), "booking start time"),
            end_time=parse_datetime(body.get("end_time"), "booking end time"),
        )
    except ValueError as error:
        return error_response(error)
    return jsonify(_one_booking(booking)), 201


@bp.patch("/bookings/<int:booking_id>")
@require_auth
def update_booking(booking_id):
    """Fields left out of the body are unchanged."""
    body = json_body()
    try:
        booking = services.update_booking(
            g.user,
            booking_id,
            resource=body.get("resource"),
            start_time=parse_datetime(body.get("start_time"), "booking start time"),
            end_time=parse_datetime(body.get("end_time"), "booking end time"),
        )
    except (PermissionError, ValueError) as error:
        return error_response(error)
    return jsonify(_one_booking(booking))


@bp.delete("/bookings/<int:booking_id>")
@require_auth
def delete_booking(booking_id):
    try:
        services.delete_booking(g.user, booking_id)
    except (PermissionError, ValueError) as error:
        return error_response(error)
    return "", 204
