from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import AttendanceStatus, SchoolEvent, TeacherAttendance, User, UserRole, Teacher, Student, Classroom, Attendance, SchoolQRCode, jakarta_now
from extensions import db
from . import teacher_bp
from .forms import AttendanceForm
import re
    
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
    
    today = jakarta_now().date()

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

@teacher_bp.route('/attendance', methods=['GET', 'POST'])
def attendance():
    # Get filter parameters
    date_str = request.args.get('date', jakarta_now().strftime('%Y-%m-%d'))
    classroom_id = request.args.get('classroom_id', type=int)
    
    try:
        from datetime import datetime
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        date = jakarta_now().date()
    
    # Format display date
    selected_date_display = date.strftime('%d %B %Y')
    
    # Get teacher info
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    
    # Get classrooms that the teacher can access
    if teacher and teacher.is_homeroom:
        # Homeroom teacher can access their class
        homeroom_class = Classroom.query.filter_by(homeroom_teacher_id=teacher.id).first()
        classrooms = [homeroom_class] if homeroom_class else []
    else:
        # Regular teacher can access all classes
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

    # Handle POST request - Bulk attendance update
    if request.method == 'POST':
        # Get form data
        form_date_str = request.form.get('date')
        form_classroom_id = request.form.get('classroom_id', type=int)
        
        try:
            from datetime import datetime
            form_date = datetime.strptime(form_date_str, '%Y-%m-%d').date()
        except ValueError:
            form_date = date
        
        # Process attendance for each student
        for student in students:
            status_key = f"status_{student.id}"
            notes_key = f"notes_{student.id}"
            
            status_value = request.form.get(status_key)
            notes_value = request.form.get(notes_key, '')
            
            if status_value:
                status_enum = AttendanceStatus(status_value)  # convert string ke Enum
                
                # Check if record already exists
                existing_record = Attendance.query.filter_by(
                    student_id=student.id,
                    date=form_date
                ).first()
                
                if existing_record:
                    # Update existing record
                    existing_record.status = status_enum
                    existing_record.notes = notes_value
                    existing_record.recorded_by = teacher.id if teacher else None
                else:
                    # Create new record
                    new_attendance = Attendance(
                        school_id=current_user.school_id,
                        student_id=student.id,
                        classroom_id=student.classroom_id,
                        date=form_date,
                        status=status_enum,
                        notes=notes_value,
                        recorded_by=teacher.id if teacher else None
                    )
                    db.session.add(new_attendance)

        db.session.commit()
        flash('Absensi berhasil disimpan!', 'success')
        return redirect(url_for('teacher.attendance', date=date_str, classroom_id=classroom_id))

    return render_template('teacher/attendance.html',
                         students=students,
                         classrooms=classrooms,
                         attendance_records=attendance_records,
                         selected_date=date.strftime('%Y-%m-%d'),
                         selected_date_display=selected_date_display,
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
        today = jakarta_now().date()
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

def validate_qr_format(qr_data):
    """
    Validate QR code format and extract information
    Expected formats:
    - STUDENT:NIS:SCHOOL_ID
    - SCHOOL:SCHOOL_ID
    """
    if not qr_data or not isinstance(qr_data, str):
        return None, "Data QR tidak valid"
    
    # Clean the QR data
    qr_data = qr_data.strip()
    
    # Split by colon
    parts = qr_data.split(':')
    
    if len(parts) < 2:
        return None, "Format QR tidak valid. Format yang benar: TYPE:IDENTIFIER:SCHOOL_ID"
    
    qr_type = parts[0].upper()
    
    if qr_type == 'STUDENT':
        if len(parts) != 3:
            return None, "Format QR siswa tidak valid. Format: STUDENT:NIS:SCHOOL_ID"
        
        _, nis, school_id = parts
        
        # Validate school_id is numeric
        try:
            school_id = int(school_id)
        except ValueError:
            return None, "School ID harus berupa angka"
        
        # Validate NIS format (you can customize this)
        if not nis or len(nis) < 3:
            return None, "NIS tidak valid"
        
        return {
            'type': 'STUDENT',
            'nis': nis,
            'school_id': school_id
        }, None
    
    elif qr_type == 'SCHOOL':
        if len(parts) != 2:
            return None, "Format QR sekolah tidak valid. Format: SCHOOL:SCHOOL_ID"
        
        _, school_id = parts
        
        try:
            school_id = int(school_id)
        except ValueError:
            return None, "School ID harus berupa angka"
        
        return {
            'type': 'SCHOOL',
            'school_id': school_id
        }, None
    
    else:
        return None, f"Jenis QR '{qr_type}' tidak dikenali. Gunakan STUDENT atau SCHOOL"

@teacher_bp.route('/scan/process', methods=['POST'])
def process_scan():
    qr_data = request.form.get('qr_data', '').strip()
    manual_status = request.form.get('status', 'hadir')  # For manual input
    manual_notes = request.form.get('notes', '').strip()
    
    if not qr_data:
        return jsonify({'success': False, 'message': 'Tidak ada data QR'})
    
    # Validate and parse QR data
    qr_info, error = validate_qr_format(qr_data)
    if error:
        return jsonify({'success': False, 'message': error})
    
    # Verify school
    if qr_info['school_id'] != current_user.school_id:
        return jsonify({
            'success': False, 
            'message': f'QR code tidak valid untuk sekolah ini (School ID: {qr_info["school_id"]})'
        })
    
    # Get teacher info
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        return jsonify({'success': False, 'message': 'Data guru tidak ditemukan'})
    
    if qr_info['type'] == 'STUDENT':
        return process_student_qr(qr_info, teacher, manual_status, manual_notes)
    elif qr_info['type'] == 'SCHOOL':
        return process_school_qr(qr_info, teacher)
    else:
        return jsonify({'success': False, 'message': 'Jenis QR code tidak dikenali'})

def process_student_qr(qr_info, teacher, status='hadir', notes=''):
    """Process student QR code for attendance"""
    try:
        # Find student by NIS
        student = Student.query.filter_by(
            nis=qr_info['nis'],
            school_id=current_user.school_id
        ).first()
        
        if not student:
            return jsonify({
                'success': False, 
                'message': f'Siswa dengan NIS {qr_info["nis"]} tidak ditemukan'
            })
        
        # Check if student is active
        if not student.user or not student.user.is_active:
            return jsonify({
                'success': False, 
                'message': f'Akun siswa {student.full_name} tidak aktif'
            })
        
        # Get today's date
        today = jakarta_now().date()
        
        # Check if attendance already exists for today
        existing_attendance = Attendance.query.filter_by(
            student_id=student.id,
            date=today
        ).first()
        
        if existing_attendance:
            # Update existing record if status is different or if it's manual input with notes
            if existing_attendance.status.value != status or (notes and existing_attendance.notes != notes):
                old_status = existing_attendance.status.value
                existing_attendance.status = AttendanceStatus(status)
                existing_attendance.recorded_by = teacher.id
                existing_attendance.updated_at = jakarta_now()
                
                if notes:
                    existing_attendance.notes = notes
                
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': f'Absensi {student.full_name} diperbarui dari {old_status.upper()} ke {status.upper()}',
                    'student_name': student.full_name,
                    'student_nis': student.nis,
                    'status': status,
                    'classroom': student.classroom.name if student.classroom else 'Belum ada kelas',
                    'updated': True,
                    'timestamp': jakarta_now().strftime('%H:%M:%S')
                })
            else:
                return jsonify({
                    'success': True,
                    'message': f'{student.full_name} sudah absen hari ini',
                    'student_name': student.full_name,
                    'student_nis': student.nis,
                    'status': existing_attendance.status.value,
                    'classroom': student.classroom.name if student.classroom else 'Belum ada kelas',
                    'already_recorded': True,
                    'recorded_at': existing_attendance.created_at.strftime('%H:%M:%S')
                })
        else:
            # Create new attendance record
            attendance = Attendance(
                school_id=current_user.school_id,
                student_id=student.id,
                classroom_id=student.classroom_id,
                date=today,
                status=AttendanceStatus(status),
                recorded_by=teacher.id,
                notes=notes if notes else None
            )
            
            db.session.add(attendance)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Absensi {student.full_name} berhasil dicatat',
                'student_name': student.full_name,
                'student_nis': student.nis,
                'status': status,
                'classroom': student.classroom.name if student.classroom else 'Belum ada kelas',
                'already_recorded': False,
                'timestamp': jakarta_now().strftime('%H:%M:%S')
            })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error memproses absensi: {str(e)}'
        })

def process_school_qr(qr_info, teacher):
    """Process school QR code for teacher attendance"""
    try:
        today = jakarta_now().date()
        
        # Check if teacher attendance already exists for today
        existing_attendance = TeacherAttendance.query.filter_by(
            teacher_id=teacher.id,
            date=today
        ).first()
        
        if existing_attendance:
            return jsonify({
                'success': True,
                'message': f'Anda sudah absen hari ini pada {existing_attendance.created_at.strftime("%H:%M")}',
                'teacher_name': teacher.full_name,
                'status': existing_attendance.status.value,
                'already_recorded': True
            })
        else:
            # Create new teacher attendance record
            attendance = TeacherAttendance(
                teacher_id=teacher.id,
                school_id=current_user.school_id,
                date=today,
                status=AttendanceStatus.HADIR,
                time_in=jakarta_now(),
                time_out=None
            )
            
            db.session.add(attendance)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Absensi guru {teacher.full_name} berhasil dicatat',
                'teacher_name': teacher.full_name,
                'status': 'hadir',
                'already_recorded': False,
                'timestamp': jakarta_now().strftime('%H:%M:%S')
            })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error memproses absensi guru: {str(e)}'
        })

@teacher_bp.route('/scan/validate', methods=['POST'])
def validate_qr():
    """Validate QR code without processing attendance"""
    qr_data = request.form.get('qr_data', '').strip()
    
    if not qr_data:
        return jsonify({'valid': False, 'message': 'Tidak ada data QR'})
    
    # Validate format
    qr_info, error = validate_qr_format(qr_data)
    if error:
        return jsonify({'valid': False, 'message': error})
    
    # Verify school
    if qr_info['school_id'] != current_user.school_id:
        return jsonify({'valid': False, 'message': 'QR code tidak valid untuk sekolah ini'})
    
    if qr_info['type'] == 'STUDENT':
        student = Student.query.filter_by(
            nis=qr_info['nis'],
            school_id=current_user.school_id
        ).first()
        
        if not student:
            return jsonify({'valid': False, 'message': f'Siswa dengan NIS {qr_info["nis"]} tidak ditemukan'})
        
        return jsonify({
            'valid': True,
            'type': 'student',
            'student_name': student.full_name,
            'student_nis': student.nis,
            'classroom': student.classroom.name if student.classroom else 'Belum ada kelas'
        })
    
    elif qr_info['type'] == 'SCHOOL':
        return jsonify({
            'valid': True,
            'type': 'school',
            'message': 'QR Code sekolah valid untuk absensi guru'
        })
    
    return jsonify({'valid': False, 'message': 'Jenis QR tidak dikenali'})

@teacher_bp.route('/my_attendance')
def my_attendance():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    
    if not teacher:
        flash('Data guru tidak ditemukan.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    # Get date range for filtering
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Default to current month if no dates provided
    if not start_date or not end_date:
        today = jakarta_now().date()
        start_date = today.replace(day=1)
        end_date = today
    else:
        try:
            from datetime import datetime
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Format tanggal tidak valid', 'danger')
            return redirect(url_for('teacher.my_attendance'))

    # Query attendance records with date filter
    records = TeacherAttendance.query.filter(
        TeacherAttendance.teacher_id == teacher.id,
        TeacherAttendance.date >= start_date,
        TeacherAttendance.date <= end_date
    ).order_by(TeacherAttendance.date.desc()).all()

    # Calculate statistics
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
        "percentage": round((hadir / total * 100) if total > 0 else 0, 1)
    }

    return render_template(
        'teacher/my_attendance.html',
        teacher=teacher,
        attendance_stats=attendance_stats,
        records=records,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        current_year=jakarta_now().year
    )

@teacher_bp.route('/attendance/bulk', methods=['POST'])
def bulk_attendance():
    """Bulk attendance processing for multiple students"""
    try:
        data = request.get_json()
        
        if not data or 'students' not in data:
            return jsonify({'success': False, 'message': 'Data tidak valid'})
        
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        if not teacher:
            return jsonify({'success': False, 'message': 'Data guru tidak ditemukan'})
        
        today = jakarta_now().date()
        processed = 0
        errors = []
        
        for student_data in data['students']:
            try:
                student_id = student_data.get('student_id')
                status = student_data.get('status', 'hadir')
                notes = student_data.get('notes', '')
                
                student = Student.query.filter_by(
                    id=student_id,
                    school_id=current_user.school_id
                ).first()
                
                if not student:
                    errors.append(f'Siswa ID {student_id} tidak ditemukan')
                    continue
                
                # Check existing attendance
                existing = Attendance.query.filter_by(
                    student_id=student_id,
                    date=today
                ).first()
                
                if existing:
                    existing.status = AttendanceStatus(status)
                    existing.notes = notes
                    existing.recorded_by = teacher.id
                    existing.updated_at = jakarta_now()
                else:
                    attendance = Attendance(
                        school_id=current_user.school_id,
                        student_id=student_id,
                        classroom_id=student.classroom_id,
                        date=today,
                        status=AttendanceStatus(status),
                        recorded_by=teacher.id,
                        notes=notes
                    )
                    db.session.add(attendance)
                
                processed += 1
                
            except Exception as e:
                errors.append(f'Error processing student {student_data.get("student_id", "unknown")}: {str(e)}')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Berhasil memproses {processed} siswa',
            'processed': processed,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})