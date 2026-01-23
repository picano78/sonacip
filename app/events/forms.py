"""
Event forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateTimeField, SelectMultipleField
from wtforms.validators import DataRequired, Optional, Length
from wtforms.fields import DateTimeLocalField


class EventForm(FlaskForm):
    """Form for creating/editing events"""
    title = StringField('Titolo', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Descrizione', validators=[Optional()])
    event_type = SelectField('Tipo Evento', choices=[
        ('allenamento', 'Allenamento'),
        ('partita', 'Partita'),
        ('torneo', 'Torneo'),
        ('meeting', 'Riunione'),
        ('altro', 'Altro')
    ], validators=[DataRequired()])
    start_date = DateTimeLocalField('Data e Ora Inizio', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    end_date = DateTimeLocalField('Data e Ora Fine', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    location = StringField('Località', validators=[Optional(), Length(max=255)])
    address = StringField('Indirizzo', validators=[Optional(), Length(max=255)])
