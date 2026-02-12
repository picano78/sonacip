"""
Event routes
Create events, convocate athletes, manage responses
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from app import db
from app.events.forms import EventForm
from app.models import Event, User, Notification, event_athletes, Post, Facility, SocietyCalendarEvent
from app.automation.utils import execute_automations, execute_rules
from app.utils import permission_required, check_permission
from datetime import datetime, timezone

bp = Blueprint('events', __name__, url_prefix='/events')


def _event_scope_id(event: Event | None):
    if event and event.creator:
        society = event.creator.get_primary_society()
        return society.id if society else None
    return None


@bp.route('/')
@login_required
@permission_required('events', 'view')
def index():
    """List all events"""
    page = request.args.get('page', 1, type=int)
    per_page = 15

    admin_access = check_permission(current_user, 'admin', 'access')
    scope = current_user.get_primary_society()

    if admin_access:
        events_query = Event.query
    elif scope:
        events_query = Event.query.filter_by(creator_id=current_user.id)
    else:
        events_query = current_user.events

    pagination = events_query.order_by(Event.start_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    events = pagination.items

    return render_template('events/index.html',
                         events=events,
                         pagination=pagination)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('events', 'create')
def create():
    """Create a new event"""
    form = EventForm(current_user=current_user)
    
    if form.validate_on_submit():
        # Get facility and color
        facility_id = form.facility_id.data if form.facility_id.data and form.facility_id.data != -1 else None
        color = (form.color.data or '').strip() or '#212529'
        
        # Ensure end_date is set
        end_date = form.end_date.data
        if not end_date and form.start_date.data:
            # Default to 2 hours after start if not specified
            from datetime import timedelta
            end_date = form.start_date.data + timedelta(hours=2)
        
        # Check for facility conflicts if facility is selected for training or match events
        society = current_user.get_primary_society()
        if facility_id and society and form.event_type.data in ('allenamento', 'partita'):
            # Verify facility belongs to this society
            facility = Facility.query.filter_by(id=facility_id, society_id=society.id).first()
            if not facility:
                flash('Campo/Palestra non valido per questa società.', 'danger')
                return redirect(url_for('events.create'))
            
            # Check for conflicts in both Event and SocietyCalendarEvent tables
            # Check Event table conflicts
            event_conflict = (
                Event.query.filter(
                    Event.facility_id == facility_id,
                    Event.start_date < end_date,
                    Event.end_date > form.start_date.data,
                    Event.status != 'cancelled'
                )
                .order_by(Event.start_date.asc())
                .first()
            )
            
            # Check SocietyCalendarEvent table conflicts
            calendar_conflict = (
                SocietyCalendarEvent.query.filter(
                    SocietyCalendarEvent.facility_id == facility_id,
                    SocietyCalendarEvent.start_datetime < end_date,
                    SocietyCalendarEvent.end_datetime > form.start_date.data,
                )
                .order_by(SocietyCalendarEvent.start_datetime.asc())
                .first()
            )
            
            if event_conflict:
                flash(
                    f'Conflitto: il campo è già occupato da evento "{event_conflict.title}" '
                    f'({event_conflict.start_date.strftime("%d/%m %H:%M")} - {event_conflict.end_date.strftime("%H:%M")}).',
                    'danger',
                )
                return redirect(url_for('events.create'))
            
            if calendar_conflict:
                flash(
                    f'Conflitto: il campo è già occupato da evento calendario "{calendar_conflict.title}" '
                    f'({calendar_conflict.start_datetime.strftime("%d/%m %H:%M")} - {calendar_conflict.end_datetime.strftime("%H:%M")}).',
                    'danger',
                )
                return redirect(url_for('events.create'))
        
        event = Event(
            title=form.title.data,
            description=form.description.data,
            event_type=form.event_type.data,
            start_date=form.start_date.data,
            end_date=end_date,
            location=form.location.data,
            address=form.address.data,
            tournament_name=form.tournament_name.data or None,
            tournament_phase=form.tournament_phase.data or None,
            opponent_name=form.opponent_name.data or None,
            home_away=form.home_away.data or None,
            score_for=form.score_for.data or None,
            score_against=form.score_against.data or None,
            bracket_url=form.bracket_url.data or None,
            creator_id=current_user.id,
            status='scheduled',
            facility_id=facility_id,
            color=color
        )
        
        db.session.add(event)
        db.session.commit()
        
        # If facility is selected and event type is training or match, create a SocietyCalendarEvent
        if facility_id and society and form.event_type.data in ('allenamento', 'partita'):
            # Map event type to society calendar event type
            event_type_map = {
                'allenamento': 'other',  # training mapped to 'other' or could add new type
                'partita': 'match',
            }
            
            calendar_event = SocietyCalendarEvent(
                society_id=society.id,
                created_by=current_user.id,
                facility_id=facility_id,
                event_id=event.id,  # Link to the Event
                title=form.title.data,
                event_type=event_type_map.get(form.event_type.data, 'other'),
                start_datetime=form.start_date.data,
                end_datetime=end_date,
                color=color,
                location_text=form.location.data,
                notes=f"Sincronizzato automaticamente da evento #{event.id}"
            )
            db.session.add(calendar_event)
            db.session.commit()
            
            flash('Evento creato e integrato nel planner campo! Ora puoi convocare gli atleti.', 'success')
        else:
            flash('Evento creato! Ora puoi convocare gli atleti.', 'success')

        # Fire automations on event creation
        execute_automations('event_created', society_id=society.id if society else None, payload={'event_id': event.id})
        execute_rules('event_created', payload={'event_id': event.id, 'creator_id': current_user.id})
        
        return redirect(url_for('events.detail', event_id=event.id))
    
    return render_template('events/create.html', form=form)


@bp.route('/<int:event_id>')
@login_required
@permission_required('events', 'view')
def detail(event_id):
    """Event detail page"""
    event = Event.query.get_or_404(event_id)
    
    # Get convocated athletes with their status
    convocated = []
    for athlete in event.convocated_athletes:
        status = event.get_athlete_status(athlete.id)
        convocated.append({
            'user': athlete,
            'status': status
        })
    
    # Check if current user can manage this event
    can_manage = current_user.id == event.creator_id or check_permission(current_user, 'events', 'manage', _event_scope_id(event))
    
    # Check if current user is convocated
    is_convocated = current_user in event.convocated_athletes
    my_status = event.get_athlete_status(current_user.id) if is_convocated else None
    
    # Statistics
    stats = {
        'total_convocated': event.convocated_athletes.count(),
        'accepted': event.get_accepted_count(),
        'pending': event.get_pending_count()
    }
    
    return render_template('events/detail.html',
                         event=event,
                         convocated=convocated,
                         can_manage=can_manage,
                         is_convocated=is_convocated,
                         my_status=my_status,
                         stats=stats)


@bp.route('/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('events', 'manage')
def edit(event_id):
    """Edit event"""
    event = Event.query.get_or_404(event_id)
    
    allowed_manage = event.creator_id == current_user.id or check_permission(current_user, 'events', 'manage', _event_scope_id(event))
    if not allowed_manage:
        flash('Non hai i permessi per modificare questo evento.', 'danger')
        return redirect(url_for('events.detail', event_id=event_id))
    
    form = EventForm(obj=event, current_user=current_user)
    
    if form.validate_on_submit():
        # Get facility and color
        facility_id = form.facility_id.data if form.facility_id.data and form.facility_id.data != -1 else None
        color = (form.color.data or '').strip() or '#212529'
        
        # Ensure end_date is set
        end_date = form.end_date.data
        if not end_date and form.start_date.data:
            from datetime import timedelta
            end_date = form.start_date.data + timedelta(hours=2)
        
        # Check for facility conflicts if facility changed for training or match events
        society = current_user.get_primary_society()
        if facility_id and society and form.event_type.data in ('allenamento', 'partita'):
            # Verify facility belongs to this society
            facility = Facility.query.filter_by(id=facility_id, society_id=society.id).first()
            if not facility:
                flash('Campo/Palestra non valido per questa società.', 'danger')
                return redirect(url_for('events.edit', event_id=event_id))
            
            # Check for conflicts excluding this event
            event_conflict = (
                Event.query.filter(
                    Event.id != event.id,
                    Event.facility_id == facility_id,
                    Event.start_date < end_date,
                    Event.end_date > form.start_date.data,
                    Event.status != 'cancelled'
                )
                .order_by(Event.start_date.asc())
                .first()
            )
            
            calendar_conflict = (
                SocietyCalendarEvent.query.filter(
                    SocietyCalendarEvent.facility_id == facility_id,
                    SocietyCalendarEvent.start_datetime < end_date,
                    SocietyCalendarEvent.end_datetime > form.start_date.data,
                    SocietyCalendarEvent.event_id != event.id,  # Exclude linked calendar event
                )
                .order_by(SocietyCalendarEvent.start_datetime.asc())
                .first()
            )
            
            if event_conflict:
                flash(
                    f'Conflitto: il campo è già occupato da evento "{event_conflict.title}" '
                    f'({event_conflict.start_date.strftime("%d/%m %H:%M")} - {event_conflict.end_date.strftime("%H:%M")}).',
                    'danger',
                )
                return redirect(url_for('events.edit', event_id=event_id))
            
            if calendar_conflict:
                flash(
                    f'Conflitto: il campo è già occupato da evento calendario "{calendar_conflict.title}" '
                    f'({calendar_conflict.start_datetime.strftime("%d/%m %H:%M")} - {calendar_conflict.end_datetime.strftime("%H:%M")}).',
                    'danger',
                )
                return redirect(url_for('events.edit', event_id=event_id))
        
        event.title = form.title.data
        event.description = form.description.data
        event.event_type = form.event_type.data
        event.start_date = form.start_date.data
        event.end_date = end_date
        event.location = form.location.data
        event.address = form.address.data
        event.tournament_name = form.tournament_name.data or None
        event.tournament_phase = form.tournament_phase.data or None
        event.opponent_name = form.opponent_name.data or None
        event.home_away = form.home_away.data or None
        event.score_for = form.score_for.data or None
        event.score_against = form.score_against.data or None
        event.bracket_url = form.bracket_url.data or None
        event.facility_id = facility_id
        event.color = color
        event.updated_at = datetime.now(timezone.utc)
        
        # Update linked calendar event if it exists
        if event.calendar_event:
            cal_event = event.calendar_event
            cal_event.title = form.title.data
            cal_event.start_datetime = form.start_date.data
            cal_event.end_datetime = end_date
            cal_event.color = color
            cal_event.location_text = form.location.data
            cal_event.facility_id = facility_id
            cal_event.updated_at = datetime.now(timezone.utc)
        elif facility_id and society and form.event_type.data in ('allenamento', 'partita'):
            # Create calendar event if it doesn't exist and facility is now selected
            event_type_map = {
                'allenamento': 'other',
                'partita': 'match',
            }
            calendar_event = SocietyCalendarEvent(
                society_id=society.id,
                created_by=current_user.id,
                facility_id=facility_id,
                event_id=event.id,
                title=form.title.data,
                event_type=event_type_map.get(form.event_type.data, 'other'),
                start_datetime=form.start_date.data,
                end_datetime=end_date,
                color=color,
                location_text=form.location.data,
                notes=f"Sincronizzato automaticamente da evento #{event.id}"
            )
            db.session.add(calendar_event)
        
        db.session.commit()
        
        flash('Evento aggiornato!', 'success')
        return redirect(url_for('events.detail', event_id=event.id))
    
    return render_template('events/edit.html', form=form, event=event)


@bp.route('/<int:event_id>/convocate', methods=['GET', 'POST'])
@login_required
@permission_required('events', 'manage')
def convocate(event_id):
    """Convocate athletes to event"""
    event = Event.query.get_or_404(event_id)
    
    allowed_manage = event.creator_id == current_user.id or check_permission(current_user, 'events', 'manage', _event_scope_id(event))
    if not allowed_manage:
        flash('Non hai i permessi per convocare atleti.', 'danger')
        return redirect(url_for('events.detail', event_id=event_id))
    
    if request.method == 'POST':
        athlete_ids = request.form.getlist('athletes')
        
        for athlete_id in athlete_ids:
            athlete = User.query.get(int(athlete_id))
            if athlete and athlete not in event.convocated_athletes:
                event.convocated_athletes.append(athlete)
                
                # Create notification
                notification = Notification(
                    user_id=athlete.id,
                    title='Nuova Convocazione',
                    message=f'Sei stato convocato per: {event.title}',
                    notification_type='event',
                    link=url_for('events.detail', event_id=event.id)
                )
                db.session.add(notification)

                # Create a direct social communication for the athlete (scoped)
                society = current_user.get_primary_society()
                society_id = society.id if society else None
                comm = Post(
                    user_id=current_user.id,
                    content=f'Convocazione: {event.title}. Rispondi dalla pagina evento.',
                    is_public=False,
                    audience='direct',
                    society_id=society_id,
                    target_user_id=athlete.id,
                    post_type='official',
                )
                db.session.add(comm)
        
        db.session.commit()
        
        flash(f'{len(athlete_ids)} atleti convocati!', 'success')
        return redirect(url_for('events.detail', event_id=event.id))
    
    # Get available athletes
    # For society: their own athletes
    # For staff: athletes of their society
    scope = current_user.get_primary_society()
    scope_id = scope.id if scope else None
    base_q = User.query.filter(
        User.role.in_(['atleta', 'athlete']),
        User.is_active == True
    )
    if scope_id and not check_permission(current_user, 'admin', 'access'):
        # Canonical membership-based athlete list
        try:
            from app.models import SocietyMembership
            athlete_ids = (
                SocietyMembership.query.filter_by(society_id=scope_id, status='active')
                .filter(SocietyMembership.role_name.in_(['atleta', 'athlete']))
                .with_entities(SocietyMembership.user_id)
                .all()
            )
            athlete_ids = [row[0] for row in athlete_ids]
            available_athletes = base_q.filter(User.id.in_(athlete_ids)).all() if athlete_ids else []
        except Exception:
            available_athletes = []
    else:
        available_athletes = base_q.all()
    
    # Remove already convocated
    available_athletes = [a for a in available_athletes if a not in event.convocated_athletes]
    
    return render_template('events/convocate.html',
                         event=event,
                         athletes=available_athletes)


@bp.route('/<int:event_id>/respond/<string:response>', methods=['POST'])
@login_required
@permission_required('events', 'view')
def respond(event_id, response):
    """Athlete responds to convocation (accept/reject)"""
    event = Event.query.get_or_404(event_id)
    
    # Check if user is convocated
    if current_user not in event.convocated_athletes:
        flash('Non sei convocato per questo evento.', 'warning')
        return redirect(url_for('events.index'))
    
    # Validate response
    if response not in ['accepted', 'rejected']:
        flash('Risposta non valida.', 'danger')
        return redirect(url_for('events.detail', event_id=event_id))
    
    # Update status
    event.set_athlete_status(current_user.id, response)
    
    # Create notification for event creator
    notification = Notification(
        user_id=event.creator_id,
        title='Risposta Convocazione',
        message=f'{current_user.get_full_name()} ha {"accettato" if response == "accepted" else "rifiutato"} la convocazione per {event.title}',
        notification_type='event',
        link=url_for('events.detail', event_id=event.id)
    )
    db.session.add(notification)
    db.session.commit()
    
    flash(f'Risposta registrata: {"Accettato" if response == "accepted" else "Rifiutato"}', 'success')
    return redirect(url_for('events.detail', event_id=event_id))


@bp.route('/<int:event_id>/delete', methods=['POST'])
@login_required
@permission_required('events', 'manage')
def delete(event_id):
    """Delete event"""
    event = Event.query.get_or_404(event_id)
    
    allowed_manage = event.creator_id == current_user.id or check_permission(current_user, 'events', 'manage', _event_scope_id(event))
    if not allowed_manage:
        flash('Non hai i permessi per eliminare questo evento.', 'danger')
        return redirect(url_for('events.detail', event_id=event_id))
    
    db.session.delete(event)
    db.session.commit()
    
    flash('Evento eliminato.', 'success')
    return redirect(url_for('events.index'))


@bp.route('/<int:event_id>/cancel', methods=['POST'])
@login_required
@permission_required('events', 'manage')
def cancel(event_id):
    """Cancel event"""
    event = Event.query.get_or_404(event_id)
    
    allowed_manage = event.creator_id == current_user.id or check_permission(current_user, 'events', 'manage', _event_scope_id(event))
    if not allowed_manage:
        flash('Non hai i permessi per cancellare questo evento.', 'danger')
        return redirect(url_for('events.detail', event_id=event_id))
    
    event.status = 'cancelled'
    db.session.commit()
    
    # Notify all convocated athletes
    for athlete in event.convocated_athletes:
        notification = Notification(
            user_id=athlete.id,
            title='Evento Cancellato',
            message=f'L\'evento "{event.title}" è stato cancellato',
            notification_type='event',
            link=url_for('events.detail', event_id=event.id)
        )
        db.session.add(notification)
    
    db.session.commit()
    
    flash('Evento cancellato. Gli atleti sono stati notificati.', 'success')
    return redirect(url_for('events.detail', event_id=event_id))


@bp.route('/my-events')
@login_required
@permission_required('events', 'view')
def my_events():
    """View my events (as athlete)"""
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    pagination = current_user.events.order_by(Event.start_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    events = pagination.items
    
    # Get status for each event
    events_with_status = []
    for event in events:
        status = event.get_athlete_status(current_user.id)
        events_with_status.append({
            'event': event,
            'status': status
        })
    
    return render_template('events/my_events.html',
                         events_with_status=events_with_status,
                         pagination=pagination)
