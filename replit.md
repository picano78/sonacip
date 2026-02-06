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
- 2026-02-05: Redesigned messaging system "Messaggi" with chat interface
- 2026-02-05: Enhanced internal messaging with Facebook blue theme (#1877f2), emoji picker, search, and read receipts
- 2026-02-05: Added language selection in profile edit page (Italian/English)
- 2026-02-05: Enhanced backup system with graphical UI, file upload/restore, hourly scheduling
- 2026-02-05: Implemented LinkedIn-style profiles with Career, Education, Skills sections
- 2026-02-05: Added Connection system (LinkedIn-style friend requests with accept/reject)
- 2026-02-05: Created Career model with title, company, location, employment type, dates, description
- 2026-02-05: Created Education model with school, degree, field of study, years
- 2026-02-05: Created Skill model with endorsements system
- 2026-02-05: Added profile sections: Experience, Education, Skills, Connections, Contact Info
- 2026-02-05: Fixed VPS login error - auto-upgrade now works for all databases (SQLite + PostgreSQL)
- 2026-02-05: Created migration for LinkedIn profile tables (career, education, skill, connection, profile_section)
- 2026-02-05: Added db.create_all() fallback for safer deployments when migrations fail

- 2026-02-06: Added PlatformFeature model for super admin control of premium/free features
- 2026-02-06: Created graphical Feature Control panel with toggle switches for all 24 site features
- 2026-02-06: Added MarketplaceListing model for user sale ads (Facebook Marketplace style)
- 2026-02-06: Created full Marketplace with listing creation, detail, edit, search, categories, and my-listings
- 2026-02-06: Added prominent Marketplace button in Social feed sidebar with blue gradient card
- 2026-02-06: Marketplace features: 9 categories, 5 conditions, multi-image upload, lightbox, similar items
- 2026-02-06: Added Marketplace quick action button in Social feed sidebar
- 2026-02-06: Updated has_feature() to check PlatformFeature settings (free features bypass subscription)
- 2026-02-06: Added Feature Control section to admin dashboard with highlighted link
- 2026-02-06: Features organized by category: Social, Media, Business, Organizzazione, Comunicazione, Supporto, Sicurezza
- 2026-02-06: Added listing auto-expiration (60 days) with visual indicators and renew functionality
- 2026-02-06: Built Subito.it-style promotion/boost system with tiered pricing (7/14/30 days)
- 2026-02-06: Created PromotionTier model (configurable boost plans with name, slug, price, duration, icon, color)
- 2026-02-06: Created ListingPromotion model (tracks active promotions with Stripe payment integration)
- 2026-02-06: Created PlatformPaymentSetting model (super admin bank/Stripe/PayPal payout config)
- 2026-02-06: Admin Payment Settings page: bank details, IBAN, Stripe account, PayPal, payout frequency/currency
- 2026-02-06: Admin Promotion Tiers dashboard: create/edit/toggle/delete tiers with revenue statistics
- 2026-02-06: Marketplace listing cards show "IN EVIDENZA" gradient badge for promoted listings
- 2026-02-06: Listing detail page: promote button, promotion status, expiry date, renew option
- 2026-02-06: My Listings page: expired filter tab, promotion badges, "In Evidenza" and "Rinnova" buttons
- 2026-02-06: Stripe checkout integration for listing promotions with webhook-driven activation
- 2026-02-06: Default promotion tiers auto-seed: €2.99/7d, €4.99/14d, €7.99/30d
- 2026-02-06: Admin dashboard links to Payment Settings and Promotion Tiers in Payments & Business section
- 2026-02-06: Created BroadcastMessage model (newsletter/broadcast with scope_type, target_roles, send_email)
- 2026-02-06: Created BroadcastRecipient model (per-recipient tracking with delivery status, email sent flag)
- 2026-02-06: Super Admin Newsletter system: compose, send to all users filtered by role, delivery tracking
- 2026-02-06: Newsletter detail page with read/unread statistics, recipient list, email delivery status
- 2026-02-06: Society broadcast system: society admins can message all their members filtered by role
- 2026-02-06: Society broadcast roles filter: atleta, coach, staff, dirigente, appassionato
- 2026-02-06: Internal delivery via Message model + optional SMTP email delivery
- 2026-02-06: Message preview feature before sending
- 2026-02-06: Admin dashboard "Comunicazione" section with Newsletter link
- 2026-02-06: Society dashboard "Comunicazioni ai Membri" card with compose and history buttons
- 2026-02-06: Complete homepage redesign with professional hero, feature cards, stats, and CTA sections
- 2026-02-06: Created User Guide page (/guida-utente) with accordion sections and step-by-step instructions
- 2026-02-06: Created Society Guide page (/guida-societa) with admin tutorials and FAQ
- 2026-02-06: Created Contact Admin page (/contatta-admin) with form to message super admin internally
- 2026-02-06: Added ContactAdminForm with subject, category, message fields and validation
- 2026-02-06: Created GDPR-compliant Privacy Policy page (/privacy) with all required sections
- 2026-02-06: Created Terms of Service page (/termini) with comprehensive legal sections
- 2026-02-06: Cookie Policy redirect to privacy page with cookie section anchor
- 2026-02-06: Professional footer redesign with 4-column layout (Brand, Platform, Guides, Legal)
- 2026-02-06: About page redesign with values cards, mission, and statistics
- 2026-02-06: Contact page redesign with professional cards (email, phone, location) and CTA
- 2026-02-06: Added Assistenza and Guida links in sidebar for logged-in users
- 2026-02-06: Enhanced client-side UX: confirm dialogs, form submit protection, custom tooltips
- 2026-02-06: Fixed Centro Export error (Society.name → Society.legal_name)
- 2026-02-06: Added mandatory email confirmation system for new registrations
- 2026-02-06: User model: email_confirmed, email_confirm_token, email_confirm_sent_at fields
- 2026-02-06: EmailConfirmationSetting model for super admin toggle (enabled, token_expiry_hours, max_resends, email_subject)
- 2026-02-06: Email confirmation utility (app/auth/email_confirm.py): token generation, SMTP sending, resend logic, token verification
- 2026-02-06: Registration routes (individual + society) send confirmation email when feature enabled
- 2026-02-06: Login blocks unconfirmed users (super_admin always bypasses)
- 2026-02-06: Session-secured pending/resend pages (no user enumeration, masked email display)
- 2026-02-06: Beautiful confirmation pending page with resend button, rate limiting, max resends enforcement
- 2026-02-06: Admin panel: Conferma Email settings page with toggle, statistics, per-user/bulk confirm, settings customization
- 2026-02-06: Auto-confirm existing users when enabling feature (via auto_confirm_existing setting)
- 2026-02-06: Admin dashboard link: "Conferma Email" in Impostazioni Sistema section
- 2026-02-06: Removed all WhatsApp references from admin, social, notifications, templates, guides, seed data
- 2026-02-06: Messaging system is now fully standalone internal system (no external service branding)
- 2026-02-06: Created Super Admin Chat Monitor panel (/admin/chat-monitor) to view all user conversations
- 2026-02-06: Chat Monitor features: statistics dashboard, conversation list, message viewer, delete messages
- 2026-02-06: Added "Controllo Chat" link in admin dashboard Comunicazione section
- 2026-02-06: Redesigned Planner month view to match Google Calendar mobile style
- 2026-02-06: Month view: prev/next navigation, "Oggi" button, today circle highlight, colored event pills
- 2026-02-06: Month view: leading/trailing days from adjacent months shown in light gray
- 2026-02-06: Month view: floating action button (FAB) for quick event creation
- 2026-02-06: Month view: view switcher tabs (Giorno/Settimana/Mese) and facility filter

## User Preferences
- Menu should be a sidebar overlay with icons (not dropdown)
- Icons should show descriptions on hover
- UI must be responsive for PC, tablet, and mobile
- Planner should allow clicking on calendar to add/edit events
- Profiles should be LinkedIn-style with career sections
- Friendships should work like LinkedIn connections (request/accept)
