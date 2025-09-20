from flask_wtf import FlaskForm
from wtforms import HiddenField, SelectField, SubmitField
from wtforms.validators import DataRequired

class AttendanceForm(FlaskForm):
    status = SelectField('Status', choices=[
        ('hadir', 'Hadir'),
        ('izin', 'Izin'),
        ('sakit', 'Sakit'),
        ('alpha', 'Alpha')
    ], validators=[DataRequired()])
    submit = SubmitField('Simpan')

class BulkAttendanceForm(FlaskForm):
    date = HiddenField('Tanggal', validators=[DataRequired()])
    classroom_id = HiddenField('Kelas', validators=[DataRequired()])
    # Kita akan generate field untuk setiap siswa dynamically