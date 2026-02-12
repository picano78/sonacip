"""
Event forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateTimeField, SelectMultipleField
from wtforms.validators import DataRequired, Optional, Length
from wtforms.fields import DateTimeLocalField
from app.models import Facility


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
    
    # Field planner integration
    facility_id = SelectField('Campo / Palestra', coerce=int, validators=[Optional()])
    color = StringField('Colore', validators=[Optional(), Length(max=20)])
    
    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        # Populate facilities based on user's society
        facility_choices = [(-1, '— Nessun campo —')]
        if current_user:
            society = current_user.get_primary_society()
            if society:
                facilities = Facility.query.filter_by(society_id=society.id).order_by(Facility.name.asc()).all()
                facility_choices.extend([(f.id, f.name) for f in facilities])
        self.facility_id.choices = facility_choices
        
        # Default color based on event type (only if creating new event, not editing)
        if not self.color.data:
            type_color = {
                'allenamento': '#0dcaf0',  # cyan for training
                'partita': '#198754',      # green for matches
                'torneo': '#0d6efd',       # blue for tournaments
                'meeting': '#6f42c1',      # purple for meetings
                'altro': '#212529',        # dark for other
            }
            self.color.data = type_color.get(self.event_type.data or 'altro', '#212529')
