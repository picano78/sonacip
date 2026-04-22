"""Forms for Field Planner"""
from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, DateField, TimeField, SelectField,
    BooleanField, IntegerField, SubmitField
)
from wtforms.validators import DataRequired, Optional, ValidationError
from datetime import datetime, date


class FieldPlannerEventForm(FlaskForm):
    """Form for creating/editing field planner events"""
    
    facility_id = SelectField('Campo/Risorsa', coerce=int, validators=[DataRequired(message='Seleziona un campo')])
    event_type = SelectField(
        'Tipo Evento',
        choices=[
            ('training', 'Allenamento'),
            ('match', 'Partita')
        ],
        validators=[DataRequired()]
    )
    
    title = StringField('Titolo', validators=[DataRequired(message='Titolo obbligatorio')])
    team = StringField('Squadra', validators=[Optional()])
    category = StringField('Categoria', validators=[Optional()])
    
    start_date = DateField('Data Inizio', format='%Y-%m-%d', validators=[DataRequired()])
    start_time = TimeField('Ora Inizio', format='%H:%M', validators=[DataRequired()])
    end_time = TimeField('Ora Fine', format='%H:%M', validators=[DataRequired()])
    
    # Recurring training for entire season
    is_recurring = BooleanField('Allenamento ricorrente (tutta la stagione)', default=False)
    recurrence_pattern = SelectField(
        'Frequenza',
        choices=[
            ('', 'Seleziona'),
            ('weekly', 'Settimanale (stesso giorno della settimana)')
        ],
        validators=[Optional()]
    )
    
    notes = TextAreaField('Note', validators=[Optional()])
    color = StringField('Colore', default='#28a745', validators=[Optional()])
    
    submit = SubmitField('Salva Evento')
    
    def validate_end_time(self, field):
        """Ensure end time is after start time"""
        if self.start_time.data and field.data:
            if field.data <= self.start_time.data:
                raise ValidationError('L\'ora di fine deve essere successiva all\'ora di inizio')
    
    def validate_is_recurring(self, field):
        """If recurring is checked, pattern must be selected"""
        if field.data and not self.recurrence_pattern.data:
            raise ValidationError('Seleziona la frequenza per eventi ricorrenti')
