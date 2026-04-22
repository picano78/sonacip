"""
Main (user-facing) forms.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length


class DashboardEditForm(FlaskForm):
    name = StringField('Nome cruscotto', validators=[DataRequired(), Length(max=200)])
    widgets = TextAreaField('Widgets (JSON array)', validators=[DataRequired(), Length(max=50000)])


class ContactAdminForm(FlaskForm):
    subject = StringField('Oggetto', validators=[
        DataRequired(message='L\'oggetto è obbligatorio.'),
        Length(min=5, max=200, message='L\'oggetto deve essere tra 5 e 200 caratteri.')
    ])
    category = SelectField('Categoria', validators=[DataRequired(message='Seleziona una categoria.')], choices=[
        ('', 'Seleziona una categoria...'),
        ('supporto_tecnico', 'Supporto Tecnico'),
        ('segnalazione_bug', 'Segnalazione Bug'),
        ('richiesta_funzionalita', 'Richiesta Funzionalità'),
        ('domanda_generale', 'Domanda Generale'),
        ('problemi_account', 'Problemi Account'),
        ('altro', 'Altro')
    ])
    message = TextAreaField('Messaggio', validators=[
        DataRequired(message='Il messaggio è obbligatorio.'),
        Length(min=10, max=2000, message='Il messaggio deve essere tra 10 e 2000 caratteri.')
    ])

