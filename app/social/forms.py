"""
Social forms
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import TextAreaField, StringField, BooleanField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, Optional, NumberRange


class PostForm(FlaskForm):
    """Form for creating posts"""
    content = TextAreaField('Cosa vuoi condividere?', validators=[
        DataRequired(),
        Length(min=1, max=5000, message='Il post deve essere tra 1 e 5000 caratteri')
    ])
    image = FileField('Immagine', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Solo immagini!')
    ])


class CommentForm(FlaskForm):
    """Form for commenting on posts"""
    content = TextAreaField('Commento', validators=[
        DataRequired(),
        Length(min=1, max=1000, message='Il commento deve essere tra 1 e 1000 caratteri')
    ])


class ProfileEditForm(FlaskForm):
    """Form for editing profile"""
    first_name = StringField('Nome', validators=[Optional()])
    last_name = StringField('Cognome', validators=[Optional()])
    phone = StringField('Telefono', validators=[Optional()])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=500)])
    website = StringField('Sito Web', validators=[Optional()])
    language = SelectField('Lingua / Language', choices=[
        ('it', 'Italiano'),
        ('en', 'English')
    ], default='it')
    avatar = FileField('Avatar', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Solo immagini!')
    ])
    cover_photo = FileField('Foto Copertina', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Solo immagini!')
    ])


class SearchForm(FlaskForm):
    """Form for searching users/societies"""
    query = StringField('Cerca', validators=[Optional()])


class PromotePostForm(FlaskForm):
    """Form per sponsorizzare un post"""
    duration_days = IntegerField('Durata (giorni)', validators=[DataRequired(), NumberRange(min=1, max=30)])
    views = IntegerField('Impression desiderate', validators=[DataRequired(), NumberRange(min=100, max=50000)])
