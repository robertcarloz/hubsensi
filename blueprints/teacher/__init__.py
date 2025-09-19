from flask import Blueprint

teacher_bp = Blueprint('teacher', __name__, template_folder='templates')

from . import routes