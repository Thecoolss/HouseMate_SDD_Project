"""Bearer tokens: household issues them at login, both services verify them.

A token is the signed payload {"user_id", "username"}. Anyone holding AUTH_SECRET can
check the signature and age without a database lookup, which is what lets the fairness
service authenticate requests while the household service is down.
"""

from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app import db
from app.models import User

_SALT = "housemate-auth"


def _serializer():
    return URLSafeTimedSerializer(current_app.config["AUTH_SECRET"], salt=_SALT)


def issue_token(user):
    return _serializer().dumps({"user_id": user.id, "username": user.username})


def require_auth(view):
    """Reject the request with 401 unless it carries a valid, unexpired bearer token.

    On success g.user is the User the token was issued to and g.token is the raw token.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme != "Bearer" or not token:
            return jsonify(error="Authentication required."), 401
        try:
            claims = _serializer().loads(token, max_age=current_app.config["TOKEN_MAX_AGE_S"])
        except BadSignature:  # also covers SignatureExpired
            return jsonify(error="Invalid or expired token."), 401

        user = db.session.get(User, claims["user_id"])
        if user is None:
            return jsonify(error="Invalid or expired token."), 401

        g.user = user
        g.token = token
        return view(*args, **kwargs)

    return wrapper
