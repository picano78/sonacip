"""Forms for Society Calendar events"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SelectMultipleField, BooleanField, DateField, TimeField, IntegerField
from wtforms.validators import DataRequired, Optional, Length
from app.models import User, Society, Facility, SocietyMembership
from app.utils import check_permission


class SocietyCalendarEventForm(FlaskForm):
    title = StringField('Titolo', validators=[Optional(), Length(max=200)])
    team = StringField('Squadra / Categoria', validators=[Optional(), Length(max=100)])
    category = StringField('Categoria', validators=[Optional(), Length(max=100)])
    event_type = SelectField('Tipo', choices=[
        ('match', 'Partita'),
        ('tournament', 'Torneo'),
        ('meeting', 'Riunione'),
        ('travel', 'Trasferta'),
        ('other', 'Altro')
    ], validators=[Optional()])
    competition_name = StringField('Competizione', validators=[Optional(), Length(max=200)])
    start_date = DateField('Data Inizio', validators=[Optional()])
    start_time = TimeField('Ora Inizio', validators=[Optional()])
    end_date = DateField('Data Fine', validators=[Optional()])
    end_time = TimeField('Ora Fine', validators=[Optional()])
    facility_id = SelectField('Palestra / Risorsa', coerce=int, validators=[Optional()])
    color = StringField('Colore', validators=[Optional(), Length(max=20)])
    location_text = StringField('Luogo', validators=[Optional(), Length(max=255)])
    notes = TextAreaField('Note', validators=[Optional()])
    share_to_social = BooleanField('Condividi come post sociale')

    society_id = SelectField('Società', coerce=int, validators=[Optional()])
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
        if current_user and not check_permission(current_user, 'admin', 'access'):
            society = current_user.get_primary_society()
            if society:
                self.society_id.choices = [(society.id, society.legal_name)]
                self.society_id.data = society.id

        # Populate staff/athletes based on chosen society
        chosen_society_id = self.society_id.data
        if chosen_society_id:
            staff_ids = (
                SocietyMembership.query.filter(
                    SocietyMembership.society_id == chosen_society_id,
                    SocietyMembership.status == 'active',
                    SocietyMembership.role_name.in_(['staff', 'coach', 'dirigente']),
                )
                .with_entities(SocietyMembership.user_id)
                .all()
            )
            staff_ids = [row[0] for row in staff_ids]
            athlete_ids = (
                SocietyMembership.query.filter(
                    SocietyMembership.society_id == chosen_society_id,
                    SocietyMembership.status == 'active',
                    SocietyMembership.role_name.in_(['atleta', 'athlete']),
                )
                .with_entities(SocietyMembership.user_id)
                .all()
            )
            athlete_ids = [row[0] for row in athlete_ids]

            staff = User.query.filter(User.id.in_(staff_ids), User.is_active == True).order_by(User.first_name.asc()).all() if staff_ids else []
            athletes = User.query.filter(User.id.in_(athlete_ids), User.is_active == True).order_by(User.first_name.asc()).all() if athlete_ids else []
            self.staff_ids.choices = [(u.id, u.get_full_name()) for u in staff]
            self.athlete_ids.choices = [(u.id, u.get_full_name()) for u in athletes]

            # Facilities for the society
            facilities = Facility.query.filter_by(society_id=chosen_society_id).order_by(Facility.name.asc()).all()
            self.facility_id.choices = [(-1, '— Nessuna risorsa —')] + [(f.id, f.name) for f in facilities]

        # Default color heuristic
        if not self.color.data:
            type_color = {
                'match': '#198754',
                'tournament': '#0d6efd',
                'meeting': '#6f42c1',
                'travel': '#fd7e14',
                'other': '#212529',
            }
            self.color.data = type_color.get(self.event_type.data or 'other', '#212529')

        # Keep a sensible default event type
        if not self.event_type.data:
            self.event_type.data = 'match'


class FacilityForm(FlaskForm):
    name = StringField('Nome', validators=[Optional(), Length(max=200)])
    address = StringField('Indirizzo', validators=[Optional(), Length(max=255)])
    capacity = IntegerField('Capienza', validators=[Optional()])
    color = StringField('Colore', validators=[Optional(), Length(max=20)])
