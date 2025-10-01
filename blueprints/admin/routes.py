from collections import Counter
import csv
from functools import wraps
import secrets
from flask import Response, current_app, render_template, redirect, url_for, flash, request, jsonify,send_file
from flask_login import login_required, current_user
import qrcode
import os
from io import BytesIO
import base64
from datetime import date, timedelta
from models import EventType, TeacherAttendance, User, UserRole, School, Teacher, Student, Classroom, SchoolEvent, SchoolQRCode, Attendance, jakarta_now
import io
from extensions import db
from . import admin_bp
from .forms import TeacherForm, StudentForm, ClassroomForm, EventForm, SchoolSettingsForm
import pandas as pd
from utils.s3_helper import *
from utils.card_generator import generate_student_card
from flask import send_file
import io

def require_admin(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != UserRole.ADMIN:
            flash('Akses ditolak. Hanya untuk Admin Sekolah.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@require_admin
def dashboard():
    teacher_count = Teacher.query.filter_by(school_id=current_user.school_id).count()
    student_count = Student.query.filter_by(school_id=current_user.school_id).count()
    classroom_count = Classroom.query.filter_by(school_id=current_user.school_id).count()
    
    today = jakarta_now().date()
    today_attendance_records = Attendance.query.filter(
        Attendance.school_id == current_user.school_id,
        Attendance.date == today
    ).all()
    
    today_attendance = len(today_attendance_records)
    
    # Hitung statistik status attendance
    status_counts = Counter([a.status.value for a in today_attendance_records])
    attendance_stats = {
        'hadir': status_counts.get('hadir', 0),
        'izin': status_counts.get('izin', 0),
        'sakit': status_counts.get('sakit', 0),
        'alpha': status_counts.get('alpha', 0)
    }
    
    # Get recent activities (mock data for now)
    recent_activities = []

    # 1. Ambil 5 absensi terbaru hari ini
    absensi_terbaru = Attendance.query.filter(
        Attendance.school_id == current_user.school_id
    ).order_by(Attendance.created_at.desc()).limit(5).all()

    for a in absensi_terbaru:
        recent_activities.append({
            'title': f"{a.student.full_name} {a.status.value.capitalize()}",
            'time': a.created_at.strftime('%H:%M %d/%m/%Y'),
            'icon': 'check-circle',
            'color': 'success' if a.status.value == 'hadir' else 'warning'
        })

    # 2. Ambil 3 event terbaru
    events_terbaru = SchoolEvent.query.filter(
        SchoolEvent.school_id == current_user.school_id
    ).order_by(SchoolEvent.created_at.desc()).limit(3).all()

    for e in events_terbaru:
        recent_activities.append({
            'title': f"Event: {e.title}",
            'time': e.created_at.strftime('%H:%M %d/%m/%Y'),
            'icon': 'calendar-event',
            'color': 'info'
        })

    # 3. Bisa juga tambah siswa atau guru baru
    recent_students = Student.query.filter_by(school_id=current_user.school_id).order_by(Student.created_at.desc()).limit(3).all()
    for s in recent_students:
        recent_activities.append({
            'title': f"Siswa baru ditambahkan: {s.full_name}",
            'time': s.created_at.strftime('%H:%M %d/%m/%Y'),
            'icon': 'person-plus',
            'color': 'success'
        })

    # Sort berdasarkan waktu terbaru
    from datetime import datetime
    recent_activities.sort(key=lambda x: datetime.strptime(x['time'], '%H:%M %d/%m/%Y'), reverse=True)
    # Get recent teachers and students
    recent_teachers = Teacher.query.filter_by(school_id=current_user.school_id).order_by(Teacher.created_at.desc()).limit(5).all()
    recent_students = Student.query.filter_by(school_id=current_user.school_id).order_by(Student.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                           teacher_count=teacher_count,
                           student_count=student_count,
                           classroom_count=classroom_count,
                           today_attendance=today_attendance,
                           today=today,
                           attendance_stats=attendance_stats,
                           recent_activities=recent_activities,
                           recent_teachers=recent_teachers,
                           recent_students=recent_students)

@admin_bp.route('/students/<int:student_id>/generate-card')
@require_admin
def generate_card(student_id):

    student = Student.query.get_or_404(student_id)
    if not student.qr_code:
        flash('Siswa ini belum memiliki QR code. Silakan buat terlebih dahulu.', 'warning')
        return redirect(url_for('admin.students'))

    card_image = generate_student_card(student.full_name, student.nis, student.qr_code)

    if card_image is None:
        flash('Gagal mengambil gambar QR code dari S3.', 'danger')
        return redirect(url_for('admin.students'))

    return send_file(
        io.BytesIO(card_image),
        mimetype='image/png',
        as_attachment=True,
        download_name=f'kartu_{student.full_name}.png'
    )

@admin_bp.route('/teachers')
@require_admin
def teachers():
    page = request.args.get('page', 1, type=int)
    teachers = Teacher.query.filter_by(school_id=current_user.school_id).paginate(
        page=page, per_page=10, error_out=False)
    return render_template('admin/teachers.html', teachers=teachers.items, pagination=teachers)

@admin_bp.route('/teachers/add', methods=['GET', 'POST'])
@require_admin
def add_teacher():
    form = TeacherForm()
    
    if form.validate_on_submit():
        # Cek NIP sudah ada di sekolah yang sama
        existing_teacher = Teacher.query.filter_by(
            nip=form.nip.data,
            school_id=current_user.school_id
        ).first()
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_teacher:
            flash(f'NIP {form.nip.data} sudah digunakan oleh {existing_teacher.full_name}!', 'danger')
            return render_template('admin/add_teacher.html', form=form)
        if existing_email:
            flash(f'Email {form.email.data} sudah digunakan!', 'danger')
            return render_template('admin/add_teacher.html', form=form)
        import secrets
        password = secrets.token_urlsafe(8)

        # Create user account
        user = User(
            school_id=current_user.school_id,
            username=f"{form.nip.data}",
            email=form.email.data if form.email.data else f"{form.nip.data}@school{current_user.school_id}.local",
            role=UserRole.TEACHER
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Create teacher
        teacher = Teacher(
            school_id=current_user.school_id,
            user_id=user.id,
            full_name=form.full_name.data,
            nip=form.nip.data,
            is_homeroom=False
        )
        db.session.add(teacher)
        db.session.commit()

        # Kirim email via Gmail API
        try:
            from utils.sendgrid_helper import send_email  # ganti gmail_helper
            body = f"""
        Halo {teacher.full_name},

        Akun guru Anda telah dibuat:
        Username: {user.username}
        Password: {password}

        Silakan login di {url_for('auth.login', _external=True)}
        """
            response = send_email(user.email, "Akun Guru Baru", body)
            
            if 200 <= response['status_code'] < 300:
                flash('Akun guru berhasil dibuat dan email terkirim!', 'success')
            else:
                flash('Akun guru dibuat, tapi gagal kirim email', 'warning')
        except Exception as e:
            flash(f'Akun guru dibuat, tapi gagal kirim email: {str(e)}', 'warning')

            return redirect(url_for('admin.teachers'))
    
    return render_template('admin/add_teacher.html', form=form)

@admin_bp.route('/teachers/<int:teacher_id>/edit', methods=['GET', 'POST'])
@require_admin
def edit_teacher(teacher_id):
    teacher = Teacher.query.filter_by(
        id=teacher_id, 
        school_id=current_user.school_id
    ).first_or_404()
    
    user = teacher.user

    # Prefill form dengan user email dan nip
    form = TeacherForm(
        obj=teacher,
        email=user.email if user else '',
        nip=teacher.nip
    )

    if form.validate_on_submit():
        # Validasi email jika berubah
        if user.email != form.email.data:
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash(f'Email {form.email.data} sudah digunakan!', 'danger')
                return render_template('admin/edit_teacher.html', form=form, teacher=teacher)

        # Update teacher fields
        teacher.full_name = form.full_name.data
        teacher.nip = form.nip.data
        teacher.is_homeroom = teacher.is_homeroom

        # Update user username dan email
        user.username = form.nip.data
        user.email = form.email.data

        db.session.commit()
        
        flash('Data guru berhasil diperbarui!', 'success')
        return redirect(url_for('admin.teachers'))
    
    return render_template('admin/edit_teacher.html', form=form, teacher=teacher)


@admin_bp.route('/teachers/<int:teacher_id>/delete', methods=['POST'])
@require_admin
def delete_teacher(teacher_id):
    teacher = Teacher.query.filter_by(
        id=teacher_id,
        school_id=current_user.school_id
    ).first_or_404()

    # Delete associated user account
    if teacher.user:
        db.session.delete(teacher.user)
    
    db.session.delete(teacher)
    db.session.commit()
    flash('Data guru berhasil dihapus!', 'success')
    return redirect(url_for('admin.teachers'))

@admin_bp.route('/students')
@require_admin
def students():
    page = request.args.get('page', 1, type=int)
    students = Student.query.filter_by(school_id=current_user.school_id).paginate(
        page=page, per_page=10, error_out=False)
    classrooms = Classroom.query.filter_by(school_id=current_user.school_id).all()
    return render_template('admin/students.html', students=students.items, pagination=students, classrooms=classrooms)

@admin_bp.route('/students/add', methods=['GET', 'POST'])
@require_admin
def add_student():
    form = StudentForm()

    # Populate classroom choices
    form.classroom_id.choices = [(0, '-- Pilih Kelas --')] + [
        (c.id, c.name) for c in Classroom.query.filter_by(school_id=current_user.school_id).all()
    ]

    if form.validate_on_submit():
        # Validasi NIS
        existing_student = Student.query.filter_by(
            nis=form.nis.data,
            school_id=current_user.school_id
        ).first()
        if existing_student:
            flash(f'NIS {form.nis.data} sudah digunakan!', 'danger')
            return render_template('admin/add_student.html', form=form)

        # Tentukan email default
        email = form.email.data.strip()

        # Validasi email
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash(f'Email {email} sudah digunakan!', 'danger')
            return render_template('admin/add_student.html', form=form)
        elif (email is None):
            flash (f"Email wajib di isi untuk mengirim username dan password siswa")

        # Generate password
        password = secrets.token_urlsafe(8)

        # Buat akun user siswa
        user = User(
            school_id=current_user.school_id,
            username=f"student_{form.nis.data}",
            email=email,
            role=UserRole.STUDENT
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # supaya dapat user.id

        # Generate QR code
        qr_data = f"STUDENT:{form.nis.data}:{current_user.school_id}"
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # Upload QR ke S3
        qr_filename = f"student_{form.nis.data}.png"
        qr_url = upload_file_to_s3(img_bytes, folder='qr_codes', filename=qr_filename)

        # Tambah data student
        student = Student(
            school_id=current_user.school_id,
            user_id=user.id,
            nis=form.nis.data,
            nisn=form.nisn.data,
            full_name=form.full_name.data,
            classroom_id=form.classroom_id.data if form.classroom_id.data != 0 else None,
            qr_code=qr_url
        )
        db.session.add(student)
        db.session.commit()

        # Kirim email via Gmail API
        try:
            from utils.sendgrid_helper import send_email
            body = f"""
Halo {student.full_name},

Akun siswa Anda telah dibuat:
Username: {user.username}
Password: {password}

Silakan login di {url_for('auth.login', _external=True)}
"""
            send_email(user.email, "Akun Siswa Baru", body)
        except Exception as e:
            flash(f'Akun siswa dibuat, tapi gagal kirim email: {str(e)}', 'warning')
        else:
            flash('Akun siswa berhasil dibuat dan email terkirim!', 'success')

        return redirect(url_for('admin.students'))

    return render_template('admin/add_student.html', form=form)

@admin_bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@require_admin
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    form = StudentForm(obj=student)
    form.email.data = student.user.email if student.user else ''

    # Populate classroom choices
    form.classroom_id.choices = [(0, '-- Pilih Kelas --')] + [
        (c.id, c.name) for c in Classroom.query.filter_by(school_id=current_user.school_id).all()
    ]

    if form.validate_on_submit():
        # Validasi NIS
        if student.nis != form.nis.data:
            existing_student = Student.query.filter_by(
                nis=form.nis.data,
                school_id=current_user.school_id
            ).first()
            if existing_student:
                flash(f'NIS {form.nis.data} sudah digunakan!', 'danger')
                return render_template('admin/edit_student.html', form=form, student=student)

        # Validasi email
        email = form.email.data.strip() if form.email.data else f"student_{form.nis.data}@school{current_user.school_id}.local"
        if student.user.email != email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash(f'Email {email} sudah digunakan!', 'danger')
                return render_template('admin/edit_student.html', form=form, student=student)

        student.user.email = email
        student.nis = form.nis.data
        student.nisn = form.nisn.data
        student.full_name = form.full_name.data
        student.classroom_id = form.classroom_id.data if form.classroom_id.data != 0 else None

        # Generate QR baru
        qr_data = f"STUDENT:{student.nis}:{current_user.school_id}"
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # Hapus QR lama di S3 kalau ada
        if student.qr_code:
            delete_file_from_s3(student.qr_code)

        # Upload QR baru
        qr_filename = f"student_{student.nis}.png"
        student.qr_code = upload_file_to_s3(img_bytes, folder='qr_codes', filename=qr_filename)

        db.session.commit()
        flash('Data siswa berhasil diperbarui!', 'success')
        return redirect(url_for('admin.students'))

    return render_template('admin/edit_student.html', form=form, student=student)



@admin_bp.route('/students/<int:student_id>/delete', methods=['POST'])
@require_admin
def delete_student(student_id):

    student = Student.query.filter_by(
        id=student_id,
        school_id=current_user.school_id
    ).first_or_404()

    # Delete QR code from S3 if exists
    if student.qr_code and student.qr_code.startswith("https://"):
        delete_file_from_s3(student.qr_code)

    # Delete associated user account
    if student.user:
        db.session.delete(student.user)
    
    db.session.delete(student)
    db.session.commit()
    flash('Data siswa berhasil dihapus!', 'success')
    return redirect(url_for('admin.students'))


@admin_bp.route('/students/import', methods=['POST'])
@require_admin
def import_students():
    from utils.s3_helper import upload_file_to_s3
    import secrets

    if 'file' not in request.files:
        flash('Tidak ada file yang diupload', 'danger')
        return redirect(url_for('admin.students'))
    
    file = request.files['file']
    classroom_id = request.form.get('classroom_id')
    
    if file.filename == '':
        flash('Tidak ada file yang dipilih', 'danger')
        return redirect(url_for('admin.students'))
    
    try:
        # Baca file
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Validasi kolom
        required_columns = ['nis', 'full_name', 'email']
        if not all(col in df.columns for col in required_columns):
            flash('File harus memiliki kolom: nis, full_name, email', 'danger')
            return redirect(url_for('admin.students'))
        
        success_count = 0
        error_count = 0
        
        for _, row in df.iterrows():
            try:
                nis = str(row['nis']).strip()
                full_name = str(row['full_name']).strip()
                email = str(row['email']).strip() if pd.notna(row['email']) and str(row['email']).strip() else f"student_{nis}@school{current_user.school_id}.local"
                nisn = str(row['nisn']).strip() if 'nisn' in df.columns and pd.notna(row['nisn']) else None

                # Cek NIS unik
                existing_student = Student.query.filter_by(nis=nis, school_id=current_user.school_id).first()
                if existing_student:
                    error_count += 1
                    continue
                
                # Cek email unik
                existing_user = User.query.filter_by(email=email).first()
                if existing_user:
                    error_count += 1
                    continue

                # Buat password acak
                password = secrets.token_urlsafe(8)

                # Buat akun user
                user = User(
                    school_id=current_user.school_id,
                    username=f"student_{nis}",
                    email=email,
                    role=UserRole.STUDENT
                )
                user.set_password(password)
                db.session.add(user)
                db.session.flush()  # agar user.id tersedia

                # Generate QR code
                qr = qrcode.QRCode(
                    version=1, 
                    error_correction=qrcode.constants.ERROR_CORRECT_L, 
                    box_size=10, 
                    border=4
                )
                qr_data = f"STUDENT:{nis}:{current_user.school_id}"
                qr.add_data(qr_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")

                # Simpan QR ke BytesIO
                qr_bytes = BytesIO()
                img.save(qr_bytes, format='PNG')
                qr_bytes.seek(0)

                # Upload ke S3
                qr_filename = f"student_{nis}.png"
                qr_s3_url = upload_file_to_s3(qr_bytes, folder='qr_codes', filename=qr_filename)

                # Buat record student
                student = Student(
                    school_id=current_user.school_id,
                    user_id=user.id,
                    nis=nis,
                    nisn=nisn,
                    full_name=full_name,
                    classroom_id=classroom_id if classroom_id else None,
                    qr_code=qr_s3_url
                )
                db.session.add(student)

                # Kirim email
                try:
                    from utils.sendgrid_helper import send_email
                    body = f"""
Halo {student.full_name},

Akun siswa Anda telah dibuat:
Username: {user.username}
Password: {password}

Silakan login di {url_for('auth.login', _external=True)}
"""
                    send_email(user.email, "Akun Siswa Baru", body)
                except Exception as e:
                    # Gagal kirim email, tapi tetap hitung siswa berhasil
                    flash(f'Akun {full_name} dibuat, tapi gagal kirim email: {str(e)}', 'warning')

                success_count += 1

            except Exception as e:
                error_count += 1
                continue
        
        db.session.commit()
        flash(f'Import selesai: {success_count} siswa berhasil, {error_count} gagal', 'success')

    except Exception as e:
        flash(f'Error memproses file: {str(e)}', 'danger')
    
    return redirect(url_for('admin.students'))


@admin_bp.route('/students/<int:student_id>')
@require_admin
def view_student(student_id):
    student = Student.query.filter_by(
        id=student_id, 
        school_id=current_user.school_id
    ).first_or_404()
    
    # Get attendance records
    attendance_records = Attendance.query.filter_by(
        student_id=student_id
    ).order_by(Attendance.date.desc()).limit(50).all()
    
    # Calculate attendance stats
    total_attendance = len(attendance_records)
    attendance_stats = {
        'hadir': len([a for a in attendance_records if a.status.value == 'hadir']),
        'izin': len([a for a in attendance_records if a.status.value == 'izin']),
        'sakit': len([a for a in attendance_records if a.status.value == 'sakit']),
        'alpha': len([a for a in attendance_records if a.status.value == 'alpha'])
    }
    
    return render_template('admin/view_student.html', 
                         student=student,
                         attendance_records=attendance_records,
                         attendance_stats=attendance_stats,
                         total_attendance=total_attendance)

@admin_bp.route('/download_template')
@require_admin
def download_template():
    import pandas as pd
    from io import BytesIO
    from flask import send_file
    data = {
        'nis': ['S001', 'S002', 'S003'],
        'nisn': ['NISN001', 'NISN002', 'NISN003'],
        'full_name': ['Nama Siswa 1', 'Nama Siswa 2', 'Nama Siswa 3'],
        'email': ['siswa1@example.com', 'siswa2@example.com', 'siswa3@example.com']
    }
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Siswa', index=False)
    
    output.seek(0)

    return send_file(
        output,
        download_name='student_import_template.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@admin_bp.route('/classrooms')
@require_admin
def classrooms():
    classrooms = Classroom.query.filter_by(school_id=current_user.school_id).all()
    teachers = Teacher.query.filter_by(school_id=current_user.school_id).all()
    return render_template('admin/classrooms.html', classrooms=classrooms, teachers=teachers)

@admin_bp.route('/classrooms/<int:classroom_id>/data')
@require_admin
def get_classroom_data(classroom_id):
    classroom = Classroom.query.filter_by(
        id=classroom_id,
        school_id=current_user.school_id
    ).first_or_404()
    
    return jsonify({
        'id': classroom.id,
        'name': classroom.name,
        'grade_level': classroom.grade_level,
        'homeroom_teacher_id': classroom.homeroom_teacher_id
    })

@admin_bp.route('/classrooms/add', methods=['GET', 'POST'])
@require_admin
def add_classroom():
    form = ClassroomForm()
    
    # Populate teacher choices
    form.homeroom_teacher_id.choices = [(0, '-- Pilih Wali Kelas --')] + [
        (t.id, t.full_name) for t in Teacher.query.filter_by(
            school_id=current_user.school_id, 
            is_homeroom=False
        ).all()
    ]
    
    if form.validate_on_submit():
        classroom = Classroom(
            school_id=current_user.school_id,
            name=form.name.data,
            grade_level=form.grade_level.data,
            homeroom_teacher_id=form.homeroom_teacher_id.data if form.homeroom_teacher_id.data != 0 else None
        )
        db.session.add(classroom)
        db.session.commit()
        
        # Update teacher's homeroom status if selected
        if form.homeroom_teacher_id.data != 0:
            teacher = Teacher.query.get(form.homeroom_teacher_id.data)
            teacher.is_homeroom = True
            db.session.commit()
        
        flash('Data kelas berhasil ditambahkan!', 'success')
        return redirect(url_for('admin.classrooms'))
    
    return render_template('admin/add_classroom.html', form=form)

@admin_bp.route('/classrooms/<int:classroom_id>/edit', methods=['GET', 'POST'])
@require_admin
def edit_classroom(classroom_id):
    classroom = Classroom.query.filter_by(
        id=classroom_id,
        school_id=current_user.school_id
    ).first_or_404()
    
    form = ClassroomForm(obj=classroom)
    
    # Populate teacher choices - include all teachers, not just non-homeroom
    form.homeroom_teacher_id.choices = [(0, '-- Pilih Wali Kelas --')] + [
        (t.id, t.full_name) for t in Teacher.query.filter_by(
            school_id=current_user.school_id
        ).all()
    ]
    
    if form.validate_on_submit():
        # Reset previous homeroom teacher if changed
        if classroom.homeroom_teacher_id and classroom.homeroom_teacher_id != form.homeroom_teacher_id.data:
            old_teacher = Teacher.query.get(classroom.homeroom_teacher_id)
            if old_teacher:
                old_teacher.is_homeroom = False
        
        form.populate_obj(classroom)
        
        # Update new homeroom teacher status
        if form.homeroom_teacher_id.data != 0:
            teacher = Teacher.query.get(form.homeroom_teacher_id.data)
            teacher.is_homeroom = True
        
        db.session.commit()
        
        flash('Data kelas berhasil diperbarui!', 'success')
        return redirect(url_for('admin.classrooms'))
    
    return render_template('admin/edit_classroom.html', form=form, classroom=classroom)

@admin_bp.route('/attendance')
@require_admin
def attendance():
    # Get attendance by date and class
    date_str = request.args.get('date', jakarta_now().strftime('%Y-%m-%d'))
    classroom_id = request.args.get('classroom_id', type=int)
    
    try:
        from datetime import datetime
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        date = jakarta_now().date()
    
    # Get classrooms for filter
    classrooms = Classroom.query.filter_by(school_id=current_user.school_id).all()
    
    # Get student attendance records
    student_query = Attendance.query.filter_by(
        school_id=current_user.school_id,
        date=date
    )
    
    if classroom_id:
        student_query = student_query.filter_by(classroom_id=classroom_id)
    
    attendance_records = student_query.all()
    
    # Get teacher attendance records for the same date
    teacher_attendance = TeacherAttendance.query.filter_by(
        school_id=current_user.school_id,
        date=date
    ).all()
    
    return render_template('admin/attendance.html', 
                         attendance_records=attendance_records,
                         teacher_attendance=teacher_attendance,
                         classrooms=classrooms,
                         selected_date=date.strftime('%Y-%m-%d'),
                         selected_classroom=classroom_id)

@admin_bp.route('/attendance/export')
@require_admin
def attendance_export_form():
    # Get classrooms for filter
    classrooms = Classroom.query.filter_by(school_id=current_user.school_id).all()
    
    current_date = jakarta_now()
    
    return render_template('admin/ekspor_absensi.html',
                         classrooms=classrooms,
                         current_month=current_date.month,
                         current_year=current_date.year)

@admin_bp.route('/attendance/export/data')
@require_admin
def attendance_export():
    # Get parameters
    export_type = request.args.get('export_type', 'student')
    month = request.args.get('month', type=int, default=jakarta_now().month)
    year = request.args.get('year', type=int, default=jakarta_now().year)
    classroom_id = request.args.get('classroom_id', type=int)
    
    # Validate month and year
    if not (1 <= month <= 12):
        month = jakarta_now().month
    if year < 2000 or year > 2100:
        year = jakarta_now().year
    
    # Calculate date range for the month
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    
    if export_type == 'student':
        # Get student attendance records for the month
        query = Attendance.query.filter(
            Attendance.school_id == current_user.school_id,
            Attendance.date >= start_date,
            Attendance.date < end_date
        )
        
        if classroom_id:
            query = query.filter_by(classroom_id=classroom_id)
        
        attendance_records = query.all()
        
        # Prepare data for Excel
        data = []
        for record in attendance_records:
            data.append({
                'Nama Siswa': record.student.full_name,
                'Kelas': record.classroom.name,
                'Tanggal': record.date.strftime('%d/%m/%Y'),
                'Status': record.status.value.title(),
                'Catatan': record.notes or '',
                'Dicatat Oleh': record.teacher.full_name if record.teacher else ''
            })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Absensi Siswa', index=False)
            
            # Auto-adjust columns width
            worksheet = writer.sheets['Absensi Siswa']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        filename = f"absensi_siswa_{month:02d}_{year}.xlsx"
        
    else:
        # Get teacher attendance records for the month
        teacher_attendance = TeacherAttendance.query.filter(
            TeacherAttendance.school_id == current_user.school_id,
            TeacherAttendance.date >= start_date,
            TeacherAttendance.date < end_date
        ).all()
        
        # Prepare data for Excel
        data = []
        for record in teacher_attendance:
            data.append({
                'Nama Guru': record.teacher.full_name,
                'Tanggal': record.date.strftime('%d/%m/%Y'),
                'Jam Masuk': record.time_in.strftime('%H:%M') if record.time_in else '',
                'Status': record.status.value.title()
            })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Absensi Guru', index=False)
            
            # Auto-adjust columns width
            worksheet = writer.sheets['Absensi Guru']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        filename = f"absensi_guru_{month:02d}_{year}.xlsx"
    
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )
    
@admin_bp.route('/events')
@require_admin
def events():
    events = SchoolEvent.query.filter_by(school_id=current_user.school_id).all()
    events_json = [
    {
        "id": event.id,
        "title": event.title,
        "start": event.start_date.isoformat(),
        "end": event.end_date.isoformat(),
        "allDay": True,
        "event_type": event.event_type.value,   # pakai .value karena enum
        "is_holiday": event.is_holiday
    }
    for event in events
]
    form = EventForm()
    return render_template('admin/events.html', events_json=events_json, form=form)

@admin_bp.route('/events/json')
@require_admin
def events_json():
    events = SchoolEvent.query.filter_by(school_id=current_user.school_id).all()
    return jsonify([
        {
            "id": event.id,
            "title": event.title,
            "start": event.start_date.isoformat(),
            "end": event.end_date.isoformat(),
            "allDay": True,
            "event_type": event.event_type.value,
            "is_holiday": event.is_holiday
        } 
        for event in events
    ])

@admin_bp.route('/events/add', methods=['POST'])
@require_admin
def add_event():
    title = request.form.get('title')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    event_type_str = request.form.get('event_type')
    is_holiday = request.form.get('is_holiday') == 'on'

    if title and start_date and end_date:
        # Tambah 1 hari supaya FullCalendar tampil benar
        from datetime import datetime
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)

        event = SchoolEvent(
            school_id=current_user.school_id,
            title=title,
            description='',
            start_date=start_dt,
            end_date=end_dt,
            event_type=EventType(event_type_str.upper()),
            is_holiday=is_holiday
        )
        db.session.add(event)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})


@admin_bp.route('/events/<int:event_id>/edit', methods=['POST'])
@require_admin
def edit_event(event_id):
    event = SchoolEvent.query.filter_by(id=event_id, school_id=current_user.school_id).first_or_404()
    title = request.form.get('title')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    event_type_str = request.form.get('event_type')
    is_holiday = request.form.get('is_holiday') == 'on'

    if title and start_date and end_date:
        from datetime import datetime
        event.title = title
        event.start_date = datetime.fromisoformat(start_date)
        event.end_date = datetime.fromisoformat(end_date)+timedelta(days=1)  # Tambah 1 hari supaya FullCalendar tampil benar
        event_type=EventType(event_type_str.upper())
        event.is_holiday = is_holiday
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})


@admin_bp.route('/events/<int:event_id>/delete', methods=['POST'])
@require_admin
def delete_event(event_id):
    event = SchoolEvent.query.filter_by(id=event_id, school_id=current_user.school_id).first_or_404()
    db.session.delete(event)
    db.session.commit()
    return jsonify({"success": True})

@admin_bp.route('/settings', methods=['GET', 'POST'])
@require_admin
def settings():
    school = School.query.get(current_user.school_id)
    form = SchoolSettingsForm(obj=school)
    
    if form.validate_on_submit():
        form.populate_obj(school)
        db.session.commit()
        
        flash('Pengaturan berhasil diperbarui!', 'success')
        return redirect(url_for('admin.settings'))
    
    return render_template('admin/settings.html', form=form, school=school)

@admin_bp.route('/generate_qr')
@require_admin
def generate_qr():
    # Cek apakah QR code untuk sekolah ini sudah ada
    school_qr = SchoolQRCode.query.filter_by(school_id=current_user.school_id).first()
    
    if not school_qr:
        # Generate QR code baru karena belum ada
        qr = qrcode.QRCode(
            version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4
        )
        qr_data = f"SCHOOL:{current_user.school_id}"
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Simpan ke memory
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        # Upload ke S3
        file_url = upload_file_to_s3(img_io, folder="qr_codes", filename=f"school_{current_user.school_id}.png")
        
        # Simpan URL ke DB
        school_qr = SchoolQRCode(school_id=current_user.school_id, qr_code=file_url)
        db.session.add(school_qr)
        db.session.commit()
    
    # Render langsung ke template
    return render_template('admin/school_qr.html', school_qr=school_qr)

@admin_bp.route('/api/events')
@require_admin
def api_events():
    events = SchoolEvent.query.filter_by(school_id=current_user.school_id).all()
    
    events_data = []
    for event in events:
        events_data.append({
            'title': event.title,
            'start': event.start_date.isoformat(),
            'end': event.end_date.isoformat(),
            'description': event.description,
            'type': event.event_type.value,
            'extendedProps': {
                'description': event.description,
                'type': event.event_type.value
            }
        })
    
    return jsonify(events_data)