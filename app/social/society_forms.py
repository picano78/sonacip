"""
Society management forms (memberships/invites).
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Optional, Length


class SocietyInviteForm(FlaskForm):
    user_query = StringField('Cerca persona (email o username)', validators=[DataRequired(), Length(max=120)])
    requested_role = SelectField(
        'Ruolo da assegnare',
        choices=[
            ('atleta', 'Atleta'),
            ('coach', 'Coach'),
            ('staff', 'Staff'),
            ('dirigente', 'Dirigente'),
            ('appassionato', 'Appassionato'),
        ],
        validators=[DataRequired()],
    )
    note = TextAreaField('Nota (opzionale)', validators=[Optional(), Length(max=500)])

