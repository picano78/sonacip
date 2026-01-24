"""
Event routes
Create events, convocate athletes, manage responses
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.events import bp
from app.events.forms import EventForm
from app.models import Event, User, Notification
from app.automation.utils import execute_automations
from datetime import datetime


@bp.route('/')
@login_required
def index():
    """List all events"""
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    # Filter based on user role
    if current_user.is_admin():
        # Admin sees all events
        events_query = Event.query
    elif current_user.is_society() or current_user.is_staff():
        # Society/staff see their own events
        events_query = Event.query.filter_by(creator_id=current_user.id)
    else:
        # Athletes see events they're convocated to
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
def create():
    """Create a new event"""
    # Only societies and staff can create events
    if not (current_user.is_society() or current_user.is_staff() or current_user.is_admin()):
        flash('Solo le società e lo staff possono creare eventi.', 'warning')
        return redirect(url_for('events.index'))
    
    form = EventForm()
    
    if form.validate_on_submit():
        event = Event(
            title=form.title.data,
            description=form.description.data,
            event_type=form.event_type.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
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
            status='scheduled'
        )
        
        db.session.add(event)
        db.session.commit()

        # Fire automations on event creation
        execute_automations('event_created', society_id=current_user.id if current_user.is_society() else None, payload={'event_id': event.id})
        
        flash('Evento creato! Ora puoi convocare gli atleti.', 'success')
        return redirect(url_for('events.detail', event_id=event.id))
    
    return render_template('events/create.html', form=form)


@bp.route('/<int:event_id>')
@login_required
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
    can_manage = (current_user.id == event.creator_id or current_user.is_admin())
    
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
def edit(event_id):
    """Edit event"""
    event = Event.query.get_or_404(event_id)
    
    # Check permissions
    if event.creator_id != current_user.id and not current_user.is_admin():
        flash('Non hai i permessi per modificare questo evento.', 'danger')
        return redirect(url_for('events.detail', event_id=event_id))
    
    form = EventForm(obj=event)
    
    if form.validate_on_submit():
        event.title = form.title.data
        event.description = form.description.data
        event.event_type = form.event_type.data
        event.start_date = form.start_date.data
        event.end_date = form.end_date.data
        event.location = form.location.data
        event.address = form.address.data
        event.tournament_name = form.tournament_name.data or None
        event.tournament_phase = form.tournament_phase.data or None
        event.opponent_name = form.opponent_name.data or None
        event.home_away = form.home_away.data or None
        event.score_for = form.score_for.data or None
        event.score_against = form.score_against.data or None
        event.bracket_url = form.bracket_url.data or None
        event.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Evento aggiornato!', 'success')
        return redirect(url_for('events.detail', event_id=event.id))
    
    return render_template('events/edit.html', form=form, event=event)


@bp.route('/<int:event_id>/convocate', methods=['GET', 'POST'])
@login_required
def convocate(event_id):
    """Convocate athletes to event"""
    event = Event.query.get_or_404(event_id)
    
    # Check permissions
    if event.creator_id != current_user.id and not current_user.is_admin():
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
        
        db.session.commit()
        
        flash(f'{len(athlete_ids)} atleti convocati!', 'success')
        return redirect(url_for('events.detail', event_id=event.id))
    
    # Get available athletes
    # For society: their own athletes
    # For staff: athletes of their society
    if current_user.is_society():
        available_athletes = User.query.filter_by(
            role='atleta',
            athlete_society_id=current_user.id,
            is_active=True
        ).all()
    elif current_user.is_staff():
        available_athletes = User.query.filter_by(
            role='atleta',
            athlete_society_id=current_user.society_id,
            is_active=True
        ).all()
    else:
        # Admin can convocate any athlete
        available_athletes = User.query.filter_by(
            role='atleta',
            is_active=True
        ).all()
    
    # Remove already convocated
    available_athletes = [a for a in available_athletes if a not in event.convocated_athletes]
    
    return render_template('events/convocate.html',
                         event=event,
                         athletes=available_athletes)


@bp.route('/<int:event_id>/respond/<string:response>', methods=['POST'])
@login_required
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
def delete(event_id):
    """Delete event"""
    event = Event.query.get_or_404(event_id)
    
    # Check permissions
    if event.creator_id != current_user.id and not current_user.is_admin():
        flash('Non hai i permessi per eliminare questo evento.', 'danger')
        return redirect(url_for('events.detail', event_id=event_id))
    
    db.session.delete(event)
    db.session.commit()
    
    flash('Evento eliminato.', 'success')
    return redirect(url_for('events.index'))


@bp.route('/<int:event_id>/cancel', methods=['POST'])
@login_required
def cancel(event_id):
    """Cancel event"""
    event = Event.query.get_or_404(event_id)
    
    # Check permissions
    if event.creator_id != current_user.id and not current_user.is_admin():
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
def my_events():
    """View my events (as athlete)"""
    if not current_user.is_athlete():
        return redirect(url_for('events.index'))
    
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
