"""
Main (user-facing) forms.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length


class DashboardEditForm(FlaskForm):
    name = StringField('Nome cruscotto', validators=[DataRequired(), Length(max=200)])
    widgets = TextAreaField('Widgets (JSON array)', validators=[DataRequired(), Length(max=50000)])

