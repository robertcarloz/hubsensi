from .auth import auth_bp
from .superadmin import superadmin_bp
from .admin import admin_bp
from .teacher import teacher_bp
from .student import student_bp

# Register all blueprints
def init_app(app):
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(superadmin_bp, url_prefix='/superadmin')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    app.register_blueprint(student_bp, url_prefix='/student')