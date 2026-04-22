# Society Visibility Controls & Enhanced Planner Notifications

## Overview

This implementation adds granular visibility controls for society members and a comprehensive notification system for planner and event changes. It enables societies to control what their authorized users can see and ensures all members are notified of important planner changes.

## Features Implemented

### 1. Society Membership Visibility Controls

#### New Fields in `SocietyMembership` Model

- **`can_see_all_events`** (Boolean): Controls whether a member can see all events in their society or only events they're convocated for
  - Default: `True` for dirigente, coach, staff
  - Default: `False` for athletes and appassionato
  
- **`can_manage_planner`** (Boolean): Grants permission to manage the field planner
  - Default: `True` for dirigente, coach
  - Default: `False` for other roles
  
- **`receive_planner_notifications`** (Boolean): Controls whether the member receives notifications for planner changes
  - Default: `True` for all roles
  - Users can disable this if they don't want planner notifications

#### Database Migration

A migration file has been created at `migrations/versions/add_society_visibility_controls.py` that:
- Adds the three new columns to the `society_membership` table
- Sets intelligent defaults based on existing role names
- Can be rolled back if needed

### 2. Enhanced Notification System

#### New Notification Functions

**`notify_planner_change(society_id, title, message, link=None)`**
- Sends notifications to all active society members who have `receive_planner_notifications=True`
- Used when events with facilities are created or modified
- Notification type: `'calendar'`

**`notify_event_change(event_id, title, message, include_creator=True)`**
- Sends notifications to all athletes convocated to an event
- Optionally includes the event creator
- Used when event details are updated
- Notification type: `'event'`

#### Notification Triggers

Notifications are automatically sent when:

1. **Event Created with Facility**
   - All society members with planner notifications enabled are notified
   - Includes facility name and event date/time
   
2. **Event Updated**
   - All convocated athletes are notified
   - Society members are notified if facility changed
   
3. **Calendar Event Created with Facility**
   - All society members with planner notifications enabled are notified
   - Includes facility name and event date/time

### 3. Visibility-Based Event Filtering

The event listing (`/events/`) now respects visibility controls:

**For Admins:**
- See all events (no restrictions)

**For Society Members with `can_see_all_events=True`:**
- See all events created by any member of their society
- See events they're convocated for

**For Other Members:**
- See only events they created
- See only events they're convocated for

### 4. Group Operations Dashboard

The society dashboard (`/social/society/dashboard`) now includes:

**Pending Planner Events Section:**
- Shows upcoming events in the next 7 days
- Displays event title, date/time, and facility
- Color-coded by event type
- Quick link to event details

**Pending Event Responses Section:**
- Shows events where the user needs to confirm/reject attendance
- Displays warning badge for pending confirmations
- Quick access to event details

**Group Operators Count:**
- Shows how many members have full visibility (`can_see_all_events=True`)
- Indicates the size of the "group operators" team

### 5. Enhanced UI/UX

**Notification Icons:**
- Calendar notifications: Orange gradient with `bi-calendar-week-fill` icon
- Event notifications: Green gradient with `bi-calendar-event-fill` icon
- Improved visual hierarchy with badges and colors

**Dashboard Cards:**
- Modern card-based layout
- Hover effects and smooth transitions
- Color-coded badges for different event types
- Responsive design for mobile devices

## Usage Guide

### For Society Administrators

1. **Setting Member Permissions:**
   - Navigate to society member management
   - Edit a member's profile
   - Toggle `can_see_all_events` to control event visibility
   - Toggle `can_manage_planner` to grant planner management rights

2. **Managing Notifications:**
   - Members can control their notification preferences
   - Disable `receive_planner_notifications` for members who don't need planner updates

3. **Creating Events with Planner Integration:**
   - Create an event via `/events/create`
   - Select event type: "Allenamento" or "Partita"
   - Choose a facility from the dropdown
   - All members with planner notifications enabled will be notified

### For Members

1. **Viewing Events:**
   - Staff/Coaches see all society events
   - Athletes see only events they're convocated for
   - Navigate to `/events/` to see filtered event list

2. **Dashboard Overview:**
   - Visit `/social/society/dashboard` for a complete overview
   - See upcoming planner events (next 7 days)
   - Check pending event responses
   - Quick access to all key actions

3. **Notifications:**
   - Receive calendar notifications when planner changes occur
   - Get notified when convocated to events
   - Get notified when event details change

## Technical Details

### Files Modified

1. **Models:**
   - `app/models.py`: Added fields to SocietyMembership

2. **Notifications:**
   - `app/notifications/utils.py`: Added notify_planner_change() and notify_event_change()

3. **Routes:**
   - `app/events/routes.py`: Integrated notifications and visibility filtering
   - `app/scheduler/routes.py`: Integrated planner notifications
   - `app/social/routes.py`: Enhanced dashboard with group operations

4. **Templates:**
   - `app/templates/social/society_dashboard.html`: Added group operations section
   - `app/templates/notifications/index.html`: Added calendar notification styling

5. **Migrations:**
   - `migrations/versions/add_society_visibility_controls.py`: Database schema update

### Database Schema Changes

```sql
ALTER TABLE society_membership 
ADD COLUMN can_see_all_events BOOLEAN DEFAULT FALSE;

ALTER TABLE society_membership 
ADD COLUMN can_manage_planner BOOLEAN DEFAULT FALSE;

ALTER TABLE society_membership 
ADD COLUMN receive_planner_notifications BOOLEAN DEFAULT TRUE;
```

### Performance Considerations

- Notification queries are optimized with filters on `status='active'` and `receive_planner_notifications=True`
- Event listing uses indexed queries with `creator_id` and society membership filters
- Dashboard queries are limited to relevant data (7 days for planner events, top 5 responses)

## Security

- All routes maintain existing permission checks
- Visibility controls add an additional layer of access control
- Notifications only sent to active society members
- No sensitive information exposed in notification messages

## Future Enhancements

Potential improvements for future versions:

1. **Notification Preferences Panel:**
   - Allow users to customize which types of notifications they receive
   - Granular control (e.g., only match notifications, not training)

2. **Email/SMS Integration:**
   - Send email notifications for critical planner changes
   - SMS alerts for last-minute event updates

3. **Calendar Sync:**
   - Export events to Google Calendar, Outlook, etc.
   - Automatic calendar updates when events change

4. **Advanced Filtering:**
   - Filter events by facility, team, date range
   - Save custom event views

5. **Notification Digest:**
   - Daily/weekly summary of planner changes
   - Configurable digest schedule

## Testing

Run the validation script to verify the implementation:

```bash
python /tmp/test_implementation.py
```

This validates:
- Model changes are correct
- Notification functions are defined
- Routes are integrated properly
- Dashboard enhancements are present
- UI improvements are implemented
- Migration is complete

## Migration Instructions

1. **Backup your database** before running migrations

2. **Run the migration:**
   ```bash
   flask db upgrade
   ```

3. **Verify the migration:**
   ```sql
   SELECT can_see_all_events, can_manage_planner, receive_planner_notifications 
   FROM society_membership 
   LIMIT 5;
   ```

4. **Rollback if needed:**
   ```bash
   flask db downgrade
   ```

## Support

For questions or issues:
- Check the validation script output
- Review the notification logs in `logs/sonacip.log`
- Verify database migration status with `flask db current`

## Changelog

**Version 1.0 (2026-02-13)**
- Initial implementation of visibility controls
- Added planner notification system
- Enhanced society dashboard with group operations
- Improved notification UI with calendar support
