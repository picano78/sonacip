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
    tournament_name = StringField('Nome Torneo', validators=[Optional(), Length(max=200)])
    tournament_phase = StringField('Fase Torneo', validators=[Optional(), Length(max=50)])
    opponent_name = StringField('Avversario', validators=[Optional(), Length(max=200)])
    home_away = SelectField('Casa/Trasferta', choices=[
        ('', '---'),
        ('home', 'Casa'),
        ('away', 'Trasferta'),
        ('neutral', 'Campo neutro')
    ], validators=[Optional()])
    score_for = StringField('Punteggio Pro', validators=[Optional(), Length(max=10)])
    score_against = StringField('Punteggio Contro', validators=[Optional(), Length(max=10)])
    bracket_url = StringField('Link Tabellone', validators=[Optional(), Length(max=255)])
    start_date = DateTimeLocalField('Data e Ora Inizio', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    end_date = DateTimeLocalField('Data e Ora Fine', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    location = StringField('Località', validators=[Optional(), Length(max=255)])
    address = StringField('Indirizzo', validators=[Optional(), Length(max=255)])
