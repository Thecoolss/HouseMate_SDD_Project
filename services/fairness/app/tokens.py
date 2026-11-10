"""Verifies the bearer tokens issued by the household service.

The token is signed with AUTH_SECRET, which both services share, so fairness checks it
locally without calling household. That keeps the fairness page working while household
is down. Fairness never issues tokens.
"""

from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, URLSafeTimedSerializer

# Must match the salt household signs with.
_SALT = "housemate-auth"


def require_auth(view):
    """Reject the request with 401 unless it carries a valid, unexpired bearer token.

    On success g.user_id and g.username come from the token, and g.token is the raw token,
    which the seam forwards to household.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme != "Bearer" or not token:
            return jsonify(error="Authentication required."), 401
        serializer = URLSafeTimedSerializer(current_app.config["AUTH_SECRET"], salt=_SALT)
        try:
            claims = serializer.loads(token, max_age=current_app.config["TOKEN_MAX_AGE_S"])
        except BadSignature:  # also covers SignatureExpired
            return jsonify(error="Invalid or expired token."), 401

        g.user_id = claims["user_id"]
        g.username = claims["username"]
        g.token = token
        return view(*args, **kwargs)

    return wrapper
