"""Routes for Society Calendar (strategic, society-wide)"""
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from app import db
from app.scheduler.forms import SocietyCalendarEventForm, FacilityForm
from app.models import (
    SocietyCalendarEvent,
    society_calendar_event_staff,
    society_calendar_event_athletes,
    User,
    Notification,
    Post,
    Facility,
    SocietyCalendarAttendance,
    FieldPlannerEvent,
)
from app.utils import permission_required, check_permission, get_active_society_id
from app.utils.audit import log_planner_change
from app.notifications.utils import notify_planner_change

bp = Blueprint('calendar', __name__, url_prefix='/scheduler')

def _scope_id():
    return get_active_society_id(current_user)

def _event_scope_id(event_id: int):
    ev = SocietyCalendarEvent.query.get(event_id)
    return ev.society_id if ev else None


def _date_range(view_mode: str, start_date: datetime.date):
    if view_mode == 'day':
        end_date = start_date + timedelta(days=1)
    elif view_mode == 'month':
        end_date = start_date + timedelta(days=31)
    else:
        end_date = start_date + timedelta(days=7)
    return start_date, end_date


def _base_query_for_user():
    q = SocietyCalendarEvent.query
    sid = get_active_society_id(current_user)
    if check_permission(current_user, 'admin', 'access'):
        # Admin sees all unless an active society scope is selected.
        return q.filter(SocietyCalendarEvent.society_id == sid) if sid else q
    if not sid:
        return q.filter(False)
    return q.filter(SocietyCalendarEvent.society_id == sid)


@bp.route('/calendar')
@login_required
@permission_required('calendar', 'view', society_id_func=lambda: _scope_id())
def index():
    view = request.args.get('view', 'week')
    try:
        start_str = request.args.get('start')
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else datetime.now(timezone.utc).date()
    except ValueError:
        start_date = datetime.now(timezone.utc).date()

    start_date, end_date = _date_range(view, start_date)

    query = _base_query_for_user()

    # Date filtering (overlapping window)
    query = query.filter(
        SocietyCalendarEvent.start_datetime >= datetime.combine(start_date, datetime.min.time()),
        SocietyCalendarEvent.start_datetime < datetime.combine(end_date, datetime.min.time())
    )

    # Text filters
    team = request.args.get('team')
    category = request.args.get('category')
    competition = request.args.get('competition')
    if team:
        query = query.filter(SocietyCalendarEvent.team.ilike(f'%{team}%'))
    if category:
        query = query.filter(SocietyCalendarEvent.category.ilike(f'%{category}%'))
    if competition:
        query = query.filter(SocietyCalendarEvent.competition_name.ilike(f'%{competition}%'))

    events = query.order_by(SocietyCalendarEvent.start_datetime.asc()).all()

    # Also get field planner events for the same period and society
    sid = get_active_society_id(current_user)
    field_planner_events = []
    if sid or check_permission(current_user, 'admin', 'access'):
        fp_query = FieldPlannerEvent.query
        if sid:
            fp_query = fp_query.filter(FieldPlannerEvent.society_id == sid)
        fp_query = fp_query.filter(
            FieldPlannerEvent.start_datetime >= datetime.combine(start_date, datetime.min.time()),
            FieldPlannerEvent.start_datetime < datetime.combine(end_date, datetime.min.time())
        )
        field_planner_events = fp_query.order_by(FieldPlannerEvent.start_datetime.asc()).all()

    # Group events by date for the view
    grouped = {}
    for ev in events:
        key = ev.start_datetime.date()
        grouped.setdefault(key, []).append(ev)
    
    # Add field planner events to grouped dict with a marker
    for ev in field_planner_events:
        key = ev.start_datetime.date()
        grouped.setdefault(key, []).append(ev)

    return render_template(
        'calendar/index.html',
        events_by_date=grouped,
        view=view,
        start_date=start_date,
        end_date=end_date,
        filters={'team': team or '', 'category': category or '', 'competition': competition or ''}
    )

@bp.route('/calendar-grid')
@login_required
@permission_required('calendar', 'view', society_id_func=lambda: _scope_id())
def grid():
    """Google-Calendar-like grid view (day/week) with facility occupancy."""
    view = request.args.get('view', 'week')
    try:
        start_str = request.args.get('start')
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else datetime.now(timezone.utc).date()
    except ValueError:
        start_date = datetime.now(timezone.utc).date()

    if view not in ('day', 'week', 'month'):
        view = 'week'

    # Normalize start_date based on view
    if view == 'week':
        start_date = start_date - timedelta(days=start_date.weekday())
        end_date = start_date + timedelta(days=7)
    elif view == 'month':
        start_date = start_date.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
    else:
        end_date = start_date + timedelta(days=1)

    sid = get_active_society_id(current_user)
    if not sid and not check_permission(current_user, 'admin', 'access'):
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('calendar.index'))

    facility_id = request.args.get('facility_id', type=int)
    facilities = []
    if sid:
        facilities = Facility.query.filter_by(society_id=sid).order_by(Facility.name.asc()).all()

    q = _base_query_for_user()
    q = q.filter(
        SocietyCalendarEvent.start_datetime < datetime.combine(end_date, datetime.min.time()),
        SocietyCalendarEvent.end_datetime > datetime.combine(start_date, datetime.min.time()),
    )
    if facility_id:
        q = q.filter(SocietyCalendarEvent.facility_id == facility_id)

    events = q.order_by(SocietyCalendarEvent.start_datetime.asc()).all()

    # Also get field planner events for the same period
    field_planner_events = []
    if sid or check_permission(current_user, 'admin', 'access'):
        fp_query = FieldPlannerEvent.query
        if sid:
            fp_query = fp_query.filter(FieldPlannerEvent.society_id == sid)
        fp_query = fp_query.filter(
            FieldPlannerEvent.start_datetime < datetime.combine(end_date, datetime.min.time()),
            FieldPlannerEvent.end_datetime > datetime.combine(start_date, datetime.min.time()),
        )
        if facility_id:
            fp_query = fp_query.filter(FieldPlannerEvent.facility_id == facility_id)
        field_planner_events = fp_query.order_by(FieldPlannerEvent.start_datetime.asc()).all()

    days = []
    d = start_date
    while d < end_date:
        days.append(d)
        d = d + timedelta(days=1)

    hours = list(range(6, 23))  # 06:00-22:00

    # Map: day -> hour -> list[events]
    grid_map = {(day, hour): [] for day in days for hour in hours}
    for ev in events:
        day = ev.start_datetime.date()
        if day < start_date or day >= end_date:
            continue
        h = ev.start_datetime.hour
        if h < hours[0]:
            h = hours[0]
        if h > hours[-1]:
            h = hours[-1]
        grid_map[(day, h)].append(ev)
    
    # Add field planner events to grid
    for ev in field_planner_events:
        day = ev.start_datetime.date()
        if day < start_date or day >= end_date:
            continue
        h = ev.start_datetime.hour
        if h < hours[0]:
            h = hours[0]
        if h > hours[-1]:
            h = hours[-1]
        grid_map[(day, h)].append(ev)

    month_names_it = ['', 'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
                       'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
    prev_month = (start_date.replace(day=1) - timedelta(days=1)).replace(day=1) if view == 'month' else None
    next_month = end_date if view == 'month' else None
    today = datetime.now(timezone.utc).date()

    leading_days = []
    trailing_days = []
    if view == 'month' and days:
        first_weekday = days[0].weekday()
        for i in range(first_weekday, 0, -1):
            leading_days.append((days[0] - timedelta(days=i)).day)
        last_weekday = days[-1].weekday()
        for i in range(1, 7 - last_weekday):
            trailing_days.append(i)

    if view == 'day':
        prev_nav = start_date - timedelta(days=1)
        next_nav = start_date + timedelta(days=1)
        nav_title = start_date.strftime('%A %d')
        nav_subtitle = '{} {}'.format(month_names_it[start_date.month], start_date.year)
    elif view == 'week':
        prev_nav = start_date - timedelta(days=7)
        next_nav = start_date + timedelta(days=7)
        week_end = start_date + timedelta(days=6)
        nav_title = '{} - {}'.format(start_date.strftime('%d/%m'), week_end.strftime('%d/%m'))
        nav_subtitle = str(start_date.year)
    else:
        prev_nav = prev_month
        next_nav = next_month
        nav_title = month_names_it[start_date.month] if view == 'month' else ''
        nav_subtitle = str(start_date.year) if view == 'month' else ''

    return render_template(
        'calendar/grid.html',
        view=view,
        start_date=start_date,
        end_date=end_date,
        days=days,
        hours=hours,
        facilities=facilities,
        facility_id=facility_id,
        grid_map=grid_map,
        month_name=month_names_it[start_date.month] if view == 'month' else '',
        month_year=start_date.year if view == 'month' else '',
        prev_month=prev_month,
        next_month=next_month,
        prev_nav=prev_nav,
        next_nav=next_nav,
        nav_title=nav_title,
        nav_subtitle=nav_subtitle,
        today=today,
        leading_days=leading_days,
        trailing_days=trailing_days,
    )


@bp.route('/occupancy')
@login_required
@permission_required('calendar', 'view', society_id_func=lambda: _scope_id())
def occupancy():
    """Facility occupancy report (booked hours per resource)."""
    try:
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else datetime.now(timezone.utc).date()
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else (start_date + timedelta(days=7))
    except ValueError:
        start_date = datetime.now(timezone.utc).date()
        end_date = start_date + timedelta(days=7)

    if end_date <= start_date:
        end_date = start_date + timedelta(days=1)

    society = current_user.get_primary_society()
    if not society and not check_permission(current_user, 'admin', 'access'):
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('calendar.index'))

    facilities = Facility.query.filter_by(society_id=society.id).order_by(Facility.name.asc()).all() if society else []
    range_start = datetime.combine(start_date, datetime.min.time())
    range_end = datetime.combine(end_date, datetime.min.time())

    q = _base_query_for_user().filter(
        SocietyCalendarEvent.facility_id.isnot(None),
        SocietyCalendarEvent.start_datetime < range_end,
        SocietyCalendarEvent.end_datetime > range_start,
    )
    events = q.all()

    # Sum booked seconds per facility
    totals = {f.id: 0 for f in facilities}
    for ev in events:
        if not ev.facility_id:
            continue
        s = max(ev.start_datetime, range_start)
        e = min(ev.end_datetime, range_end)
        if e > s:
            totals[ev.facility_id] = totals.get(ev.facility_id, 0) + int((e - s).total_seconds())

    rows = []
    for f in facilities:
        secs = totals.get(f.id, 0)
        rows.append({'facility': f, 'hours': round(secs / 3600.0, 2)})
    rows.sort(key=lambda r: r['hours'], reverse=True)

    return render_template(
        'calendar/occupancy.html',
        start_date=start_date,
        end_date=end_date,
        rows=rows,
    )


@bp.route('/calendar/<int:event_id>')
@login_required
@permission_required('calendar', 'view', society_id_func=_event_scope_id)
def detail(event_id):
    event = SocietyCalendarEvent.query.get_or_404(event_id)
    if not event.is_visible_to(current_user):
        abort(403)
    # RSVP statuses for athletes
    attendance = SocietyCalendarAttendance.query.filter_by(event_id=event.id).all()
    attendance_map = {a.user_id: a.status for a in attendance}
    my_status = attendance_map.get(current_user.id)
    return render_template('calendar/detail.html', event=event, attendance_map=attendance_map, my_status=my_status)


@bp.route('/calendar/new', methods=['GET', 'POST'])
@login_required
@permission_required('calendar', 'manage', society_id_func=lambda: _scope_id())
def create():
    form = SocietyCalendarEventForm(current_user=current_user)
    scope = current_user.get_primary_society()
    scope_id = scope.id if scope else None

    # Pre-fill date/time from URL params (when clicking on calendar grid)
    if request.method == 'GET':
        date_param = request.args.get('date')
        hour_param = request.args.get('hour')
        if date_param:
            try:
                prefill_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                form.start_date.data = prefill_date
                form.end_date.data = prefill_date
            except ValueError:
                pass
        if hour_param:
            try:
                prefill_hour = int(hour_param)
                from datetime import time as dt_time
                form.start_time.data = dt_time(prefill_hour, 0)
                form.end_time.data = dt_time(min(prefill_hour + 1, 23), 0)
            except (ValueError, TypeError):
                pass

    if form.validate_on_submit():
        if scope_id and not check_permission(current_user, 'admin', 'access') and form.society_id.data != scope_id:
            flash('Non puoi creare eventi per una società diversa.', 'danger')
            return redirect(url_for('calendar.index'))

        start_dt = datetime.combine(form.start_date.data, form.start_time.data)
        end_dt = None
        if form.end_date.data and form.end_time.data:
            end_dt = datetime.combine(form.end_date.data, form.end_time.data)
        if not end_dt:
            end_dt = start_dt + timedelta(hours=2)

        facility_id = form.facility_id.data if form.facility_id.data and form.facility_id.data != -1 else None
        if facility_id:
            # Verify facility belongs to this society
            facility = Facility.query.filter_by(id=facility_id, society_id=form.society_id.data).first()
            if not facility:
                flash('Risorsa/palestra non valida per questa società.', 'danger')
                return redirect(url_for('calendar.create'))

            # Conflict detection: same facility overlapping time range
            conflict = (
                SocietyCalendarEvent.query.filter(
                    SocietyCalendarEvent.society_id == form.society_id.data,
                    SocietyCalendarEvent.facility_id == facility_id,
                    SocietyCalendarEvent.start_datetime < end_dt,
                    SocietyCalendarEvent.end_datetime > start_dt,
                )
                .order_by(SocietyCalendarEvent.start_datetime.asc())
                .first()
            )
            if conflict:
                flash(
                    f'Conflitto: la risorsa è già occupata da "{conflict.title}" '
                    f'({conflict.start_datetime.strftime("%d/%m %H:%M")} - {conflict.end_datetime.strftime("%H:%M")}).',
                    'danger',
                )
                return redirect(url_for('calendar.create'))

        event = SocietyCalendarEvent(
            society_id=form.society_id.data,
            created_by=current_user.id,
            facility_id=facility_id,
            title=form.title.data,
            team=form.team.data,
            category=form.category.data,
            event_type=form.event_type.data,
            competition_name=form.competition_name.data,
            start_datetime=start_dt,
            end_datetime=end_dt,
            color=(form.color.data or '').strip() or '#212529',
            location_text=form.location_text.data,
            notes=form.notes.data,
            share_to_social=form.share_to_social.data
        )
        db.session.add(event)
        db.session.flush()

        # Attach staff
        if form.staff_ids.data:
            staff_members = User.query.filter(User.id.in_(form.staff_ids.data)).all()
            for member in staff_members:
                event.staff_members.append(member)

        # Attach athletes
        if form.athlete_ids.data:
            athletes = User.query.filter(User.id.in_(form.athlete_ids.data)).all()
            for athlete in athletes:
                event.athletes.append(athlete)

        db.session.commit()

        # Create RSVP rows for athletes
        try:
            for athlete in event.athletes.all():
                if not SocietyCalendarAttendance.query.filter_by(event_id=event.id, user_id=athlete.id).first():
                    db.session.add(SocietyCalendarAttendance(event_id=event.id, user_id=athlete.id, status='pending'))
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Notify staff and athletes linked to the event
        try:
            recipients = event.staff_members.all() + event.athletes.all()
            for recipient in recipients:
                notification = Notification(
                    user_id=recipient.id,
                    title='Nuovo evento calendario società',
                    message=f'{event.title} - {event.start_datetime.strftime("%d/%m/%Y %H:%M")}',
                    notification_type='calendar',
                    link=url_for('calendar.detail', event_id=event.id)
                )
                db.session.add(notification)
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Direct social post for each athlete (so they see it in their feed)
        try:
            for athlete in event.athletes.all():
                db.session.add(
                    Post(
                        user_id=current_user.id,
                        content=f'Convocazione: {event.title} ({event.start_datetime.strftime("%d/%m/%Y %H:%M")}). Conferma disponibilità.',
                        is_public=False,
                        audience='direct',
                        society_id=event.society_id,
                        target_user_id=athlete.id,
                        post_type='calendar_invite',
                    )
                )
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Optional social post
        if event.share_to_social:
            try:
                post = Post(
                    user_id=current_user.id,
                    content=f'Nuovo evento in calendario: {event.title} ({event.start_datetime.strftime("%d/%m/%Y")})',
                    is_public=True,
                    audience='society',
                    society_id=event.society_id,
                    post_type='calendar'
                )
                db.session.add(post)
                db.session.commit()
            except Exception:
                db.session.rollback()
        
        # Notify all society members about planner change if facility is used
        if facility_id:
            facility_name = event.facility.name if event.facility else "risorsa"
            notify_planner_change(
                event.society_id,
                f"Nuovo evento sul planner: {event.title}",
                f"È stato creato un nuovo evento '{event.title}' sul {facility_name} per il {event.start_datetime.strftime('%d/%m/%Y')} alle {event.start_datetime.strftime('%H:%M')}.",
                link=url_for('calendar.detail', event_id=event.id)
            )
        
        # Log the creation
        log_planner_change(
            user_id=current_user.id,
            society_id=event.society_id,
            action='calendar_event_created',
            entity_type='SocietyCalendarEvent',
            entity_id=event.id,
            details={
                'title': event.title,
                'facility_id': facility_id,
                'event_type': event.event_type,
                'start_datetime': event.start_datetime.strftime('%Y-%m-%d %H:%M'),
                'end_datetime': event.end_datetime.strftime('%Y-%m-%d %H:%M') if event.end_datetime else None
            }
        )
        
        flash('Evento inserito nel Calendario Società.', 'success')
        return redirect(url_for('calendar.index'))

    return render_template('calendar/create.html', form=form)


@bp.route('/calendar/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('calendar', 'manage', society_id_func=_event_scope_id)
def edit(event_id):
    """Edit society calendar event"""
    event = SocietyCalendarEvent.query.get_or_404(event_id)
    
    scope = current_user.get_primary_society()
    scope_id = scope.id if scope else None
    
    # Check permissions
    if not check_permission(current_user, 'admin', 'access'):
        if event.society_id != get_active_society_id(current_user):
            abort(403)
    
    form = SocietyCalendarEventForm(current_user=current_user, obj=event)
    
    if form.validate_on_submit():
        # Store old values for logging
        old_values = {
            'title': event.title,
            'facility_id': event.facility_id,
            'start_datetime': event.start_datetime,
            'end_datetime': event.end_datetime
        }
        
        if scope_id and not check_permission(current_user, 'admin', 'access') and form.society_id.data != scope_id:
            flash('Non puoi modificare eventi per una società diversa.', 'danger')
            return redirect(url_for('calendar.detail', event_id=event.id))
        
        start_dt = datetime.combine(form.start_date.data, form.start_time.data)
        end_dt = None
        if form.end_date.data and form.end_time.data:
            end_dt = datetime.combine(form.end_date.data, form.end_time.data)
        if not end_dt:
            end_dt = start_dt + timedelta(hours=2)
        
        facility_id = form.facility_id.data if form.facility_id.data and form.facility_id.data != -1 else None
        if facility_id:
            # Verify facility belongs to this society
            facility = Facility.query.filter_by(id=facility_id, society_id=form.society_id.data).first()
            if not facility:
                flash('Risorsa/palestra non valida per questa società.', 'danger')
                return render_template('calendar/edit.html', form=form, event=event)
            
            # Conflict detection: same facility overlapping time range (excluding current event)
            conflict = (
                SocietyCalendarEvent.query.filter(
                    SocietyCalendarEvent.id != event.id,
                    SocietyCalendarEvent.society_id == form.society_id.data,
                    SocietyCalendarEvent.facility_id == facility_id,
                    SocietyCalendarEvent.start_datetime < end_dt,
                    SocietyCalendarEvent.end_datetime > start_dt,
                )
                .order_by(SocietyCalendarEvent.start_datetime.asc())
                .first()
            )
            if conflict:
                flash(
                    f'Conflitto: la risorsa è già occupata da "{conflict.title}" '
                    f'({conflict.start_datetime.strftime("%d/%m %H:%M")} - {conflict.end_datetime.strftime("%H:%M")}).',
                    'danger',
                )
                return render_template('calendar/edit.html', form=form, event=event)
        
        # Update event fields
        event.society_id = form.society_id.data
        event.facility_id = facility_id
        event.title = form.title.data
        event.team = form.team.data
        event.category = form.category.data
        event.event_type = form.event_type.data
        event.competition_name = form.competition_name.data
        event.start_datetime = start_dt
        event.end_datetime = end_dt
        event.color = (form.color.data or '').strip() or '#212529'
        event.location_text = form.location_text.data
        event.notes = form.notes.data
        event.share_to_social = form.share_to_social.data
        
        # Update staff associations
        event.staff_members.clear()
        if form.staff_ids.data:
            staff_members = User.query.filter(User.id.in_(form.staff_ids.data)).all()
            for member in staff_members:
                event.staff_members.append(member)
        
        # Update athlete associations
        event.athletes.clear()
        if form.athlete_ids.data:
            athletes = User.query.filter(User.id.in_(form.athlete_ids.data)).all()
            for athlete in athletes:
                event.athletes.append(athlete)
        
        db.session.commit()
        
        # Update RSVP rows for athletes (add new ones, keep existing)
        try:
            for athlete in event.athletes.all():
                if not SocietyCalendarAttendance.query.filter_by(event_id=event.id, user_id=athlete.id).first():
                    db.session.add(SocietyCalendarAttendance(event_id=event.id, user_id=athlete.id, status='pending'))
            db.session.commit()
        except Exception:
            db.session.rollback()
        
        # Notify staff and athletes linked to the event
        try:
            recipients = event.staff_members.all() + event.athletes.all()
            for recipient in recipients:
                notification = Notification(
                    user_id=recipient.id,
                    title='Evento calendario modificato',
                    message=f'{event.title} - {event.start_datetime.strftime("%d/%m/%Y %H:%M")}',
                    notification_type='calendar',
                    link=url_for('calendar.detail', event_id=event.id)
                )
                db.session.add(notification)
            db.session.commit()
        except Exception:
            db.session.rollback()
        
        # Notify all society members about planner change if facility is used
        if facility_id:
            facility_name = event.facility.name if event.facility else "risorsa"
            notify_planner_change(
                event.society_id,
                f"Evento modificato: {event.title}",
                f"L'evento '{event.title}' sul {facility_name} è stato modificato per il {event.start_datetime.strftime('%d/%m/%Y')} alle {event.start_datetime.strftime('%H:%M')}.",
                link=url_for('calendar.detail', event_id=event.id)
            )
        
        # Log the modification
        log_planner_change(
            user_id=current_user.id,
            society_id=event.society_id,
            action='calendar_event_updated',
            entity_type='SocietyCalendarEvent',
            entity_id=event.id,
            details={
                'old_values': old_values,
                'new_values': {
                    'title': event.title,
                    'facility_id': facility_id,
                    'start_datetime': event.start_datetime.strftime('%Y-%m-%d %H:%M'),
                    'end_datetime': event.end_datetime.strftime('%Y-%m-%d %H:%M') if event.end_datetime else None
                }
            }
        )
        
        flash('Evento aggiornato nel Calendario Società.', 'success')
        return redirect(url_for('calendar.detail', event_id=event.id))
    
    # Pre-fill form with existing event data
    if request.method == 'GET':
        form.society_id.data = event.society_id
        form.facility_id.data = event.facility_id if event.facility_id else -1
        form.title.data = event.title
        form.team.data = event.team
        form.category.data = event.category
        form.event_type.data = event.event_type
        form.competition_name.data = event.competition_name
        form.start_date.data = event.start_datetime.date()
        form.start_time.data = event.start_datetime.time()
        if event.end_datetime:
            form.end_date.data = event.end_datetime.date()
            form.end_time.data = event.end_datetime.time()
        form.color.data = event.color
        form.location_text.data = event.location_text
        form.notes.data = event.notes
        form.share_to_social.data = event.share_to_social
        
        # Pre-fill staff and athlete IDs
        form.staff_ids.data = [member.id for member in event.staff_members.all()]
        form.athlete_ids.data = [athlete.id for athlete in event.athletes.all()]
    
    return render_template('calendar/edit.html', form=form, event=event)


@bp.route('/calendar/<int:event_id>/respond/<string:response>', methods=['POST'])
@login_required
@permission_required('calendar', 'view', society_id_func=lambda event_id, response: _event_scope_id(event_id))
def respond(event_id, response):
    """Athlete responds to a society calendar convocation."""
    event = SocietyCalendarEvent.query.get_or_404(event_id)
    if not event.is_visible_to(current_user):
        abort(403)
    if current_user.id not in [u.id for u in event.athletes.all()]:
        flash('Non sei convocato per questo evento.', 'warning')
        return redirect(url_for('calendar.detail', event_id=event.id))

    if response not in ('accepted', 'declined'):
        flash('Risposta non valida.', 'danger')
        return redirect(url_for('calendar.detail', event_id=event.id))

    row = SocietyCalendarAttendance.query.filter_by(event_id=event.id, user_id=current_user.id).first()
    if not row:
        row = SocietyCalendarAttendance(event_id=event.id, user_id=current_user.id, status='pending')
        db.session.add(row)
    row.status = response
    row.responded_at = datetime.now(timezone.utc)
    db.session.commit()

    flash('Risposta registrata.', 'success')
    return redirect(url_for('calendar.detail', event_id=event.id))


@bp.route('/facilities', methods=['GET', 'POST'])
@login_required
@permission_required('calendar', 'manage', society_id_func=lambda: _scope_id())
def facilities():
    """Manage society facilities/resources (palestre)."""
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('calendar.index'))

    form = FacilityForm()
    if form.validate_on_submit():
        f = Facility(
            society_id=society.id,
            name=form.name.data,
            address=form.address.data or None,
            capacity=form.capacity.data,
            color=(form.color.data or '').strip() or '#0d6efd',
            created_by=current_user.id,
        )
        db.session.add(f)
        db.session.commit()
        flash('Risorsa creata.', 'success')
        return redirect(url_for('calendar.facilities'))

    facilities = Facility.query.filter_by(society_id=society.id).order_by(Facility.name.asc()).all()
    return render_template('calendar/facilities.html', facilities=facilities, form=form, society=society)


@bp.route('/modifications')
@login_required
@permission_required('calendar', 'view', society_id_func=lambda: _scope_id())
def modifications():
    """View modification log for calendar and field planner events."""
    from app.utils.audit import get_planner_changes
    
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('calendar.index'))
    
    # Get modification logs for this society
    changes = get_planner_changes(society.id, limit=100)
    
    return render_template('calendar/modifications.html', changes=changes, society=society)
