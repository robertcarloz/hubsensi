# app.py
import os
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, logout_user
from config import Config
from extensions import db, login_manager, migrate, csrf
from models import User, UserRole, jakarta_now
from blueprints import init_app as init_blueprints

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    # Initialize blueprints
    init_blueprints(app)
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Login manager settings
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login untuk mengakses halaman ini.'
    login_manager.login_message_category = 'info'

        # Error handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()  # Rollback session jika terjadi error database
        return render_template('errors/500.html', error=error if app.config['DEBUG'] else None), 500

    @app.errorhandler(503)
    def service_unavailable_error(error):
        return render_template('errors/503.html'), 503
    
    # Context processor to make school data available in all templates
    @app.context_processor
    def inject_school_data():
        school_data = {}
        if hasattr(request, 'school_id') and request.school_id:
            from models import School
            school = School.query.get(request.school_id)
            if school:
                school_data = {
                    'school': school,
                    'brand_name': school.brand_name or school.name,
                    'primary_color': school.primary_color or '#0d6efd',
                    'secondary_color': school.secondary_color or '#6c757d',
                    'logo_url': school.logo_url
                }
        return school_data
    
    @app.context_processor
    def inject_now():
        return {'now': jakarta_now()} 
    @app.before_request
    def check_subscription():
        # Skip untuk superadmin dan routes tertentu
        if (current_user.is_anonymous or 
            current_user.role == UserRole.SUPERADMIN or
            request.endpoint in ['auth.logout', 'auth.login', 'static']):
            return
        
        # Periksa status langganan sekolah
        if (current_user.school_id and 
            hasattr(current_user, 'school') and 
            current_user.school.subscription):
            
            subscription = current_user.school.subscription
            if not subscription.is_valid():
                flash('Langganan sekolah Anda telah kedaluwarsa. Silakan hubungi administrator.', 'warning')
                
                # Logout user jika langganan tidak valid
                if request.endpoint not in ['auth.logout', 'auth.login']:
                    logout_user()
                    return redirect(url_for('auth.login'))
            
    # Middleware to set school_id based on current user
    @app.before_request
    def set_school_id():
        from flask_login import current_user
        if current_user.is_authenticated and current_user.school_id:
            request.school_id = current_user.school_id
        else:
            request.school_id = None
    
    @app.before_request
    def check_registration_access():
        # Blok akses ke register jika tidak diizinkan
        if request.endpoint == 'auth.register' and os.environ.get('ALLOW_PUBLIC_REGISTRATION', 'false').lower() != 'true':
            abort(404)
    # Main route
    @app.route('/')
    def index():
        from flask_login import current_user
        
        # Redirect authenticated users to their respective dashboards
        if current_user.is_authenticated:
            if current_user.role == UserRole.SUPERADMIN:
                return redirect(url_for('superadmin.dashboard'))
            elif current_user.role == UserRole.ADMIN:
                return redirect(url_for('admin.dashboard'))
            elif current_user.role == UserRole.TEACHER:
                return redirect(url_for('teacher.dashboard'))
            elif current_user.role == UserRole.STUDENT:
                return redirect(url_for('student.dashboard'))
        
        return render_template('index.html')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    # Health check endpoint for deployment
    @app.route('/health')
    def health_check():
        return jsonify({'status': 'healthy'}), 200
    
    return app

# Create app instance
app = create_app()
with app.app_context():
    print("=== ROUTES TERDAFTAR ===")
    for rule in app.url_map.iter_rules():
        print(rule.endpoint, rule.rule)
    print("========================")
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(
    host="0.0.0.0",
    port=port,
    debug=app.config.get('DEBUG', False),
    threaded = True
)