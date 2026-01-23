"""
CRM Forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, BooleanField
from wtforms.validators import DataRequired, Email, Optional


class ContactForm(FlaskForm):
    """Form for creating/editing contacts"""
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
    """Form for creating/editing opportunities"""
    title = StringField('Titolo', validators=[DataRequired()])
    description = TextAreaField('Descrizione', validators=[Optional()])
    
    opportunity_type = SelectField('Tipo', choices=[
        ('athlete_recruitment', 'Reclutamento Atleta'),
        ('sponsorship', 'Sponsorizzazione'),
        ('partnership', 'Partnership'),
        ('event', 'Evento'),
        ('membership', 'Iscrizione'),
        ('other', 'Altro')
    ], validators=[DataRequired()])
    
    stage = SelectField('Fase', choices=[
        ('prospecting', 'Prospecting'),
        ('qualification', 'Qualificazione'),
        ('proposal', 'Proposta'),
        ('negotiation', 'Negoziazione'),
        ('closed_won', 'Chiusa - Vinta'),
        ('closed_lost', 'Chiusa - Persa')
    ], validators=[DataRequired()])
    
    value = StringField('Valore (€)', validators=[Optional()])
    probability = SelectField('Probabilità', choices=[
        ('10', '10%'),
        ('25', '25%'),
        ('50', '50%'),
        ('75', '75%'),
        ('90', '90%'),
        ('100', '100%')
    ], validators=[Optional()])
    
    expected_close_date = DateField('Data Chiusura Prevista', format='%Y-%m-%d', validators=[Optional()])
    
    contact_id = SelectField('Contatto Collegato', coerce=int, validators=[Optional()])


class ActivityForm(FlaskForm):
    """Form for logging activities"""
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
    opportunity_id = SelectField('Opportunità', coerce=int, validators=[Optional()])
