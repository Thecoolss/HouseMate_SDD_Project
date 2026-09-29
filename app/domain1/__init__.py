from flask import Blueprint

bp = Blueprint("domain1", __name__)

from app.domain1 import routes
