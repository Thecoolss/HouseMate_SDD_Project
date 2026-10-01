from datetime import datetime

from app import db
from app.models import Booking, Task


VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_BOOKING_RESOURCES = {"laundry", "kitchen", "living_room"}
_UNCHANGED = object()


def _get_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found.")
    return task


def get_task_for_edit(user, task_id):
    task = _get_task(task_id)
    if task.created_by != user.id:
        raise PermissionError("Only the task creator can edit this task.")
    return task


def _validate_title(title):
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Task title is required.")
    return title.strip()


def _validate_difficulty(difficulty):
    if difficulty not in VALID_DIFFICULTIES:
        raise ValueError("Difficulty must be easy, medium, or hard.")


def create_task(user, title, description, difficulty, due_date=None):
    title = _validate_title(title)
    _validate_difficulty(difficulty)

    task = Task(
        title=title,
        description=description,
        difficulty=difficulty,
        status="pending",
        assigned_to=None,
        created_by=user.id,
        due_date=due_date,
    )
    db.session.add(task)
    db.session.commit()
    return task


def update_task(
    user,
    task_id,
    title=None,
    description=_UNCHANGED,
    difficulty=None,
    due_date=_UNCHANGED,
):
    task = get_task_for_edit(user, task_id)

    if title is not None:
        task.title = _validate_title(title)
    if difficulty is not None:
        _validate_difficulty(difficulty)
        task.difficulty = difficulty

    if description is not _UNCHANGED:
        task.description = description
    if due_date is not _UNCHANGED:
        task.due_date = due_date
    db.session.commit()
    return task


def delete_task(user, task_id):
    task = _get_task(task_id)
    if task.created_by != user.id:
        raise PermissionError("Only the task creator can delete this task.")

    db.session.delete(task)
    db.session.commit()


def claim_task(user, task_id):
    task = _get_task(task_id)
    if task.status != "pending":
        raise ValueError("Only pending tasks can be claimed.")
    if task.assigned_to is not None:
        raise ValueError("This task has already been claimed.")

    task.assigned_to = user.id
    db.session.commit()
    return task


def mark_complete(user, task_id):
    task = _get_task(task_id)
    if task.status != "pending":
        raise ValueError("Only pending tasks can be completed.")
    if task.assigned_to != user.id:
        raise PermissionError("Only the assignee can complete this task.")

    task.status = "done"
    task.completed_at = datetime.utcnow()
    db.session.commit()
    return task


def list_tasks(user):
    return Task.query.order_by(Task.created_at.desc()).all()


def get_completed_task_contributions(period_start, period_end):
    if period_start is None or period_end is None or period_start > period_end:
        raise ValueError("The contribution period is invalid.")

    rows = db.session.execute(
        db.select(Task.assigned_to, Task.difficulty, Task.completed_at)
        .where(
            Task.status == "done",
            Task.assigned_to.is_not(None),
            Task.completed_at >= period_start,
            Task.completed_at <= period_end,
        )
        .order_by(Task.completed_at.asc())
    )
    return [
        {
            "user_id": user_id,
            "difficulty": difficulty,
            "completed_at": completed_at,
        }
        for user_id, difficulty, completed_at in rows
    ]


def get_overdue_task_counts(calculated_at):
    if not isinstance(calculated_at, datetime):
        raise ValueError("The calculation time is invalid.")

    rows = db.session.execute(
        db.select(Task.assigned_to, db.func.count(Task.id))
        .where(
            Task.status == "pending",
            Task.assigned_to.is_not(None),
            Task.due_date.is_not(None),
            Task.due_date < calculated_at,
        )
        .group_by(Task.assigned_to)
    )
    return [
        {"user_id": user_id, "overdue_tasks": overdue_count}
        for user_id, overdue_count in rows
    ]


def _get_booking(booking_id):
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        raise ValueError("Booking not found.")
    return booking


def get_booking_for_edit(user, booking_id):
    booking = _get_booking(booking_id)
    if booking.created_by != user.id:
        raise PermissionError("Only the booking creator can edit this booking.")
    return booking


def _validate_booking(resource, start_time, end_time):
    if not isinstance(resource, str) or not resource.strip():
        raise ValueError("Resource is required.")
    resource = resource.strip()
    if resource not in VALID_BOOKING_RESOURCES:
        raise ValueError("Choose a valid household resource.")
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        raise ValueError("Booking start and end times are required.")
    if end_time <= start_time:
        raise ValueError("Booking end time must be after its start time.")
    return resource


def _has_booking_conflict(resource, start_time, end_time, exclude_booking_id=None):
    query = db.select(Booking.id).where(
        Booking.resource == resource,
        Booking.start_time < end_time,
        Booking.end_time > start_time,
    )
    if exclude_booking_id is not None:
        query = query.where(Booking.id != exclude_booking_id)
    return db.session.scalar(query) is not None


def create_booking(user, resource, start_time, end_time):
    resource = _validate_booking(resource, start_time, end_time)
    if _has_booking_conflict(resource, start_time, end_time):
        raise ValueError("This resource is already booked during that time.")

    booking = Booking(
        resource=resource,
        start_time=start_time,
        end_time=end_time,
        created_by=user.id,
    )
    db.session.add(booking)
    db.session.commit()
    return booking


def update_booking(user, booking_id, resource=None, start_time=None, end_time=None):
    booking = get_booking_for_edit(user, booking_id)

    updated_resource = resource if resource is not None else booking.resource
    updated_start = start_time if start_time is not None else booking.start_time
    updated_end = end_time if end_time is not None else booking.end_time
    updated_resource = _validate_booking(updated_resource, updated_start, updated_end)

    if _has_booking_conflict(
        updated_resource,
        updated_start,
        updated_end,
        exclude_booking_id=booking.id,
    ):
        raise ValueError("This resource is already booked during that time.")

    booking.resource = updated_resource
    booking.start_time = updated_start
    booking.end_time = updated_end
    db.session.commit()
    return booking


def delete_booking(user, booking_id):
    booking = _get_booking(booking_id)
    if booking.created_by != user.id:
        raise PermissionError("Only the booking creator can delete this booking.")

    db.session.delete(booking)
    db.session.commit()


def list_bookings(user):
    return Booking.query.order_by(Booking.start_time.asc(), Booking.id.asc()).all()


def get_booking_contributions(period_start, period_end):
    if period_start is None or period_end is None or period_start > period_end:
        raise ValueError("The contribution period is invalid.")

    rows = db.session.execute(
        db.select(Booking.created_by)
        .where(
            Booking.start_time >= period_start,
            Booking.start_time <= period_end,
        )
        .order_by(Booking.start_time.asc())
    )
    return [{"user_id": user_id} for (user_id,) in rows]