from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, DateField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, Email, Optional
from wtforms.widgets import TextArea

class TeacherForm(FlaskForm):
    full_name = StringField('Nama Lengkap', validators=[DataRequired()])
    nip = StringField('NIP', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    is_homeroom = BooleanField('Wali Kelas')  # checkbox saja
    submit = SubmitField('Simpan')


class StudentForm(FlaskForm):
    nis = StringField('NIS', validators=[DataRequired()])
    nisn = StringField('NISN', validators=[Optional()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    full_name = StringField('Nama Lengkap', validators=[DataRequired()])
    classroom_id = SelectField('Kelas', coerce=int)
    submit = SubmitField('Simpan')

class ClassroomForm(FlaskForm):
    name = StringField('Nama Kelas', validators=[DataRequired()])
    grade_level = StringField('Tingkat Kelas', validators=[Optional()])
    homeroom_teacher_id = SelectField('Wali Kelas', coerce=int)
    submit = SubmitField('Simpan')

class EventForm(FlaskForm):
    title = StringField('Judul', validators=[DataRequired()])
    description = TextAreaField('Deskripsi', validators=[Optional()])
    start_date = DateField('Tanggal Mulai', format='%Y-%m-%d', validators=[DataRequired()])
    end_date = DateField('Tanggal Selesai', format='%Y-%m-%d', validators=[DataRequired()])
    event_type = SelectField('Jenis Event', choices=[
        ('acara', 'Acara'),
        ('libur', 'Libur'),
        ('ujian', 'Ujian')
    ], validators=[DataRequired()])
    is_holiday = SelectField('Hari Libur', choices=[
        (False, 'Tidak'),
        (True, 'Ya')
    ], coerce=lambda x: x == 'True')
    submit = SubmitField('Simpan')

class SchoolSettingsForm(FlaskForm):
    name = StringField('Nama Sekolah', validators=[Optional()])
    brand_name = StringField('Nama Brand', validators=[Optional()])
    address = TextAreaField('Alamat', validators=[Optional()])
    phone = StringField('Telepon', validators=[Optional()])
    email = StringField('Email', validators=[Optional(), Email()])
    website = StringField('Website', validators=[Optional()])
    primary_color = StringField('Warna Primer', default='#0d6efd', validators=[Optional()])
    secondary_color = StringField('Warna Sekunder', default='#6c757d', validators=[Optional()])
    logo_url = StringField('URL Logo', validators=[Optional()])
    submit = SubmitField('Simpan')