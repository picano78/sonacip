"""Message forms"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length


class MessageForm(FlaskForm):
    """Compose a direct message"""
    recipient = StringField('Destinatario (email o username)', validators=[DataRequired(), Length(max=120)])
    subject = StringField('Oggetto', validators=[Length(max=200)])
    body = TextAreaField('Messaggio', validators=[DataRequired(), Length(min=1, max=5000)])
