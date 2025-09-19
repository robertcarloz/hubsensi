from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from extensions import db
from models import AttendanceStatus, SchoolEvent, TeacherAttendance, User, UserRole, Teacher, Student, Classroom, Attendance, SchoolQRCode
from . import teacher_bp
from .forms import AttendanceForm

@teacher_bp.before_request
@login_required
def require_teacher():
    if current_user.role != UserRole.TEACHER:
        flash('Akses ditolak. Hanya untuk Guru/Staff.', 'danger')
        return redirect(url_for('auth.login'))

@teacher_bp.route('/dashboard')
def dashboard():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    
    # Homeroom class
    homeroom_class = None
    if teacher and teacher.is_homeroom:
        homeroom_class = Classroom.query.filter_by(homeroom_teacher_id=teacher.id).first()
    
    today = datetime.now().date()

    # Upcoming events khusus sekolah
    upcoming_events = SchoolEvent.query.filter(
    SchoolEvent.school_id == current_user.school_id,
    SchoolEvent.end_date >= today  # artinya event belum berakhir
    ).order_by(SchoolEvent.start_date.asc()).limit(3).all()

    # Recent activities (misal absensi terbaru di sekolah)
    recent_activities = Attendance.query.join(Student).filter(
        Attendance.school_id == current_user.school_id
    ).order_by(Attendance.date.desc()).limit(3).all()

    # Attendance stats hanya untuk homeroom class
    attendance_stats = {"hadir": 0, "sakit": 0, "izin": 0, "alpa": 0}
    if homeroom_class:
        # Ambil siswa di kelas itu
        student_ids = [s.id for s in Student.query.filter_by(classroom_id=homeroom_class.id).all()]
        
        # Ambil attendance hari ini untuk siswa-siswa itu
        attendance_records = Attendance.query.filter(
            Attendance.student_id.in_(student_ids),
            Attendance.date == today
        ).all()
        
        for a in attendance_records:
            if a.status in attendance_stats:
                attendance_stats[a.status] += 1

    return render_template(
        'teacher/dashboard.html',
        teacher=teacher,
        homeroom_class=homeroom_class,
        today=today,
        upcoming_events=upcoming_events,
        recent_activities=recent_activities,
        attendance_stats=attendance_stats
    )

@teacher_bp.route('/attendance')
def attendance():
    # Get filter parameters
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    classroom_id = request.args.get('classroom_id', type=int)
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        date = datetime.now().date()
    
    # Get teacher info
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    
    # Get classrooms that the teacher can access
    if teacher and teacher.is_homeroom:
        # Homeroom teacher can access their class
        homeroom_class = Classroom.query.filter_by(homeroom_teacher_id=teacher.id).first()
        classrooms = [homeroom_class] if homeroom_class else []
    else:
        # Regular teacher can access all classes (or implement your own logic)
        classrooms = Classroom.query.filter_by(school_id=current_user.school_id).all()
    
    # Get students based on filters
    students_query = Student.query.filter_by(school_id=current_user.school_id)
    
    if classroom_id:
        students_query = students_query.filter_by(classroom_id=classroom_id)
    
    students = students_query.all()
    
    # Get existing attendance records
    attendance_records = {}
    if students:
        student_ids = [s.id for s in students]
        records = Attendance.query.filter(
            Attendance.student_id.in_(student_ids),
            Attendance.date == date
        ).all()
        
        for record in records:
            attendance_records[record.student_id] = record
    
    return render_template('teacher/attendance.html',
                         students=students,
                         classrooms=classrooms,
                         attendance_records=attendance_records,
                         selected_date=date.strftime('%Y-%m-%d'),
                         selected_classroom=classroom_id)

@teacher_bp.route('/attendance/<int:student_id>', methods=['POST'])
def record_attendance(student_id):
    student = Student.query.filter_by(
        id=student_id, 
        school_id=current_user.school_id
    ).first_or_404()
    
    form = AttendanceForm()
    
    if form.validate_on_submit():
        # Get teacher info
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        
        # Check if attendance already exists for today
        today = datetime.now().date()
        attendance = Attendance.query.filter_by(
            student_id=student_id,
            date=today
        ).first()
        
        if attendance:
            # Update existing record
            attendance.status = form.status.data
            attendance.recorded_by = teacher.id if teacher else None
            flash('Absensi berhasil diperbarui!', 'success')
        else:
            # Create new record
            attendance = Attendance(
                school_id=current_user.school_id,
                student_id=student_id,
                classroom_id=student.classroom_id,
                date=today,
                status=form.status.data,
                recorded_by=teacher.id if teacher else None
            )
            db.session.add(attendance)
            flash('Absensi berhasil dicatat!', 'success')
        
        db.session.commit()
    
    return redirect(url_for('teacher.attendance'))

@teacher_bp.route('/scan')
def scan():
    return render_template('teacher/scan.html')

@teacher_bp.route('/scan/process', methods=['POST'])
def process_scan():
    qr_data = request.form.get('qr_data')
    
    if not qr_data:
        return jsonify({'success': False, 'message': 'Tidak ada data QR'})
    
    # Parse QR data
    parts = qr_data.split(':')
    if len(parts) != 3:
        return jsonify({'success': False, 'message': 'Format QR tidak valid'})
    
    qr_type, identifier, school_id = parts
    
    # Verify school
    if int(school_id) != current_user.school_id:
        return jsonify({'success': False, 'message': 'QR code tidak valid untuk sekolah ini'})
    
    if qr_type == 'STUDENT':
        # Student QR code
        student = Student.query.filter_by(
            nis=identifier,
            school_id=current_user.school_id
        ).first()
        
        if not student:
            return jsonify({'success': False, 'message': 'Siswa tidak ditemukan'})
        
        # Get teacher info
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        
        # Check if attendance already exists for today
        today = datetime.now().date()
        attendance = Attendance.query.filter_by(
            student_id=student.id,
            date=today
        ).first()
        
        if attendance:
            return jsonify({
                'success': True, 
                'message': f'{student.full_name} sudah absen hari ini',
                'student_name': student.full_name,
                'status': attendance.status.value,
                'already_recorded': True
            })
        else:
            # Create new record with default status "hadir"
            attendance = Attendance(
                school_id=current_user.school_id,
                student_id=student.id,
                classroom_id=student.classroom_id,
                date=today,
                status='hadir',
                recorded_by=teacher.id if teacher else None
            )
            db.session.add(attendance)
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'message': f'Absensi {student.full_name} berhasil dicatat',
                'student_name': student.full_name,
                'status': 'hadir',
                'already_recorded': False
            })
    
    elif qr_type == 'SCHOOL':
        # School QR code (for teacher attendance)
        # Implement teacher attendance logic here
        return jsonify({'success': True, 'message': 'QR code sekolah terdeteksi'})
    
    else:
        return jsonify({'success': False, 'message': 'Jenis QR code tidak dikenali'})

from datetime import date

@teacher_bp.route('/my_attendance')
def my_attendance():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    
    if not teacher:
        flash('Data guru tidak ditemukan.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    # Query attendance guru ini
    records = TeacherAttendance.query.filter_by(teacher_id=teacher.id).all()

    total = len(records)
    hadir = sum(1 for r in records if r.status == AttendanceStatus.HADIR)
    izin = sum(1 for r in records if r.status == AttendanceStatus.IZIN)
    sakit = sum(1 for r in records if r.status == AttendanceStatus.SAKIT)
    alpha = sum(1 for r in records if r.status == AttendanceStatus.ALPHA)

    attendance_stats = {
        "total": total,
        "hadir": hadir,
        "izin": izin,
        "sakit": sakit,
        "alpha": alpha,
    }

    return render_template(
        'teacher/my_attendance.html',
        teacher=teacher,
        attendance_stats=attendance_stats,
        records=records,
        current_year=date.today().year   # ✅ kirim current_year ke template
    )

