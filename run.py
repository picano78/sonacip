"""
Production-safe entry point
WARNING: Use gunicorn in production, not this script
"""
import os
from app import create_app

# Create app with environment-based config
app = create_app()

if __name__ == "__main__":
    # PRODUCTION SAFETY: Never allow debug mode via direct run
    # This script is for development only
    is_production = os.environ.get('APP_ENV') == 'production' or os.environ.get('FLASK_ENV') == 'production'
    if is_production:
        raise RuntimeError("Cannot run directly in production. Use gunicorn instead.")
    
    # Development mode only
    app.run(host="0.0.0.0", port=5000, debug=False)
