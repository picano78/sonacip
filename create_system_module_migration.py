#!/usr/bin/env python3
"""Create migration for SystemModule model"""
from flask_migrate import migrate as mig_cmd
from app import create_app, db

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # Import models to ensure they're registered
        from app.models import SystemModule
        
        # Use Flask-Migrate's migrate function
        from flask_migrate import Migrate, migrate
        mig = Migrate(app, db, directory='migrations')
        migrate(directory='migrations', message='Add SystemModule model for modular updates')
