from utils.timezone import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy import and_
from werkzeug.security import generate_password_hash
from extensions import db
from models import User, UserRole, School, Teacher, Student
from . import auth_bp
from .forms import LoginForm, RegistrationForm, PasswordForm, ProfileForm
from zoneinfo import ZoneInfo

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Redirect berdasarkan role
        if current_user.role == UserRole.SUPERADMIN:
            return redirect(url_for('superadmin.dashboard'))
        elif current_user.role == UserRole.ADMIN:
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == UserRole.TEACHER:
            return redirect(url_for('teacher.dashboard'))
        elif current_user.role == UserRole.STUDENT:
            return redirect(url_for('student.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data) and user.is_active:
            # Cek status sekolah untuk user non-superadmin
            if user.role != UserRole.SUPERADMIN:
                if not user.school.is_active:
                    flash('Sekolah tempat Anda terdaftar sedang dinonaktifkan.', 'danger')
                    return render_template('auth/login.html', form=form)
                # opsional: cek langganan
                if user.school.subscription and not user.school.subscription.is_valid():
                    flash('Langganan sekolah Anda telah kedaluwarsa. Silakan hubungi administrator.', 'danger')
                    return render_template('auth/login.html', form=form)
            
            login_user(user)
            user.last_login = db.func.now()
            db.session.commit()
            
            flash('Login berhasil!', 'success')
            
            # Redirect berdasarkan role
            if user.role == UserRole.SUPERADMIN:
                return redirect(url_for('superadmin.dashboard'))
            elif user.role == UserRole.ADMIN:
                return redirect(url_for('admin.dashboard'))
            elif user.role == UserRole.TEACHER:
                return redirect(url_for('teacher.dashboard'))
            elif user.role == UserRole.STUDENT:
                return redirect(url_for('student.dashboard'))
        else:
            flash('Login gagal. Periksa username dan password Anda.', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    profile_form = ProfileForm(obj=current_user)
    password_form = PasswordForm()

    if profile_form.validate_on_submit() and 'update_profile' in request.form:
        existing_user = User.query.filter(and_(User.email == profile_form.email.data, User.id != current_user.id)).first()
        if existing_user:
            flash('Email sudah digunakan. Silahkan gunakan email lain.', 'danger')
            return redirect(url_for('auth.profile'))
        current_user.username = profile_form.username.data
        current_user.email = profile_form.email.data
        db.session.commit()
        flash('Profil berhasil diperbarui!', 'success')
        return redirect(url_for('auth.profile'))

    if password_form.validate_on_submit() and 'change_password' in request.form:
        if not current_user.check_password(password_form.current_password.data):
            flash('Password lama salah!', 'danger')
        elif password_form.new_password.data != password_form.confirm_password.data:
            flash('Konfirmasi password tidak cocok!', 'danger')
        else:
            current_user.set_password(password_form.new_password.data)
            db.session.commit()
            flash('Password berhasil diubah!', 'success')
        return redirect(url_for('auth.profile'))

    return render_template(
        'auth/profile.html',
        profile_form=profile_form,
        password_form=password_form,
        school=current_user.school if hasattr(current_user, 'school') else None,
        now=datetime.now()
    )