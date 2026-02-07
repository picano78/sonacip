# SONACIP - Sports Society Management Platform

## Overview
SONACIP is a comprehensive Italian-language platform designed for the management of sports societies, athletes, and enthusiasts. Its primary purpose is to streamline operations for sports organizations by offering robust features for user and event management, fostering social interactions, enabling efficient communication, and supporting administrative tasks. The platform aims to be a central hub for sports communities, enhancing engagement and simplifying organizational workflows within the Italian sports landscape.

## User Preferences
- Menu should be a sidebar overlay with icons (not dropdown)
- Icons should show descriptions on hover
- UI must be responsive for PC, tablet, and mobile
- Planner should allow clicking on calendar to add/edit events
- Profiles should be LinkedIn-style with career sections
- Friendships should work like LinkedIn connections (request/accept)

## System Architecture
The SONACIP platform is built on a Python 3.11 Flask 3.0.0 backend, utilizing SQLAlchemy 2.0 with Flask-SQLAlchemy and Flask-Migrate for ORM and database management. Authentication is handled via Flask-Login with bcrypt for secure password hashing. User input is managed with Flask-WTF and WTForms, while Flask-Limiter provides rate limiting. OAuth functionality is integrated using Authlib, and Stripe is ready for payment processing.

The application's structure is modular, with dedicated packages for core functionalities. All modules are listed in `CORE_MODULES` in `app/__init__.py` and auto-registered via `_register_blueprints()`. Database migrations are managed with Alembic.

### Core Modules (Blueprints)
main, auth, admin, ads, crm, events, social, backup, notifications, analytics, messages, tournaments, tasks, scheduler, subscription, marketplace, groups, stories, polls, stats, payments, documents, gamification

### Key Architectural Features
- **UI/UX:** Responsive sidebar with icons and tooltips. Google Calendar-style planner. LinkedIn-style profiles with Career/Education/Skills. Facebook-blue (#1877f2) theme throughout. Chat-like messaging with emoji picker.
- **Database:** PostgreSQL via `DATABASE_URL` (Neon-backed Replit DB).
- **Security:** Flask-Login, bcrypt, mandatory email confirmation, rate limiting.
- **Customization:** Drag-and-drop sidebar menu ordering, Page Builder for core pages, content stored in `CustomizationKV`.
- **CRM:** Sports society member management with roles (athlete, coach, staff, director, enthusiast), certificates, fees, event convocations, expiry reminders.
- **Marketplace:** Facebook Marketplace-style listing system with Stripe payments.
- **Communication:** Newsletter system, society broadcasts, internal messaging, Super Admin Chat Monitor.
- **Backup System:** Graphical UI with file upload/restore and hourly scheduling.
- **Feature Control:** `PlatformFeature` model (34+ features) with super admin toggle, premium/free distinction.

## Recent Improvements (Feb 7, 2026)

### UI/UX Polish
- SVG favicon and PWA icons (trophy on #1877f2 background, all sizes: 16, 32, 180, 192, 512)
- Consistent Facebook-blue (#1877f2) theme across all CSS and templates (replaced Bootstrap default #0d6efd)
- Redesigned error pages (403, 404, 500) with animated gradient illustrations and action buttons
- Modernized auth pages: reset_password, reset_password_request, register_society now use card-based gradient design
- HTML autocomplete attributes on all auth form inputs for browser autofill support
- GDPR-style cookie banner (bottom bar with slide animation, replaces modal popup)
- Global page loading indicator (animated gradient bar at top)
- Error handlers in `app/__init__.py` now render proper templates with try/except fallback

## Recent Features (Feb 6, 2026)

### Groups & Community (`app/groups/`)
- Group CRUD with cover images, descriptions, privacy settings
- Group feed with posts, group chat, member management
- Join/leave groups, admin role management
- Templates in `app/templates/groups/`

### Stories/Status (`app/stories/`)
- Image/text story upload with 24-hour auto-expiry
- Story feed viewer with viewer tracking
- Templates in `app/templates/stories/`

### Polls & Voting (`app/polls/`)
- Poll creation with multiple options, voting, results display
- Anonymous/public voting modes, expiration dates
- Templates in `app/templates/polls/`

### Advanced Sports Statistics (`app/stats/`)
- Athlete stats tracking with stat templates
- Match statistics recording, progress visualization
- Templates in `app/templates/stats/`

### Online Payments (`app/payments/`)
- Stripe-based fee payment with checkout sessions
- Payment receipts, admin dashboard for payment tracking
- Uses existing Stripe integration (STRIPE_SECRET_KEY)
- Templates in `app/templates/payments/`

### Document Management (`app/documents/`)
- File upload/download with folder organization
- Access control, document sharing within societies
- Uploads stored in `uploads/documents/`
- Templates in `app/templates/documents/`

### Multi-language (`app/translations.py`)
- Lightweight JSON translation system with `t()` function
- 5 languages: Italian (default), English, Spanish, French, German
- Language switcher in footer of base template
- Context processor injects `t`, `current_language`, `supported_languages`

### Customizable Dashboards (`app/main/dashboard_widgets.py`)
- 12 widget types: feed_preview, upcoming_events, my_tasks, notifications, stats_summary, calendar_mini, my_groups, polls_active, documents_recent, leaderboard_mini, weather, quick_links
- Drag-and-drop customization at `/dashboard/customize`
- User layout preferences saved in `UserDashboardLayout`
- Widget partials in `app/templates/widgets/`

### Gamification (`app/gamification/`)
- Badge system with 12 default badges across social/sport/engagement categories
- Points system with 10-level progression
- Login streak tracking (integrated into auth login flow)
- Leaderboard with rankings
- Engine in `app/gamification/engine.py`, routes in `app/gamification/routes.py`

### Push Notifications
- Service worker push handler in `app/static/sw.js`
- Push subscription endpoints (POST subscribe/unsubscribe)
- `app/notifications/push_utils.py` with `send_push_notification()`
- Client library `app/static/js/push.js` loaded globally in base.html

### PWA Enhancements
- Enhanced `manifest.json` with shortcuts, categories, screenshots
- Improved service worker with cache-first strategy and offline fallback
- Push event handling in service worker

## Database Models (Key New Models)
- `PushSubscription` - Browser push notification subscriptions
- `Group`, `GroupMembership`, `GroupMessage` - Community groups
- `Story`, `StoryView` - Temporary stories/status updates
- `Poll`, `PollOption`, `PollVote` - Polls and voting
- `AthleteStat`, `StatTemplate` - Sports statistics
- `Document`, `DocumentFolder` - Document management
- `Badge`, `UserBadge`, `UserPoints` - Gamification
- `DashboardWidget`, `UserDashboardLayout` - Dashboard widgets
- `FeePayment` - Online fee payments

## External Dependencies
- **Database:** PostgreSQL (Neon-backed via Replit)
- **Payment Processing:** Stripe
- **Authentication:** Authlib (for OAuth)
- **Email:** SMTP (for email confirmation and broadcast messages)
- **Push Notifications:** pywebpush (optional, graceful degradation)
