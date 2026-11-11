from flask import jsonify

from app import db
from app.api_utils import json_body
from app.auth import bp
from app.models import User
from app.tokens import issue_token


def _auth_response(user, status):
    return (
        jsonify(token=issue_token(user), user={"id": user.id, "username": user.username}),
        status,
    )


@bp.post("/register")
def register():
    body = json_body()
    username = body.get("username")
    password = body.get("password")
    username = username.strip() if isinstance(username, str) else ""

    if not username:
        return jsonify(error="Username is required."), 400
    if not isinstance(password, str) or not password:
        return jsonify(error="Password is required."), 400
    if User.query.filter_by(username=username).first():
        return jsonify(error="That username is already taken."), 409

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return _auth_response(user, 201)


@bp.post("/login")
def login():
    body = json_body()
    username = body.get("username")
    password = body.get("password")
    username = username.strip() if isinstance(username, str) else ""

    user = User.query.filter_by(username=username).first()
    if user is None or not isinstance(password, str) or not user.check_password(password):
        return jsonify(error="Invalid username or password."), 401
    return _auth_response(user, 200)
