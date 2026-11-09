from flask import Blueprint

bp = Blueprint("internal", __name__)

from app.internal import routes
