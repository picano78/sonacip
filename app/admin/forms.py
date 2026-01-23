"""
Admin forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, TextAreaField, PasswordField
from wtforms.validators import DataRequired, Email, Optional, Length


class UserEditForm(FlaskForm):
    """Form for editing users"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired()])
    first_name = StringField('Nome', validators=[Optional()])
    last_name = StringField('Cognome', validators=[Optional()])
    phone = StringField('Telefono', validators=[Optional()])
    role = SelectField('Ruolo', choices=[
        ('super_admin', 'Super Admin'),
        ('societa', 'Società Sportiva'),
        ('staff', 'Staff'),
        ('atleta', 'Atleta'),
        ('appassionato', 'Appassionato')
    ], validators=[DataRequired()])
    is_active = BooleanField('Account Attivo')
    is_verified = BooleanField('Account Verificato')


class UserSearchForm(FlaskForm):
    """Form for searching users"""
    query = StringField('Cerca', validators=[Optional()])
    role = SelectField('Ruolo', choices=[
        ('', 'Tutti'),
        ('super_admin', 'Super Admin'),
        ('societa', 'Società Sportiva'),
        ('staff', 'Staff'),
        ('atleta', 'Atleta'),
        ('appassionato', 'Appassionato')
    ], validators=[Optional()])
    status = SelectField('Stato', choices=[
        ('', 'Tutti'),
        ('active', 'Attivi'),
        ('inactive', 'Disattivati'),
        ('verified', 'Verificati'),
        ('unverified', 'Non Verificati')
    ], validators=[Optional()])
