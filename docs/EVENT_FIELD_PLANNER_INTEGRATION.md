# Event Field Planner Integration

## Overview

This feature integrates the Event creation functionality with the Field Planner (Society Calendar), allowing automatic field/facility booking when creating training or match events.

## Features

### 1. Facility Selection
When creating an event, users can select a facility (campo/palestra) from their society's available facilities:
- Dropdown shows all facilities belonging to the user's society
- Only visible for training (`allenamento`) and match (`partita`) events

### 2. Conflict Detection
Before creating or editing an event with a facility:
- System checks for conflicts in both Event and SocietyCalendarEvent tables
- Displays clear error message if field is already occupied
- Shows the conflicting event title and time range

### 3. Color Customization
- Each event can have a custom color for calendar display
- Default colors are assigned based on event type:
  - Training: `#0dcaf0` (cyan)
  - Match: `#198754` (green)
  - Tournament: `#0d6efd` (blue)
  - Meeting: `#6f42c1` (purple)
  - Other: `#212529` (dark)
- Users can customize the color using a color picker

### 4. Automatic Calendar Integration
When a facility is selected for training or match events:
- A corresponding SocietyCalendarEvent is automatically created
- The calendar event is linked to the original Event via `event_id`
- Updates to the Event automatically sync to the calendar event

## Database Schema

### Event Table
- `facility_id` (Integer, FK to Facility): Selected facility/field
- `color` (String, 20): Color for calendar display

### SocietyCalendarEvent Table
- `event_id` (Integer, FK to Event): Link to the originating Event

## Usage

### Creating an Event with Field Booking

1. Navigate to Events → Create Event
2. Fill in basic event information (title, type, dates)
3. Select event type as "Allenamento" or "Partita"
4. The "Planner Campo" section will appear
5. Select a facility from the dropdown
6. Optionally customize the color
7. Click "Crea Evento"

If the field is available, the event will be created and automatically added to the field planner. If there's a conflict, an error message will display.

### Editing an Event

1. Navigate to the event detail page
2. Click "Modifica"
3. Change facility or other details
4. Click "Salva"

The system will check for conflicts with the new settings and sync changes to the calendar event if it exists.

## Technical Details

### Event Type Mapping

Since SocietyCalendarEvent doesn't have a dedicated "training" type, the mapping is:
- `allenamento` → `other`
- `partita` → `match`

### Conflict Detection Logic

Conflicts are detected when:
- Same facility_id
- Overlapping time ranges (start_date < end_date AND end_date > start_date)
- Event status is not 'cancelled'
- Excluding the event being edited and its linked calendar event

### Synchronization

When editing an Event with a linked SocietyCalendarEvent:
- Title, dates, color, location, and facility are synced
- If facility is added to an Event without a calendar event, one is created
- If facility is removed, the calendar event remains but loses the facility link

## Code Locations

- **Models**: `app/models.py` (Event and SocietyCalendarEvent classes)
- **Forms**: `app/events/forms.py` (EventForm)
- **Routes**: `app/events/routes.py` (create and edit routes)
- **Templates**: 
  - `app/templates/events/create.html`
  - `app/templates/events/edit.html`
  - `app/templates/events/detail.html`
- **Migration**: `migrations/versions/add_event_field_planner_integration.py`

## Future Enhancements

Potential improvements:
1. Add a dedicated "training" event type to SocietyCalendarEvent
2. Allow bulk facility booking for recurring training sessions
3. Display facility availability calendar when selecting dates
4. Send notifications to facility managers when bookings are made
5. Add facility capacity warnings
