"""
Security Routes
Gestisce endpoint di sicurezza come CSP reporting
"""

from flask import Blueprint, request, current_app
from app import csrf, limiter
import json

bp = Blueprint('security', __name__, url_prefix='/security')

@bp.route('/csp-report', methods=['POST'])
@csrf.exempt
@limiter.limit("100 per hour")
def csp_report():
    """
    Endpoint per ricevere report di violazioni CSP
    """
    try:
        # Try to get JSON, but also handle empty or malformed requests
        report = None
        try:
            report = request.get_json(force=True, silent=True)
        except:
            pass
        
        if report and 'csp-report' in report:
            csp_violation = report['csp-report']
            
            # Log della violazione
            current_app.logger.warning(
                f"CSP Violation: "
                f"blocked-uri={csp_violation.get('blocked-uri')}, "
                f"violated-directive={csp_violation.get('violated-directive')}, "
                f"document-uri={csp_violation.get('document-uri')}"
            )
            
            # Salva nel security logger se disponibile
            if hasattr(current_app, 'security_logger'):
                current_app.security_logger.log_event(
                    'CSP_VIOLATION',
                    f"Blocked URI: {csp_violation.get('blocked-uri')}, "
                    f"Directive: {csp_violation.get('violated-directive')}",
                    severity='warning'
                )
        
        # Always return 204 No Content to acknowledge receipt
        return '', 204
    
    except Exception as e:
        current_app.logger.error(f"CSP report error: {e}")
        # Still return 204 to prevent browser retries
        return '', 204
