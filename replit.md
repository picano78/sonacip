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

The application's structure is modular, with dedicated packages for core functionalities such as authentication, administration, event management, social networking, messaging, notifications, CRM, advertising, analytics, marketplace, and subscription management. Database migrations are managed with Alembic.

Key architectural features include:
- **UI/UX:** Redesigned navigation as a responsive sidebar with icons and tooltips. The Planner features Google Calendar-style day, week, and month views with clickable cells for event creation. User profiles are designed in a LinkedIn-style format, including sections for Career, Education, and Skills, and a connection system for social networking. The messaging system is a chat-like interface with a Facebook-blue theme, emoji picker, and search. A comprehensive homepage, user guides, legal pages (Privacy Policy, Terms of Service), and an "About" page have been professionally redesigned.
- **Technical Implementations:**
    - **Database:** Defaults to SQLite, with PostgreSQL support via `DATABASE_URL`.
    - **Security:** Flask-Login for authentication, bcrypt for password hashing, and mandatory email confirmation for new registrations with configurable settings.
    - **Customization:** A graphical Sidebar Menu Order admin page allows drag-and-drop reordering and visibility toggles for menu items. A Page Builder system enables super administrators to configure core pages (Homepage, About, Contact, Legal, Guides) using a variety of section types, with content stored in `CustomizationKV`.
    - **CRM:** Rewritten from a sales CRM to focus on sports society member management, including user search, role assignment (athlete, coach, staff, director, enthusiast), member detail pages with certificates, fees, event convocations, and automated expiry reminders for certificates and fees.
    - **Marketplace:** A Facebook Marketplace-style system for user sale ads, featuring listing creation, categories, conditions, multi-image upload, promotion/boost options, and Stripe integration for payments.
    - **Communication:** A super admin newsletter system for broadcasting messages to users filtered by role, and a society broadcast system for society admins to message their members. An internal messaging system replaces external services. A Super Admin Chat Monitor panel allows viewing and managing user conversations.
    - **Backup System:** Enhanced with a graphical UI, file upload/restore capabilities, and hourly scheduling.
    - **Feature Control:** A `PlatformFeature` model allows super administrators to toggle 24 site features on/off, distinguishing between premium and free functionalities.

## Recent Changes (Feb 6, 2026)
- **Gamification System:** Full gamification module with points, badges (12 default badges), 10-level progression system, login streak tracking, leaderboard, and admin badge management. Engine in `app/gamification/engine.py`, routes in `app/gamification/routes.py`, templates in `app/templates/gamification/`.
- **Customizable Dashboards:** Dashboard widget system with 12 widget types (feed preview, upcoming events, tasks, notifications, stats, mini calendar, groups, polls, documents, leaderboard mini, weather, quick links). Drag-and-drop customization interface with save/reset. Widget module in `app/main/dashboard_widgets.py`, customize template in `app/templates/main/dashboard_customize.html`, widget partials in `app/templates/widgets/`.
- **Login Streak Integration:** Auth login flow automatically updates user login streak for gamification engagement.
- **Sidebar Navigation:** Gamification link added to sidebar navigation in both menu configurations.

## External Dependencies
- **Database:** SQLite (default), PostgreSQL (optional)
- **Payment Processing:** Stripe
- **Authentication:** Authlib (for OAuth)
- **Email:** SMTP (for email confirmation and broadcast messages)