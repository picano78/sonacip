# SONACIP - Sports Society Management Platform

## Overview
SONACIP is a comprehensive Italian-language platform for managing sports societies, athletes, and enthusiasts. It provides features for user management, events, social networking, messaging, and more.

## Project Architecture

### Tech Stack
- **Backend**: Python 3.11, Flask 3.0.0
- **Database**: SQLite (default), PostgreSQL (optional via DATABASE_URL)
- **ORM**: SQLAlchemy 2.0 with Flask-SQLAlchemy and Flask-Migrate
- **Authentication**: Flask-Login with bcrypt password hashing
- **Forms**: Flask-WTF with WTForms
- **Rate Limiting**: Flask-Limiter
- **OAuth**: Authlib
- **Payments**: Stripe integration ready

### Directory Structure
```
/
├── app/                    # Main application package
│   ├── __init__.py        # App factory and extensions
│   ├── models.py          # SQLAlchemy models
│   ├── core/              # Core configuration and bootstrap
│   ├── auth/              # Authentication routes and forms
│   ├── admin/             # Admin panel
│   ├── main/              # Main routes
│   ├── events/            # Event management
│   ├── social/            # Social networking features
│   ├── messages/          # Messaging system
│   ├── notifications/     # Notification system
│   ├── crm/               # CRM functionality
│   ├── ads/               # Advertisement management
│   ├── analytics/         # Analytics dashboard
│   ├── backup/            # Backup utilities
│   ├── marketplace/       # Marketplace features
│   ├── scheduler/         # Task scheduling
│   ├── subscription/      # Subscription management
│   └── tournaments/       # Tournament management
├── migrations/            # Alembic database migrations
├── uploads/               # User uploaded files
├── backups/               # Database backups
├── logs/                  # Application logs
├── run.py                 # Application entry point
├── config.py              # Configuration shim
└── requirements.txt       # Python dependencies
```

### Key Configuration
- Application runs on port 5000
- Database defaults to SQLite (sonacip.db) unless DATABASE_URL is set
- SECRET_KEY auto-generated and persisted if not provided
- Session lifetime: 7 days
- Max upload size: 16MB

### Running the Application
- Development: `python -c "from run import app; app.run(host='0.0.0.0', port=5000, debug=False)"`
- Production: `gunicorn --bind=0.0.0.0:5000 --reuse-port --workers=2 run:app`

## Recent Changes
- 2026-02-05: Initial import and Replit environment setup
- 2026-02-05: Fixed navbar "Planner" visibility - added to database config and template
- 2026-02-05: Implemented Planner calendar views (day, week, month) with Google Calendar style
- 2026-02-05: Redesigned navigation as sidebar with icons and tooltips (responsive for PC/tablet/mobile)
- 2026-02-05: Added clickable calendar cells to create events directly from the Planner grid
- 2026-02-05: Fixed AuditLog constructor usage in utils.py
- 2026-02-05: Renamed duplicate function names in __init__.py
- 2026-02-05: Added clickable avatar for profile image upload
- 2026-02-05: Redesigned messaging system with WhatsApp-style chat interface
- 2026-02-05: Enhanced internal messaging with WhatsApp green theme, emoji picker, search, and read receipts
- 2026-02-05: Added language selection in profile edit page (Italian/English)
- 2026-02-05: Enhanced backup system with graphical UI, file upload/restore, hourly scheduling
- 2026-02-05: Implemented LinkedIn-style profiles with Career, Education, Skills sections
- 2026-02-05: Added Connection system (LinkedIn-style friend requests with accept/reject)
- 2026-02-05: Created Career model with title, company, location, employment type, dates, description
- 2026-02-05: Created Education model with school, degree, field of study, years
- 2026-02-05: Created Skill model with endorsements system
- 2026-02-05: Added profile sections: Experience, Education, Skills, Connections, Contact Info

## User Preferences
- Menu should be a sidebar overlay with icons (not dropdown)
- Icons should show descriptions on hover
- UI must be responsive for PC, tablet, and mobile
- Planner should allow clicking on calendar to add/edit events
- Profiles should be LinkedIn-style with career sections
- Friendships should work like LinkedIn connections (request/accept)
