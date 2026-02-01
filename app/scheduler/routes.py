"""Routes for Society Calendar (strategic, society-wide)"""
from datetime import datetime, timedelta
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
)
from app.utils import permission_required, check_permission

bp = Blueprint('scheduler', __name__, url_prefix='/scheduler')


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
    if check_permission(current_user, 'admin', 'access'):
        return q

    society = current_user.get_primary_society()
    if not society:
        return q.filter(False)

    return q.filter(SocietyCalendarEvent.society_id == society.id)


@bp.route('/calendar')
@login_required
@permission_required('calendar', 'view')
def index():
    view = request.args.get('view', 'week')
    try:
        start_str = request.args.get('start')
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else datetime.utcnow().date()
    except ValueError:
        start_date = datetime.utcnow().date()

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

    # Group events by date for the view
    grouped = {}
    for ev in events:
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


@bp.route('/calendar/<int:event_id>')
@login_required
@permission_required('calendar', 'view')
def detail(event_id):
    event = SocietyCalendarEvent.query.get_or_404(event_id)
    if not event.is_visible_to(current_user):
        abort(403)
    return render_template('calendar/detail.html', event=event)


@bp.route('/calendar/new', methods=['GET', 'POST'])
@login_required
@permission_required('calendar', 'manage')
def create():
    form = SocietyCalendarEventForm(current_user=current_user)
    scope = current_user.get_primary_society()
    scope_id = scope.id if scope else None

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
        flash('Evento inserito nel Calendario Società.', 'success')
        return redirect(url_for('calendar.index'))

    return render_template('calendar/create.html', form=form)


@bp.route('/facilities', methods=['GET', 'POST'])
@login_required
@permission_required('calendar', 'manage')
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