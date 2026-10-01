from flask import Blueprint

bp = Blueprint("domain2", __name__)

from app.domain2 import routes
