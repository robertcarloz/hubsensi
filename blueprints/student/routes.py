from flask import render_template, redirect, request, url_for, flash, send_file
from flask_login import login_required, current_user
from utils.timezone import datetime
from datetime import timedelta
from extensions import db
from models import User, UserRole, Student, Attendance
from . import student_bp
import os

@student_bp.before_request
@login_required
def require_student():
    if current_user.role != UserRole.STUDENT:
        flash('Akses ditolak. Hanya untuk Siswa.', 'danger')
        return redirect(url_for('auth.login'))

@student_bp.route('/dashboard')
def dashboard():
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    if not student:
        flash('Data siswa tidak ditemukan.', 'danger')
        return redirect(url_for('auth.logout'))
    
    # Get attendance summary
    today = datetime.now().date()
    start_date = today - timedelta(days=30)  # Last 30 days
    
    attendance_records = Attendance.query.filter(
        Attendance.student_id == student.id,
        Attendance.date >= start_date,
        Attendance.date <= today
    ).order_by(Attendance.date.desc()).all()
    
    # Count attendance status
    status_count = {
        'hadir': 0,
        'izin': 0,
        'sakit': 0,
        'alpha': 0
    }
    
    for record in attendance_records:
        status_count[record.status.value] += 1
    
    return render_template('student/dashboard.html', 
                         student=student,
                         attendance_records=attendance_records,
                         status_count=status_count)

@student_bp.route('/attendance')
def attendance():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash("Data siswa tidak ditemukan.", "danger")
        return redirect(url_for('auth.logout'))

    # Ambil semua absensi siswa
    attendance_records = Attendance.query.filter_by(student_id=student.id)\
                            .order_by(Attendance.date.desc()).all()

    # Hitung jumlah per status
    status_count = {
        'hadir': 0,
        'izin': 0,
        'sakit': 0,
        'alpha': 0
    }
    for record in attendance_records:
        status_count[record.status.value] += 1

    return render_template(
        'student/attendance.html',
        student=student,
        attendance_records=attendance_records,
        status_count=status_count
    )

@student_bp.route('/qr_code')
def qr_code():
    student = Student.query.filter_by(user_id=current_user.id).first()

    if not student:
        flash("Data siswa tidak ditemukan.", "danger")
        return redirect(url_for('auth.logout'))

    return render_template('student/qr_code.html', student=student)

@student_bp.route('/download_qr')
def download_qr():
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    if not student or not student.qr_code:
        flash('QR code tidak tersedia.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    # Return the QR code image file
    return send_file(student.qr_code, as_attachment=True, 
                    download_name=f"qr_code_{student.nis}.png")