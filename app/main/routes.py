"""
Main routes
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import current_user, login_required
from app import db
from app.utils import check_permission
from app.main.forms import DashboardEditForm

bp = Blueprint('main', __name__, url_prefix='')


@bp.route('/')
def index():
    """Homepage - redirect based on auth status"""
    if current_user.is_authenticated:
        return redirect(url_for('social.feed'))
    return render_template('main/index.html')


@bp.route('/about')
def about():
    """About page"""
    return render_template('main/about.html')


@bp.route('/contact')
def contact():
    """Contact page"""
    return render_template('main/contact.html')


@bp.route('/healthz')
def healthz():
    """Lightweight health check for uptime monitoring"""
    return {'status': 'ok'}, 200


@bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard (personal, configurable)."""
    from app.models import Dashboard, DashboardTemplate, Notification, Message, Post, Event, Task
    import json

    dash = Dashboard.query.filter_by(user_id=current_user.id, is_default=True).first()
    if not dash:
        dash = Dashboard.query.filter_by(user_id=current_user.id).order_by(Dashboard.id.asc()).first()

    if not dash:
        tpl = DashboardTemplate.query.filter_by(role_name=current_user.role).first()
        if not tpl:
            tpl = DashboardTemplate.query.filter_by(role_name=None).first()
        widgets = []
        layout = 'grid'
        if tpl:
            try:
                widgets = json.loads(tpl.widgets or '[]')
            except Exception:
                widgets = []
            layout = tpl.layout or 'grid'
        if not widgets:
            widgets = [
                {"type": "quick_links"},
                {"type": "stats"},
                {"type": "recent_notifications"},
            ]
        dash = Dashboard(
            name='Il mio cruscotto',
            description='Dashboard personale',
            user_id=current_user.id,
            widgets=json.dumps(widgets),
            layout=layout,
            is_default=True,
        )
        db.session.add(dash)
        db.session.commit()

    widgets = dash.get_widgets()

    # Basic data used by widgets (keep safe / fast)
    stats = {}
    try:
        stats = {
            "posts": Post.query.filter_by(user_id=current_user.id).count(),
            "events_created": Event.query.filter_by(creator_id=current_user.id).count(),
            "tasks_assigned": Task.query.filter_by(assigned_to=current_user.id).count(),
            "notifications_unread": Notification.query.filter_by(user_id=current_user.id, is_read=False).count(),
            "messages_unread": Message.query.filter_by(recipient_id=current_user.id, is_read=False).count(),
        }
    except Exception:
        stats = {}

    recent_notifications = []
    try:
        recent_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(5).all()
    except Exception:
        recent_notifications = []

    return render_template(
        'main/dashboard.html',
        dashboard=dash,
        widgets=widgets,
        stats=stats,
        recent_notifications=recent_notifications,
    )


@bp.route('/dashboard/edit', methods=['GET', 'POST'])
@login_required
def edit_dashboard():
    """Edit the current user's default dashboard."""
    from app.models import Dashboard, DashboardTemplate
    import json

    dash = Dashboard.query.filter_by(user_id=current_user.id, is_default=True).first()
    if not dash:
        dash = Dashboard.query.filter_by(user_id=current_user.id).order_by(Dashboard.id.asc()).first()
    if not dash:
        # Force creation by visiting /dashboard first
        return redirect(url_for('main.dashboard'))

    form = DashboardEditForm()
    if request.method == 'GET':
        form.name.data = dash.name
        form.widgets.data = dash.widgets

    if form.validate_on_submit():
        try:
            parsed = json.loads(form.widgets.data or '[]')
            if not isinstance(parsed, list):
                raise ValueError('Widgets must be a JSON array')
        except Exception as exc:
            flash(f'JSON non valido: {exc}', 'danger')
            return render_template('main/dashboard_edit.html', form=form, dashboard=dash)

        dash.name = form.name.data
        dash.widgets = form.widgets.data
        db.session.commit()
        flash('Cruscotto aggiornato.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('main/dashboard_edit.html', form=form, dashboard=dash)


@bp.route('/dashboard/reset', methods=['POST'])
@login_required
def reset_dashboard():
    """Reset dashboard to the role template."""
    from app.models import Dashboard, DashboardTemplate
    import json

    dash = Dashboard.query.filter_by(user_id=current_user.id, is_default=True).first()
    if not dash:
        flash('Nessun cruscotto trovato.', 'warning')
        return redirect(url_for('main.dashboard'))

    tpl = DashboardTemplate.query.filter_by(role_name=current_user.role).first()
    if not tpl:
        tpl = DashboardTemplate.query.filter_by(role_name=None).first()
    if not tpl:
        flash('Nessun template disponibile.', 'warning')
        return redirect(url_for('main.dashboard'))

    dash.layout = tpl.layout or dash.layout
    dash.widgets = tpl.widgets
    db.session.commit()
    flash('Cruscotto ripristinato al template.', 'success')
    return redirect(url_for('main.dashboard'))


@bp.route('/scope/society', methods=['POST'])
@login_required
def set_society_scope():
    """
    Set active society scope in session.
    Used to switch context when a user has multiple memberships.
    """
    society_id = request.form.get('society_id', type=int)
    if not society_id:
        session.pop('active_society_id', None)
        flash('Contesto società ripristinato.', 'success')
        return redirect(request.referrer or url_for('main.dashboard'))

    if not current_user.can_access_society(society_id) and not check_permission(current_user, 'admin', 'access'):
        flash('Non puoi selezionare questa società.', 'danger')
        return redirect(request.referrer or url_for('main.dashboard'))

    session['active_society_id'] = int(society_id)
    flash('Contesto società aggiornato.', 'success')
    return redirect(request.referrer or url_for('main.dashboard'))
