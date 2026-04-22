"""Automation management forms for admin panel."""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError
import json


class AutomationRuleForm(FlaskForm):
    """Form for creating/editing automation rules."""
    name = StringField('Nome Regola', validators=[
        DataRequired(message='Il nome è obbligatorio'),
        Length(max=200, message='Nome troppo lungo')
    ])
    
    event_type = SelectField('Tipo Evento', validators=[DataRequired()], choices=[
        ('medical_certificate.expiring', 'Certificato Medico in Scadenza'),
        ('fee.due', 'Quota in Scadenza'),
        ('tournament.created', 'Torneo Creato'),
        ('tournament.started', 'Torneo Iniziato'),
        ('match.scored', 'Partita Conclusa'),
        ('event.created', 'Evento Creato'),
        ('event.upcoming', 'Evento Imminente'),
        ('task.created', 'Task Creato'),
        ('task.completed', 'Task Completato'),
        ('social.posted', 'Post Pubblicato'),
        ('user.registered', 'Utente Registrato'),
        ('subscription.expired', 'Abbonamento Scaduto')
    ])
    
    condition = TextAreaField('Condizione (JSON o espressione)', validators=[
        Optional(),
        Length(max=1000)
    ], description='Es: {"field": "status", "op": "==", "value": "completed"} oppure status == "completed"')
    
    actions = TextAreaField('Azioni (JSON)', validators=[
        DataRequired(message='Le azioni sono obbligatorie')
    ], description='Array JSON di azioni. Es: [{"type": "notify", "user_id": 1, "title": "Test", "message": "Hello"}]')
    
    is_active = BooleanField('Attiva', default=True)
    
    max_retries = IntegerField('Tentativi Massimi', validators=[
        NumberRange(min=0, max=10, message='Da 0 a 10 tentativi')
    ], default=3)
    
    retry_delay = IntegerField('Ritardo Retry (secondi)', validators=[
        NumberRange(min=10, max=3600, message='Da 10 a 3600 secondi')
    ], default=60)
    
    def validate_actions(self, field):
        """Validate actions JSON."""
        try:
            actions = json.loads(field.data)
            if not isinstance(actions, list):
                actions = [actions]
            
            from app.automation.validation import validate_action_schema
            for action in actions:
                is_valid, error = validate_action_schema(action)
                if not is_valid:
                    raise ValidationError(f'Azione non valida: {error}')
        except json.JSONDecodeError as e:
            raise ValidationError(f'JSON non valido: {str(e)}')
    
    def validate_condition(self, field):
        """Validate condition if provided."""
        if not field.data or not field.data.strip():
            return
        
        # Try parsing as JSON
        try:
            json.loads(field.data)
        except json.JSONDecodeError:
            # Allow simple expressions
            import re
            valid_expr = re.match(r'^\w+(?:\.\w+)*\s*(?:==|!=|>|<|>=|<=|contains)\s*.+$', field.data.strip())
            if not valid_expr:
                raise ValidationError('Condizione non valida. Usa JSON o espressione semplice come "status == completed"')
