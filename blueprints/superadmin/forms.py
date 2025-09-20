from flask_wtf import FlaskForm
from pyparsing import Regex
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, Regexp
class AdminRegistrationForm(FlaskForm):
    username = StringField('Username Admin', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email Admin', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                    validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Buat Sekolah & Admin')

class SchoolForm(FlaskForm):
    name = StringField('Nama Sekolah', validators=[DataRequired(), Length(max=100)])
    code = StringField('Kode Sekolah', validators=[DataRequired(), Length(max=20)])
    address = TextAreaField('Alamat', validators=[DataRequired()])
    phone = StringField('Telepon', validators=[DataRequired(),Regexp(r'^\d+$', message="Harus berupa angka"), Length(max=20)])
    email = StringField('Email', validators=[DataRequired(), Email(message='Format Email Tidak Valid'), Length(max=100)])
    website = StringField('Website', validators=[Optional(), Length(max=100)])
    brand_name = StringField('Nama Brand', validators=[Optional(), Length(max=100)])
    submit = SubmitField('Simpan')