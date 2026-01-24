"""Forms for tournament management"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, DateField, BooleanField
from wtforms.validators import DataRequired, Optional, Length

class TournamentForm(FlaskForm):
    name = StringField('Nome Torneo', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Descrizione', validators=[Optional()])
    format = SelectField('Formato', choices=[
        ('round_robin', 'Girone all\'italiana'),
        ('knockout', 'Eliminazione diretta'),
        ('groups_finals', 'Gironi + Finali')
    ], validators=[DataRequired()])
    season = StringField('Stagione', validators=[Optional(), Length(max=50)])
    start_date = DateField('Data inizio', validators=[Optional()])
    end_date = DateField('Data fine', validators=[Optional()])
    auto_select = BooleanField('Selezione automatica squadre')
    auto_criteria = TextAreaField('Criteri auto-selezione (JSON)', validators=[Optional()])

class TournamentTeamForm(FlaskForm):
    name = StringField('Nome squadra', validators=[DataRequired(), Length(max=150)])
    category = StringField('Categoria', validators=[Optional(), Length(max=100)])
    external_ref = StringField('Riferimento esterno', validators=[Optional(), Length(max=100)])

class TournamentMatchForm(FlaskForm):
    home_team_id = IntegerField('Squadra casa', validators=[DataRequired()])
    away_team_id = IntegerField('Squadra trasferta', validators=[DataRequired()])
    round_label = StringField('Turno/Fase', validators=[Optional(), Length(max=100)])
    match_date = DateField('Data', validators=[Optional()])
    location = StringField('Luogo', validators=[Optional(), Length(max=255)])

class MatchScoreForm(FlaskForm):
    home_score = IntegerField('Gol casa', validators=[DataRequired()])
    away_score = IntegerField('Gol trasferta', validators=[DataRequired()])
