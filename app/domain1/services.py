from datetime import datetime

from app import db
from app.models import Task


VALID_DIFFICULTIES = {"easy", "medium", "hard"}


def _get_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found.")
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


def update_task(user, task_id, title=None, description=None, difficulty=None, due_date=None):
    task = _get_task(task_id)
    if task.created_by != user.id:
        raise PermissionError("Only the task creator can edit this task.")

    if title is not None:
        task.title = _validate_title(title)
    if difficulty is not None:
        _validate_difficulty(difficulty)
        task.difficulty = difficulty

    task.description = description
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