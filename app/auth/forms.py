"""
Authentication forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Optional, Length
from app.models import User, Role


def _registration_role_choices():
    allowed_names = ['appassionato', 'atleta', 'athlete']
    try:
        roles = Role.query.filter(Role.name.in_(allowed_names), Role.is_active == True).all()
        choices = [(r.name, r.display_name or r.name) for r in roles]
    except Exception:
        choices = [
            ('appassionato', 'Appassionato'),
            ('atleta', 'Atleta'),
            ('athlete', 'Athlete')
        ]
    ordered = []
    for name in allowed_names:
        for slug, label in choices:
            if slug == name:
                ordered.append((slug, label))
    return ordered or choices


class LoginForm(FlaskForm):
    """Login form"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Ricordami')


class RegistrationForm(FlaskForm):
    """Registration form for individuals (Appassionato/Atleta)"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=80, message='Username deve essere tra 3 e 80 caratteri')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password deve essere almeno 6 caratteri')
    ])
    password2 = PasswordField('Conferma Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Le password devono coincidere')
    ])
    first_name = StringField('Nome', validators=[DataRequired()])
    last_name = StringField('Cognome', validators=[DataRequired()])
    phone = StringField('Telefono', validators=[Optional()])
    role = SelectField('Tipo Account', choices=[], validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role.choices = _registration_role_choices()
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email già registrata. Usa un\'altra email.')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username già in uso. Scegline un altro.')


class SocietyRegistrationForm(FlaskForm):
    """Registration form for sports societies"""
    # Account credentials
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80, message='Username deve essere tra 3 e 80 caratteri')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password deve essere almeno 6 caratteri')
    ])
    password2 = PasswordField('Conferma Password', validators=[
        DataRequired(),
        EqualTo('password', message='Le password devono coincidere')
    ])
    
    # Society information
    company_name = StringField('Nome Società', validators=[DataRequired()])
    company_type = SelectField('Tipo Società', choices=[
        ('ASD', 'Associazione Sportiva Dilettantistica (ASD)'),
        ('SSD', 'Società Sportiva Dilettantistica (SSD)'),
        ('SRL', 'S.R.L. Sportiva'),
        ('altro', 'Altro')
    ], validators=[DataRequired()])
    fiscal_code = StringField('Codice Fiscale', validators=[DataRequired()])
    vat_number = StringField('Partita IVA', validators=[Optional()])
    
    # Contact info
    phone = StringField('Telefono', validators=[DataRequired()])
    address = StringField('Indirizzo', validators=[DataRequired()])
    city = StringField('Città', validators=[DataRequired()])
    province = StringField('Provincia', validators=[DataRequired(), Length(max=2)])
    postal_code = StringField('CAP', validators=[DataRequired()])
    website = StringField('Sito Web', validators=[Optional()])
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email già registrata. Usa un\'altra email.')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username già in uso. Scegline un altro.')
