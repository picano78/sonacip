"""
Rate Limiting Configuration for API endpoints
"""

# Rate limits per tipo di endpoint
RATE_LIMITS = {
    'authentication': "5 per minute",  # Login, register
    'api_write': "30 per minute",      # POST, PUT, DELETE API
    'api_read': "100 per minute",      # GET API
    'file_upload': "10 per minute",    # Upload file
    'sensitive': "3 per minute",       # Operazioni sensibili
}

def get_rate_limit(endpoint_type):
    """Ottieni il rate limit per un tipo di endpoint"""
    return RATE_LIMITS.get(endpoint_type, "60 per minute")
