"""Forms for Society Calendar events"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SelectMultipleField, BooleanField, DateField, TimeField
from wtforms.validators import DataRequired, Optional, Length
from app.models import User, Society


class SocietyCalendarEventForm(FlaskForm):
    title = StringField('Titolo', validators=[DataRequired(), Length(max=200)])
    team = StringField('Squadra / Categoria', validators=[Optional(), Length(max=100)])
    category = StringField('Categoria', validators=[Optional(), Length(max=100)])
    event_type = SelectField('Tipo', choices=[
        ('match', 'Partita'),
        ('tournament', 'Torneo'),
        ('meeting', 'Riunione'),
        ('travel', 'Trasferta'),
        ('other', 'Altro')
    ], validators=[DataRequired()])
    competition_name = StringField('Competizione', validators=[Optional(), Length(max=200)])
    start_date = DateField('Data Inizio', validators=[DataRequired()])
    start_time = TimeField('Ora Inizio', validators=[DataRequired()])
    end_date = DateField('Data Fine', validators=[Optional()])
    end_time = TimeField('Ora Fine', validators=[Optional()])
    location_text = StringField('Luogo', validators=[Optional(), Length(max=255)])
    notes = TextAreaField('Note', validators=[Optional()])
    share_to_social = BooleanField('Condividi come post sociale')

    society_id = SelectField('Società', coerce=int, validators=[DataRequired()])
    staff_ids = SelectMultipleField('Staff coinvolto', coerce=int, validators=[Optional()])
    athlete_ids = SelectMultipleField('Atleti convocati', coerce=int, validators=[Optional()])

    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        # Populate societies
        society_choices = []
        try:
            societies = Society.query.order_by(Society.legal_name.asc()).all()
            for s in societies:
                society_choices.append((s.id, s.legal_name))
        except Exception:
            pass
        self.society_id.choices = society_choices

        # If not super admin, restrict to their primary society
        if current_user and not current_user.is_admin():
            society = current_user.get_primary_society()
            if society:
                self.society_id.choices = [(society.id, society.legal_name)]
                self.society_id.data = society.id

        # Populate staff/athletes based on chosen society
        chosen_society_id = self.society_id.data
        if chosen_society_id:
            staff = User.query.filter(
                User.society_id == chosen_society_id,
                User.is_active == True
            ).order_by(User.first_name.asc()).all()
            athletes = User.query.filter(
                User.athlete_society_id == chosen_society_id,
                User.is_active == True
            ).order_by(User.first_name.asc()).all()
            self.staff_ids.choices = [(u.id, u.get_full_name()) for u in staff]
            self.athlete_ids.choices = [(u.id, u.get_full_name()) for u in athletes]

        # Keep a sensible default event type
        if not self.event_type.data:
            self.event_type.data = 'match'
