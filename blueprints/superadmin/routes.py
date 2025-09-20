from random import random
import string
from flask import jsonify, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.security import generate_password_hash
from blueprints import admin
from extensions import db
from models import User, UserRole, School, Teacher, Student
from utils.sendgrid_helper import send_email
from . import superadmin_bp
from .forms import AdminRegistrationForm, SchoolForm
from ..auth.forms import RegistrationForm

def require_superadmin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.SUPERADMIN:
            flash('Akses ditolak. Hanya untuk Superadmin.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@superadmin_bp.route('/dashboard')
@require_superadmin
def dashboard():
    schools = School.query.order_by(School.created_at.desc()).all()
    admin_count = User.query.filter(User.role == UserRole.ADMIN).count()
    
    # Hitung sekolah per bulan
    month_labels = ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des']
    month_counts = [0]*12
    for school in schools:
        month_index = school.created_at.month - 1
        month_counts[month_index] += 1
    
    return render_template(
        'superadmin/dashboard.html',
        schools=schools,
        admin_count=admin_count,
        month_labels=month_labels,
        month_counts=month_counts
    )

@superadmin_bp.route('/schools')
@require_superadmin
def schools():
    schools = School.query.all()
    return render_template(
    'superadmin/schools.html',
    schools=schools,
    UserRole=UserRole
)

@superadmin_bp.route('/schools/add', methods=['GET', 'POST'])
@login_required
@require_superadmin
def add_school():
    # Pastikan hanya superadmin yang bisa mengakses
    if current_user.role != UserRole.SUPERADMIN:
        flash('Akses ditolak. Hanya Superadmin yang dapat menambahkan sekolah.', 'danger')
        return redirect(url_for('superadmin.dashboard'))
    
    form = SchoolForm()
    admin_form = AdminRegistrationForm()  # Form khusus untuk admin sekolah
    if form.validate_on_submit() and admin_form.validate():
        # Cek apakah kode sekolah sudah ada
        existing_school = School.query.filter_by(code=form.code.data).first()
        if existing_school:
            flash('Kode sekolah sudah digunakan. Silakan gunakan kode yang lain.', 'danger')
            return render_template('superadmin/add_school.html', form=form, admin_form=admin_form)
        
        existing_school_name = School.query.filter_by(name=form.name.data).first()
        if existing_school_name:
            flash('Nama sekolah sudah digunakan. Silakan gunakan nama yang lain.', 'danger')
            return render_template('superadmin/add_school.html', form=form, admin_form=admin_form)
        
        # Cek apakah username admin sudah ada
        existing_admin = User.query.filter_by(username=admin_form.username.data).first()
        if existing_admin:
            flash('Username admin sudah digunakan. Silakan gunakan username yang lain.', 'danger')
            return render_template('superadmin/add_school.html', form=form, admin_form=admin_form)
        
        existing_email = User.query.filter_by(email=admin_form.email.data).first()
        if existing_email:
            flash('Email sudah digunakan. Silahkan gunakan email lain.', 'danger')
            return render_template('superadmin/add_school.html', form=form, admin_form=admin_form)
        
        # Buat sekolah baru
        school = School(
            name=form.name.data,
            code=form.code.data,
            address=form.address.data,
            phone=form.phone.data,
            email=form.email.data,
            website=form.website.data,
            is_active=True  # Sekolah aktif secara default
        )
        db.session.add(school)
        db.session.flush()  # Mendapatkan ID sekolah tanpa commit
        
        # Buat admin user untuk sekolah
        admin_user = User(
            school_id=school.id,
            username=admin_form.username.data,
            email=admin_form.email.data,
            role=UserRole.ADMIN
        )
        admin_user.set_password(admin_form.password.data)
        db.session.add(admin_user)
        
        db.session.commit()
        
        flash('Sekolah dan admin berhasil ditambahkan!', 'success')
        return redirect(url_for('superadmin.schools'))
    
    return render_template('superadmin/add_school.html', form=form, admin_form=admin_form)

@superadmin_bp.route('/schools/<int:school_id>/edit', methods=['GET', 'POST'])
@require_superadmin
def edit_school(school_id):
    school = School.query.get_or_404(school_id)
    form = SchoolForm(obj=school)
    admin_form = AdminRegistrationForm()  # Form untuk tambah admin
    admins = User.query.filter_by(school_id=school.id, role=UserRole.ADMIN).all()  # Semua admin sekolah

    if form.validate_on_submit():
        form.populate_obj(school)
        db.session.commit()
        
        flash('Data sekolah berhasil diperbarui!', 'success')
        return redirect(url_for('superadmin.schools'))

    return render_template('superadmin/edit_school.html',
                       form=form,
                       school=school,
                       admin_form=admin_form,
                       UserRole=UserRole)

@superadmin_bp.route('/schools/<int:school_id>/delete', methods=['POST'])
@require_superadmin
def delete_school(school_id):
    school = School.query.get_or_404(school_id)
    
    # Delete all related data (users, teachers, students, etc.)
    User.query.filter_by(school_id=school_id).delete()
    
    db.session.delete(school)
    db.session.commit()
    
    flash('Sekolah berhasil dihapus!', 'success')
    return redirect(url_for('superadmin.schools'))

@superadmin_bp.route('/schools/<int:school_id>/add-admin', methods=['POST'])
@require_superadmin
def add_admin(school_id):
    school = School.query.get_or_404(school_id)
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    if not username or not email or not password:
        return {"success": False, "message": "Semua field wajib diisi"}, 400

    if password != confirm_password:
        return {"success": False, "message": "Password tidak sama"}, 400

    # Cek username / email unik
    if User.query.filter_by(username=username).first():
        return {"success": False, "message": "Username sudah dipakai"}, 400
    if User.query.filter_by(email=email).first():
        return {"success": False, "message": "Email sudah dipakai"}, 400

    # Buat admin baru
    new_admin = User(
        school_id=school.id,
        username=username,
        email=email,
        role=UserRole.ADMIN,
        is_active=True
    )
    new_admin.set_password(password)

    db.session.add(new_admin)
    db.session.commit()

    return {"success": True, "message": "Admin berhasil ditambahkan"}

@superadmin_bp.route('/schools/<int:school_id>/toggle-status', methods=['POST'])
@require_superadmin
def toggle_school_status(school_id):
    school = School.query.get_or_404(school_id)
    data = request.get_json()
    
    if 'is_active' not in data:
        return {"success": False, "message": "Data status tidak ada"}, 400

    school.is_active = bool(data['is_active'])
    db.session.commit()

    status_text = "aktif" if school.is_active else "nonaktif"
    return {"success": True, "message": f"Sekolah berhasil {status_text}kan"}

@superadmin_bp.route('/admins/<int:admin_id>/reset-password', methods=['POST'])
@require_superadmin
def reset_password(admin_id):
    admin = User.query.get_or_404(admin_id)
    if admin.role != UserRole.ADMIN:
        flash("User bukan admin, tidak bisa reset password.", "danger")
        return redirect(url_for('superadmin.edit_school', school_id=admin.school_id))

    # Generate password random
    import random, string
    new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    # Update password (hash)
    admin.set_password(new_password)
    db.session.commit()

    # Kirim email via SendGrid
    subject = "Reset Password Akun Admin"
    body = f"""
Halo {admin.username},

Password akun Anda telah direset oleh Superadmin.
Berikut login terbaru Anda:

Username: {admin.username}
Password: {new_password}

Silakan login dan segera ubah password Anda.
"""

    try:
        response = send_email(to_email=admin.email, subject=subject, body=body)
        flash(f"Password berhasil direset dan dikirim ke email admin (status {response['status_code']}).", "success")
    except Exception as e:
        flash(f"Gagal mengirim email: {str(e)}", "danger")

    return redirect(url_for('superadmin.edit_school', school_id=admin.school_id))
