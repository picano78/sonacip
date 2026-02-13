"""
Security Event Logger
Traccia eventi sospetti e potenziali attacchi
"""

import logging
from datetime import datetime, timezone
from flask import request, current_app
from app import db
from app.models import AuditLog

# Security event types
SECURITY_EVENTS = {
    'FAILED_LOGIN_ATTEMPT': 'Tentativo di login fallito',
    'MULTIPLE_FAILED_LOGINS': 'Multipli tentativi di login falliti',
    'SUSPICIOUS_FILE_UPLOAD': 'Tentativo di upload file sospetto',
    'POTENTIAL_XSS': 'Potenziale tentativo XSS',
    'POTENTIAL_SQL_INJECTION': 'Potenziale tentativo SQL Injection',
    'CSRF_TOKEN_INVALID': 'Token CSRF invalido',
    'PATH_TRAVERSAL_ATTEMPT': 'Tentativo di path traversal',
    'RATE_LIMIT_EXCEEDED': 'Rate limit superato',
    'UNAUTHORIZED_ACCESS': 'Tentativo di accesso non autorizzato',
    'SESSION_HIJACK_ATTEMPT': 'Potenziale session hijacking',
    'CSP_VIOLATION': 'Violazione CSP',
    'SUPER_ADMIN_LOGIN': 'Accesso super admin',
}

class SecurityEventLogger:
    """Logger centralizzato per eventi di sicurezza"""
    
    def __init__(self, app=None):
        self.app = app
        self.logger = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Inizializza il logger con l'app Flask"""
        self.logger = logging.getLogger('security')
        handler = logging.FileHandler(
            app.config.get('SECURITY_LOG_FILE', 'logs/security.log')
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.WARNING)
    
    def log_event(self, event_type, details=None, user_id=None, severity='warning'):
        """
        Logga un evento di sicurezza
        
        Args:
            event_type: Tipo di evento (da SECURITY_EVENTS)
            details: Dettagli aggiuntivi dell'evento
            user_id: ID dell'utente coinvolto (se disponibile)
            severity: Livello di gravità (info, warning, error, critical)
        """
        if event_type not in SECURITY_EVENTS:
            event_type = 'UNKNOWN_EVENT'
        
        description = SECURITY_EVENTS.get(event_type, 'Evento sconosciuto')
        
        # Log su file
        log_message = f"[{event_type}] {description}"
        if details:
            log_message += f" - {details}"
        if user_id:
            log_message += f" - User ID: {user_id}"
        
        # IP e User Agent
        try:
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent', 'Unknown')
            log_message += f" - IP: {ip_address} - UA: {user_agent}"
        except:
            pass
        
        # Log con il livello appropriato
        if self.logger:
            log_method = getattr(self.logger, severity, self.logger.warning)
            log_method(log_message)
        
        # Salva anche nel database (AuditLog)
        try:
            if current_app:
                with current_app.app_context():
                    audit = AuditLog(
                        user_id=user_id,
                        action=event_type,
                        entity_type='SecurityEvent',
                        entity_id=None,
                        details=f"{description}. {details or ''}",
                        ip_address=request.remote_addr if request else None,
                        created_at=datetime.now(timezone.utc)
                    )
                    db.session.add(audit)
                    db.session.commit()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save security event to database: {e}")
    
    def log_failed_login(self, identifier, reason='Invalid credentials'):
        """Log tentativo di login fallito"""
        self.log_event(
            'FAILED_LOGIN_ATTEMPT',
            f"Identifier: {identifier}, Reason: {reason}",
            severity='warning'
        )
    
    def log_suspicious_upload(self, filename, mime_type, reason):
        """Log tentativo di upload sospetto"""
        self.log_event(
            'SUSPICIOUS_FILE_UPLOAD',
            f"File: {filename}, MIME: {mime_type}, Reason: {reason}",
            severity='error'
        )
    
    def log_csrf_violation(self, endpoint):
        """Log violazione CSRF"""
        self.log_event(
            'CSRF_TOKEN_INVALID',
            f"Endpoint: {endpoint}",
            severity='error'
        )
    
    def log_unauthorized_access(self, endpoint, user_id=None):
        """Log tentativo di accesso non autorizzato"""
        self.log_event(
            'UNAUTHORIZED_ACCESS',
            f"Endpoint: {endpoint}",
            user_id=user_id,
            severity='warning'
        )
    
    def log_super_admin_login(self, user_id, username, email):
        """
        Log accesso del super admin.
        IP address e user agent sono catturati automaticamente da log_event().
        """
        self.log_event(
            'SUPER_ADMIN_LOGIN',
            f"Username: {username}, Email: {email}",
            user_id=user_id,
            severity='info'
        )

# Istanza globale
security_logger = SecurityEventLogger()
