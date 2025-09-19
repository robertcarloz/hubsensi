from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired

class AttendanceForm(FlaskForm):
    status = SelectField('Status', choices=[
        ('hadir', 'Hadir'),
        ('izin', 'Izin'),
        ('sakit', 'Sakit'),
        ('alpha', 'Alpha')
    ], validators=[DataRequired()])
    submit = SubmitField('Simpan')