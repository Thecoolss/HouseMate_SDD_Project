from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.auth import bp
from app.models import User


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect("/tasks")

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username:
            flash("Username is required.", "error")
            return render_template("auth/register.html")

        # The form's "required" attribute only stops browsers; a direct POST can still send an
        # empty password, so the server must reject it too.
        if not password:
            flash("Password is required.", "error")
            return render_template("auth/register.html")

        if User.query.filter_by(username=username).first():
            flash("That username is already taken.", "error")
            return render_template("auth/register.html")

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        session.permanent = True
        return redirect("/tasks")

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect("/tasks")

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            session.permanent = True
            return redirect("/tasks")

        flash("Invalid username or password.", "error")

    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
