"""Routes for Field Planner (field/facility occupancy only)"""
from datetime import datetime, timedelta, timezone, date, time as dt_time
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.field_planner import bp
from app.field_planner.forms import FieldPlannerEventForm
from app.models import FieldPlannerEvent, Facility, Notification
from app.utils import permission_required, check_permission, get_active_society_id
from app.utils.audit import log_planner_change
from app.notifications.utils import notify_planner_change


def _scope_id():
    """Get active society ID for permission checks"""
    return get_active_society_id(current_user)


def _event_scope_id(event_id: int):
    """Get society ID for a specific event"""
    ev = db.session.get(FieldPlannerEvent, event_id)
    return ev.society_id if ev else None


def _get_facilities_for_society(society_id):
    """Get facilities for a society, ordered by name"""
    return Facility.query.filter_by(society_id=society_id).order_by(Facility.name.asc()).all()


@bp.route('/')
@login_required
@permission_required('field_planner', 'view', society_id_func=lambda: _scope_id())
def index():
    """Field Planner calendar grid view"""
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
        return redirect(url_for('main.dashboard'))

    facility_id = request.args.get('facility_id', type=int)
    facilities = []
    if sid:
        facilities = Facility.query.filter_by(society_id=sid).order_by(Facility.name.asc()).all()

    # Query field planner events
    q = FieldPlannerEvent.query
    if sid:
        q = q.filter(FieldPlannerEvent.society_id == sid)
    elif check_permission(current_user, 'admin', 'access'):
        pass  # Admin sees all
    else:
        q = q.filter(False)  # No access

    q = q.filter(
        FieldPlannerEvent.start_datetime < datetime.combine(end_date, datetime.min.time()),
        FieldPlannerEvent.end_datetime > datetime.combine(start_date, datetime.min.time()),
    )
    if facility_id:
        q = q.filter(FieldPlannerEvent.facility_id == facility_id)

    events = q.order_by(FieldPlannerEvent.start_datetime.asc()).all()

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

    month_names_it = ['', 'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
                       'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
    prev_month = (start_date.replace(day=1) - timedelta(days=1)).replace(day=1) if view == 'month' else None
    next_month = end_date if view == 'month' else None
    today = datetime.now(timezone.utc).date()

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
        'field_planner/index.html',
        view=view,
        start_date=start_date,
        end_date=end_date,
        days=days,
        hours=hours,
        facilities=facilities,
        facility_id=facility_id,
        grid_map=grid_map,
        prev_nav=prev_nav,
        next_nav=next_nav,
        nav_title=nav_title,
        nav_subtitle=nav_subtitle,
        today=today,
    )


@bp.route('/event/<int:event_id>')
@login_required
@permission_required('field_planner', 'view', society_id_func=_event_scope_id)
def detail(event_id):
    """View field planner event details"""
    event = FieldPlannerEvent.query.get_or_404(event_id)
    if not event.is_visible_to(current_user):
        abort(403)
    return render_template('field_planner/detail.html', event=event)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
@permission_required('field_planner', 'manage', society_id_func=lambda: _scope_id())
def create():
    """Create new field planner event"""
    form = FieldPlannerEventForm()
    
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('field_planner.index'))
    
    # Populate facility choices
    facilities = _get_facilities_for_society(society.id)
    form.facility_id.choices = [(f.id, f.name) for f in facilities]
    
    if not facilities:
        flash('Devi creare almeno un campo prima di aggiungere eventi al planner.', 'warning')
        return redirect(url_for('calendar.facilities'))

    # Pre-fill date/time from URL params
    if request.method == 'GET':
        date_param = request.args.get('date')
        hour_param = request.args.get('hour')
        if date_param:
            try:
                prefill_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                form.start_date.data = prefill_date
            except ValueError:
                pass
        if hour_param:
            try:
                prefill_hour = int(hour_param)
                form.start_time.data = dt_time(prefill_hour, 0)
                form.end_time.data = dt_time(min(prefill_hour + 1, 23), 0)
            except (ValueError, TypeError):
                pass

    if form.validate_on_submit():
        start_dt = datetime.combine(form.start_date.data, form.start_time.data)
        end_dt = datetime.combine(form.start_date.data, form.end_time.data)
        
        # Check for conflicts on the same facility
        conflict = (
            FieldPlannerEvent.query.filter(
                FieldPlannerEvent.society_id == society.id,
                FieldPlannerEvent.facility_id == form.facility_id.data,
                FieldPlannerEvent.start_datetime < end_dt,
                FieldPlannerEvent.end_datetime > start_dt,
            )
            .order_by(FieldPlannerEvent.start_datetime.asc())
            .first()
        )
        if conflict:
            flash(
                f'Sovraccaricamento campo: il campo è già occupato da "{conflict.title}" '
                f'({conflict.start_datetime.strftime("%d/%m %H:%M")} - {conflict.end_datetime.strftime("%H:%M")}). '
                f'Il planner campo permette un solo impegno per campo alla volta.',
                'danger',
            )
            return redirect(url_for('field_planner.create'))

        # Handle recurring events for entire season (Aug 1 - Jul 31)
        if form.is_recurring.data and form.recurrence_pattern.data == 'weekly':
            # Create main event
            event = FieldPlannerEvent(
                society_id=society.id,
                facility_id=form.facility_id.data,
                created_by=current_user.id,
                event_type=form.event_type.data,
                title=form.title.data,
                team=form.team.data,
                category=form.category.data,
                start_datetime=start_dt,
                end_datetime=end_dt,
                is_recurring=True,
                recurrence_pattern='weekly',
                notes=form.notes.data,
                color=form.color.data or '#28a745'
            )
            
            # Calculate season end: July 31 of next year if we're after August, otherwise this year
            current_year = form.start_date.data.year
            if form.start_date.data.month >= 8:
                season_end = date(current_year + 1, 7, 31)
            else:
                season_end = date(current_year, 7, 31)
            
            event.recurrence_end_date = season_end
            db.session.add(event)
            db.session.flush()
            
            # Create recurring instances
            current_dt = start_dt + timedelta(days=7)
            end_season_dt = datetime.combine(season_end, start_dt.time())
            created_count = 1
            
            while current_dt <= end_season_dt:
                recurring_end_dt = current_dt + (end_dt - start_dt)
                
                # Check for conflict on each recurring date
                conflict_check = (
                    FieldPlannerEvent.query.filter(
                        FieldPlannerEvent.society_id == society.id,
                        FieldPlannerEvent.facility_id == form.facility_id.data,
                        FieldPlannerEvent.start_datetime < recurring_end_dt,
                        FieldPlannerEvent.end_datetime > current_dt,
                    ).first()
                )
                
                if not conflict_check:
                    recurring_event = FieldPlannerEvent(
                        society_id=society.id,
                        facility_id=form.facility_id.data,
                        created_by=current_user.id,
                        event_type=form.event_type.data,
                        title=form.title.data,
                        team=form.team.data,
                        category=form.category.data,
                        start_datetime=current_dt,
                        end_datetime=recurring_end_dt,
                        is_recurring=False,
                        parent_event_id=event.id,
                        notes=form.notes.data,
                        color=form.color.data or '#28a745'
                    )
                    db.session.add(recurring_event)
                    created_count += 1
                
                current_dt += timedelta(days=7)
            
            db.session.commit()
            
            # Log the creation
            log_planner_change(
                user_id=current_user.id,
                society_id=society.id,
                action='field_planner_created_recurring',
                entity_type='FieldPlannerEvent',
                entity_id=event.id,
                details={
                    'title': event.title,
                    'facility_id': event.facility_id,
                    'event_type': event.event_type,
                    'instances_created': created_count,
                    'season_end': season_end.strftime('%Y-%m-%d')
                }
            )
            
            flash(f'Allenamento ricorrente creato: {created_count} sessioni programmate fino al {season_end.strftime("%d/%m/%Y")}.', 'success')
            
        else:
            # Create single event
            event = FieldPlannerEvent(
                society_id=society.id,
                facility_id=form.facility_id.data,
                created_by=current_user.id,
                event_type=form.event_type.data,
                title=form.title.data,
                team=form.team.data,
                category=form.category.data,
                start_datetime=start_dt,
                end_datetime=end_dt,
                notes=form.notes.data,
                color=form.color.data or '#28a745'
            )
            db.session.add(event)
            db.session.commit()
            
            # Log the creation
            log_planner_change(
                user_id=current_user.id,
                society_id=society.id,
                action='field_planner_created',
                entity_type='FieldPlannerEvent',
                entity_id=event.id,
                details={
                    'title': event.title,
                    'facility_id': event.facility_id,
                    'event_type': event.event_type,
                    'start_datetime': event.start_datetime.strftime('%Y-%m-%d %H:%M'),
                    'end_datetime': event.end_datetime.strftime('%Y-%m-%d %H:%M')
                }
            )
            
            flash('Evento inserito nel Planner Campo.', 'success')

        # Notify society members
        facility = db.session.get(Facility, form.facility_id.data)
        if facility:
            notify_planner_change(
                society.id,
                f"Nuovo impegno sul campo: {event.title}",
                f"È stato creato un nuovo impegno '{event.title}' sul campo {facility.name} per il {event.start_datetime.strftime('%d/%m/%Y')} alle {event.start_datetime.strftime('%H:%M')}.",
                link=url_for('field_planner.detail', event_id=event.id)
            )

        return redirect(url_for('field_planner.index'))

    return render_template('field_planner/create.html', form=form, facilities=facilities)


@bp.route('/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('field_planner', 'manage', society_id_func=_event_scope_id)
def edit(event_id):
    """Edit field planner event"""
    event = FieldPlannerEvent.query.get_or_404(event_id)
    
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('field_planner.index'))
    
    # Check permissions
    if not check_permission(current_user, 'admin', 'access'):
        if event.society_id != get_active_society_id(current_user):
            abort(403)
    
    # Populate facility choices
    facilities = _get_facilities_for_society(society.id)
    
    form = FieldPlannerEventForm()
    form.facility_id.choices = [(f.id, f.name) for f in facilities]
    
    if form.validate_on_submit():
        # Store old values for logging
        old_values = {
            'title': event.title,
            'facility_id': event.facility_id,
            'start_datetime': event.start_datetime.strftime('%Y-%m-%d %H:%M'),
            'end_datetime': event.end_datetime.strftime('%Y-%m-%d %H:%M')
        }
        
        start_dt = datetime.combine(form.start_date.data, form.start_time.data)
        end_dt = datetime.combine(form.start_date.data, form.end_time.data)
        
        # Check for conflicts on the same facility (excluding current event)
        conflict = (
            FieldPlannerEvent.query.filter(
                FieldPlannerEvent.id != event.id,
                FieldPlannerEvent.society_id == society.id,
                FieldPlannerEvent.facility_id == form.facility_id.data,
                FieldPlannerEvent.start_datetime < end_dt,
                FieldPlannerEvent.end_datetime > start_dt,
            )
            .order_by(FieldPlannerEvent.start_datetime.asc())
            .first()
        )
        if conflict:
            flash(
                f'Sovraccaricamento campo: il campo è già occupato da "{conflict.title}" '
                f'({conflict.start_datetime.strftime("%d/%m %H:%M")} - {conflict.end_datetime.strftime("%H:%M")}). '
                f'Il planner campo permette un solo impegno per campo alla volta.',
                'danger',
            )
            return render_template('field_planner/edit.html', form=form, event=event, facilities=facilities)
        
        # Update event fields
        event.facility_id = form.facility_id.data
        event.event_type = form.event_type.data
        event.title = form.title.data
        event.team = form.team.data
        event.category = form.category.data
        event.start_datetime = start_dt
        event.end_datetime = end_dt
        event.notes = form.notes.data
        event.color = form.color.data or '#28a745'
        
        db.session.commit()
        
        # Log the modification
        log_planner_change(
            user_id=current_user.id,
            society_id=event.society_id,
            action='field_planner_updated',
            entity_type='FieldPlannerEvent',
            entity_id=event.id,
            details={
                'old_values': old_values,
                'new_values': {
                    'title': event.title,
                    'facility_id': event.facility_id,
                    'start_datetime': event.start_datetime.strftime('%Y-%m-%d %H:%M'),
                    'end_datetime': event.end_datetime.strftime('%Y-%m-%d %H:%M')
                }
            }
        )
        
        # Notify society members
        facility = db.session.get(Facility, form.facility_id.data)
        if facility:
            notify_planner_change(
                society.id,
                f"Impegno modificato: {event.title}",
                f"L'impegno '{event.title}' sul campo {facility.name} è stato modificato per il {event.start_datetime.strftime('%d/%m/%Y')} alle {event.start_datetime.strftime('%H:%M')}.",
                link=url_for('field_planner.detail', event_id=event.id)
            )
        
        flash('Evento aggiornato nel Planner Campo.', 'success')
        return redirect(url_for('field_planner.detail', event_id=event.id))
    
    # Pre-fill form with existing event data
    if request.method == 'GET':
        form.facility_id.data = event.facility_id
        form.event_type.data = event.event_type
        form.title.data = event.title
        form.team.data = event.team
        form.category.data = event.category
        form.start_date.data = event.start_datetime.date()
        form.start_time.data = event.start_datetime.time()
        form.end_time.data = event.end_datetime.time()
        form.notes.data = event.notes
        form.color.data = event.color
    
    return render_template('field_planner/edit.html', form=form, event=event, facilities=facilities)


@bp.route('/event/<int:event_id>/delete', methods=['POST'])
@login_required
@permission_required('field_planner', 'manage', society_id_func=_event_scope_id)
def delete(event_id):
    """Delete field planner event"""
    event = FieldPlannerEvent.query.get_or_404(event_id)
    
    if not check_permission(current_user, 'admin', 'access'):
        if event.society_id != get_active_society_id(current_user):
            abort(403)
    
    # If it's a recurring parent, delete all children too
    if event.is_recurring:
        FieldPlannerEvent.query.filter_by(parent_event_id=event.id).delete()
    
    # Log before deletion
    log_planner_change(
        user_id=current_user.id,
        society_id=event.society_id,
        action='field_planner_deleted',
        entity_type='FieldPlannerEvent',
        entity_id=event.id,
        details={
            'title': event.title,
            'facility_id': event.facility_id,
            'event_type': event.event_type,
            'was_recurring': event.is_recurring
        }
    )
    
    db.session.delete(event)
    db.session.commit()
    
    flash('Evento eliminato dal Planner Campo.', 'success')
    return redirect(url_for('field_planner.index'))
