from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.domain1 import bp
from app.domain1 import services
from app.models import User
from app.time_utils import local_to_utc_naive


def _parse_due_date(value):
    if not value:
        return None
    try:
        local_time = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Enter a valid due date and time.") from None
    return local_to_utc_naive(local_time)


def _handle_task_error(error):
    if str(error) == "Task not found.":
        abort(404)
    flash(str(error), "error")
    return redirect(url_for("domain1.list_tasks"))


@bp.get("/tasks")
@login_required
def list_tasks():
    tasks = services.list_tasks(current_user)
    user_ids = {task.created_by for task in tasks}
    user_ids.update(task.assigned_to for task in tasks if task.assigned_to is not None)
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    usernames = {user.id: user.username for user in users}
    return render_template("tasks/list.html", tasks=tasks, usernames=usernames)


@bp.get("/tasks/new")
@login_required
def new_task():
    return render_template("tasks/form.html", task=None, form_data={})


@bp.post("/tasks")
@login_required
def create_task():
    form_data = request.form
    try:
        services.create_task(
            current_user,
            title=form_data.get("title"),
            description=form_data.get("description") or None,
            difficulty=form_data.get("difficulty"),
            due_date=_parse_due_date(form_data.get("due_date")),
        )
    except ValueError as error:
        flash(str(error), "error")
        return render_template("tasks/form.html", task=None, form_data=form_data), 400

    flash("Task created.", "success")
    return redirect(url_for("domain1.list_tasks"))


@bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    if request.method == "GET":
        try:
            task = services.get_task_for_edit(current_user, task_id)
        except PermissionError:
            abort(403)
        except ValueError:
            abort(404)
        return render_template("tasks/form.html", task=task, form_data={})

    form_data = request.form
    try:
        services.update_task(
            current_user,
            task_id,
            title=form_data.get("title"),
            description=form_data.get("description") or None,
            difficulty=form_data.get("difficulty"),
            due_date=_parse_due_date(form_data.get("due_date")),
        )
    except PermissionError:
        abort(403)
    except ValueError as error:
        if str(error) == "Task not found.":
            abort(404)
        flash(str(error), "error")
        try:
            task = services.get_task_for_edit(current_user, task_id)
        except PermissionError:
            abort(403)
        except ValueError:
            abort(404)
        return render_template("tasks/form.html", task=task, form_data=form_data), 400

    flash("Task updated.", "success")
    return redirect(url_for("domain1.list_tasks"))


@bp.post("/tasks/<int:task_id>/claim")
@login_required
def claim_task(task_id):
    try:
        services.claim_task(current_user, task_id)
    except ValueError as error:
        return _handle_task_error(error)
    flash("Task claimed.", "success")
    return redirect(url_for("domain1.list_tasks"))


@bp.post("/tasks/<int:task_id>/complete")
@login_required
def complete_task(task_id):
    try:
        services.mark_complete(current_user, task_id)
    except PermissionError:
        abort(403)
    except ValueError as error:
        return _handle_task_error(error)
    flash("Task completed.", "success")
    return redirect(url_for("domain1.list_tasks"))


@bp.post("/tasks/<int:task_id>/delete")
@login_required
def remove_task(task_id):
    try:
        services.delete_task(current_user, task_id)
    except PermissionError:
        abort(403)
    except ValueError as error:
        return _handle_task_error(error)
    flash("Task deleted.", "success")
    return redirect(url_for("domain1.list_tasks"))


def _parse_booking_datetime(value):
    if not value:
        return None
    try:
        local_time = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Enter a valid booking date and time.") from None
    return local_to_utc_naive(local_time)


def _handle_booking_error(error):
    if str(error) == "Booking not found.":
        abort(404)
    flash(str(error), "error")
    return redirect(url_for("domain1.list_bookings"))


@bp.get("/bookings")
@login_required
def list_bookings():
    bookings = services.list_bookings(current_user)
    user_ids = {booking.created_by for booking in bookings}
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    usernames = {user.id: user.username for user in users}
    return render_template("bookings/list.html", bookings=bookings, usernames=usernames)


@bp.get("/bookings/new")
@login_required
def new_booking():
    return render_template("bookings/form.html", booking=None, form_data={})


@bp.post("/bookings")
@login_required
def create_booking():
    form_data = request.form
    try:
        services.create_booking(
            current_user,
            resource=form_data.get("resource"),
            start_time=_parse_booking_datetime(form_data.get("start_time")),
            end_time=_parse_booking_datetime(form_data.get("end_time")),
        )
    except ValueError as error:
        flash(str(error), "error")
        return render_template("bookings/form.html", booking=None, form_data=form_data), 400

    flash("Booking created.", "success")
    return redirect(url_for("domain1.list_bookings"))


@bp.route("/bookings/<int:booking_id>/edit", methods=["GET", "POST"])
@login_required
def edit_booking(booking_id):
    if request.method == "GET":
        try:
            booking = services.get_booking_for_edit(current_user, booking_id)
        except PermissionError:
            abort(403)
        except ValueError:
            abort(404)
        return render_template("bookings/form.html", booking=booking, form_data={})

    form_data = request.form
    try:
        services.update_booking(
            current_user,
            booking_id,
            resource=form_data.get("resource"),
            start_time=_parse_booking_datetime(form_data.get("start_time")),
            end_time=_parse_booking_datetime(form_data.get("end_time")),
        )
    except PermissionError:
        abort(403)
    except ValueError as error:
        if str(error) == "Booking not found.":
            abort(404)
        flash(str(error), "error")
        try:
            booking = services.get_booking_for_edit(current_user, booking_id)
        except PermissionError:
            abort(403)
        except ValueError:
            abort(404)
        return render_template("bookings/form.html", booking=booking, form_data=form_data), 400

    flash("Booking updated.", "success")
    return redirect(url_for("domain1.list_bookings"))


@bp.post("/bookings/<int:booking_id>/delete")
@login_required
def remove_booking(booking_id):
    try:
        services.delete_booking(current_user, booking_id)
    except PermissionError:
        abort(403)
    except ValueError as error:
        return _handle_booking_error(error)
    flash("Booking deleted.", "success")
    return redirect(url_for("domain1.list_bookings"))