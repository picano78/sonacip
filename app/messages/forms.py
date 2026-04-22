"""Message forms"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Length, Optional, NumberRange


class MessageForm(FlaskForm):
    """Compose a direct message"""
    recipient = StringField('Destinatario (email o username)', validators=[DataRequired(), Length(max=120)])
    subject = StringField('Oggetto', validators=[Length(max=200)])
    body = TextAreaField('Messaggio', validators=[DataRequired(), Length(min=1, max=5000)])


class MessageGroupForm(FlaskForm):
    """Create or edit a message group"""
    name = StringField('Nome del gruppo', validators=[DataRequired(), Length(min=1, max=120)])
    description = TextAreaField('Descrizione', validators=[Optional(), Length(max=500)])
    avatar = FileField('Avatar del gruppo', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Solo immagini!')])
    is_announcement_only = BooleanField('Solo amministratori possono inviare messaggi')
    max_members = IntegerField('Numero massimo di membri', 
                               validators=[Optional(), NumberRange(min=2, max=256)],
                               default=256)
