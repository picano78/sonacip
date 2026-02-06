"""
CRM Forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, BooleanField, IntegerField, HiddenField
from wtforms.validators import DataRequired, Email, Optional, Length
from app.models import User, SocietyMembership


class ContactForm(FlaskForm):
    first_name = StringField('Nome', validators=[DataRequired()])
    last_name = StringField('Cognome', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Telefono', validators=[Optional()])
    company = StringField('Azienda/Società', validators=[Optional()])
    position = StringField('Posizione', validators=[Optional()])

    contact_type = SelectField('Tipo Contatto', choices=[
        ('prospect', 'Prospect'),
        ('athlete', 'Atleta Potenziale'),
        ('sponsor', 'Sponsor'),
        ('partner', 'Partner'),
        ('parent', 'Genitore'),
        ('other', 'Altro')
    ], validators=[DataRequired()])

    status = SelectField('Stato', choices=[
        ('new', 'Nuovo'),
        ('contacted', 'Contattato'),
        ('interested', 'Interessato'),
        ('converted', 'Convertito'),
        ('lost', 'Perso')
    ], validators=[DataRequired()])

    source = SelectField('Fonte', choices=[
        ('website', 'Sito Web'),
        ('social', 'Social Media'),
        ('referral', 'Referral'),
        ('event', 'Evento'),
        ('advertising', 'Pubblicità'),
        ('other', 'Altro')
    ], validators=[Optional()])

    notes = TextAreaField('Note', validators=[Optional()])
    address = StringField('Indirizzo', validators=[Optional()])
    city = StringField('Città', validators=[Optional()])
    postal_code = StringField('CAP', validators=[Optional()])


class OpportunityForm(FlaskForm):
    """Deprecated – kept as stub for import compatibility."""
    pass


class PipelineStageForm(FlaskForm):
    """Deprecated – kept as stub for import compatibility."""
    pass


class ActivityForm(FlaskForm):
    activity_type = SelectField('Tipo Attività', choices=[
        ('call', 'Chiamata'),
        ('email', 'Email'),
        ('meeting', 'Incontro'),
        ('note', 'Nota'),
        ('task', 'Task'),
        ('other', 'Altro')
    ], validators=[DataRequired()])

    subject = StringField('Oggetto', validators=[DataRequired()])
    description = TextAreaField('Descrizione', validators=[Optional()])
    activity_date = DateField('Data', format='%Y-%m-%d', validators=[Optional()])
    completed = BooleanField('Completata')

    contact_id = SelectField('Contatto', coerce=int, validators=[Optional()])


class MedicalCertificateForm(FlaskForm):
    user_id = SelectField('Atleta', coerce=int, validators=[DataRequired()])
    issued_on = DateField('Data rilascio', format='%Y-%m-%d', validators=[Optional()])
    expires_on = DateField('Data scadenza', format='%Y-%m-%d', validators=[DataRequired()])
    status = SelectField('Stato', choices=[
        ('valid', 'Valido'),
        ('expired', 'Scaduto'),
        ('revoked', 'Revocato'),
    ], validators=[DataRequired()])
    notes = TextAreaField('Note', validators=[Optional(), Length(max=2000)])

    def __init__(self, *args, **kwargs):
        society_id = kwargs.pop('society_id', None)
        super().__init__(*args, **kwargs)
        choices = []
        if society_id:
            athlete_ids = (
                SocietyMembership.query.filter(
                    SocietyMembership.society_id == society_id,
                    SocietyMembership.status == 'active',
                    SocietyMembership.role_name.in_(['atleta', 'athlete']),
                )
                .with_entities(SocietyMembership.user_id)
                .all()
            )
            athlete_ids = [r[0] for r in athlete_ids]
            athletes = User.query.filter(User.id.in_(athlete_ids), User.is_active == True).order_by(User.first_name.asc()).all() if athlete_ids else []
            choices = [(u.id, u.get_full_name()) for u in athletes]
        self.user_id.choices = choices


class SocietyFeeForm(FlaskForm):
    user_id = SelectField('Membro', coerce=int, validators=[DataRequired()])
    description = StringField('Descrizione', validators=[Optional(), Length(max=255)])
    amount_eur = StringField('Importo (€)', validators=[DataRequired(), Length(max=20)])
    due_on = DateField('Scadenza', format='%Y-%m-%d', validators=[DataRequired()])
    status = SelectField('Stato', choices=[
        ('pending', 'In attesa'),
        ('paid', 'Pagata'),
        ('cancelled', 'Annullata'),
    ], validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        society_id = kwargs.pop('society_id', None)
        super().__init__(*args, **kwargs)
        choices = []
        if society_id:
            member_ids = (
                SocietyMembership.query.filter(
                    SocietyMembership.society_id == society_id,
                    SocietyMembership.status == 'active',
                )
                .with_entities(SocietyMembership.user_id)
                .all()
            )
            member_ids = [r[0] for r in member_ids]
            members = User.query.filter(User.id.in_(member_ids), User.is_active == True).order_by(User.first_name.asc()).all() if member_ids else []
            choices = [(u.id, u.get_full_name()) for u in members]
        self.user_id.choices = choices


class MemberSearchForm(FlaskForm):
    q = StringField('Cerca utente', validators=[Optional(), Length(max=120)])


class MemberAddForm(FlaskForm):
    user_id = HiddenField('user_id', validators=[DataRequired()])
    role_name = SelectField('Ruolo', choices=[
        ('atleta', 'Atleta'),
        ('coach', 'Coach'),
        ('dirigente', 'Dirigente'),
        ('staff', 'Staff'),
        ('appassionato', 'Appassionato'),
    ], validators=[DataRequired()])
