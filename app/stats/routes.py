import json
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from app import db
from app.models import AthleteStat, StatTemplate, User, SocietyMembership
from app.utils import check_permission, get_active_society_id

bp = Blueprint('stats', __name__, url_prefix='/stats')


@bp.before_request
def _check_feature():
    from app.utils import check_feature_enabled
    if not check_feature_enabled('sports_stats'):
        from flask import flash
        flash('Questa funzionalità non è attualmente disponibile.', 'warning')
        return redirect(url_for('main.dashboard'))


def _is_coach_or_admin():
    if check_permission(current_user, 'admin', 'access'):
        return True
    scope_id = get_active_society_id(current_user)
    if scope_id:
        membership = SocietyMembership.query.filter_by(
            society_id=scope_id, user_id=current_user.id, status='active'
        ).first()
        if membership and membership.role_name in ('coach', 'dirigente', 'staff'):
            return True
    if getattr(current_user, 'staff_role', None) in ('coach', 'dirigente'):
        return True
    return False


def _get_society_members():
    scope_id = get_active_society_id(current_user)
    if not scope_id:
        return []
    memberships = SocietyMembership.query.filter_by(
        society_id=scope_id, status='active'
    ).all()
    user_ids = [m.user_id for m in memberships]
    if not user_ids:
        return []
    return User.query.filter(User.id.in_(user_ids)).order_by(User.last_name, User.first_name).all()


def _parse_metrics(stat):
    try:
        return json.loads(stat.metrics) if stat.metrics else {}
    except (json.JSONDecodeError, TypeError):
        return {}


@bp.route('/')
@login_required
def index():
    scope_id = get_active_society_id(current_user)
    base_q = AthleteStat.query
    if scope_id:
        member_ids = [m.user_id for m in SocietyMembership.query.filter_by(society_id=scope_id, status='active').all()]
        if member_ids:
            base_q = base_q.filter(AthleteStat.user_id.in_(member_ids))
        else:
            base_q = base_q.filter(AthleteStat.id < 0)

    total_entries = base_q.count()
    athletes_tracked = db.session.query(func.count(func.distinct(AthleteStat.user_id))).filter(
        AthleteStat.id.in_([s.id for s in base_q.all()])
    ).scalar() if total_entries > 0 else 0
    sport_types_count = db.session.query(func.count(func.distinct(AthleteStat.sport_type))).filter(
        AthleteStat.id.in_([s.id for s in base_q.all()])
    ).scalar() if total_entries > 0 else 0

    recent_stats = base_q.order_by(AthleteStat.stat_date.desc(), AthleteStat.created_at.desc()).limit(10).all()
    for s in recent_stats:
        s._parsed_metrics = _parse_metrics(s)

    top_athletes = []
    if total_entries > 0:
        top_q = (
            db.session.query(AthleteStat.user_id, func.count(AthleteStat.id).label('cnt'))
            .filter(AthleteStat.id.in_([s.id for s in base_q.all()]))
            .group_by(AthleteStat.user_id)
            .order_by(desc('cnt'))
            .limit(5)
            .all()
        )
        for user_id, cnt in top_q:
            u = db.session.get(User, user_id)
            if u:
                top_athletes.append({'user': u, 'count': cnt})

    return render_template('stats/index.html',
                           total_entries=total_entries,
                           athletes_tracked=athletes_tracked,
                           sport_types_count=sport_types_count,
                           recent_stats=recent_stats,
                           top_athletes=top_athletes)


@bp.route('/athlete/<int:user_id>')
@login_required
def athlete(user_id):
    user = User.query.get_or_404(user_id)
    season_filter = request.args.get('season', '')
    type_filter = request.args.get('stat_type', '')

    q = AthleteStat.query.filter_by(user_id=user_id)
    if season_filter:
        q = q.filter_by(season=season_filter)
    if type_filter:
        q = q.filter_by(stat_type=type_filter)

    stats = q.order_by(AthleteStat.stat_date.desc()).all()
    for s in stats:
        s._parsed_metrics = _parse_metrics(s)

    seasons = db.session.query(func.distinct(AthleteStat.season)).filter(
        AthleteStat.user_id == user_id, AthleteStat.season.isnot(None)
    ).all()
    seasons = sorted([s[0] for s in seasons if s[0]], reverse=True)

    stat_types = db.session.query(func.distinct(AthleteStat.stat_type)).filter(
        AthleteStat.user_id == user_id, AthleteStat.stat_type.isnot(None)
    ).all()
    stat_types = sorted([s[0] for s in stat_types if s[0]])

    summary = {}
    if stats:
        latest = stats[0]
        summary = _parse_metrics(latest)

    return render_template('stats/athlete.html',
                           athlete=user,
                           stats=stats,
                           seasons=seasons,
                           stat_types=stat_types,
                           summary=summary,
                           current_season=season_filter,
                           current_type=type_filter)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not _is_coach_or_admin():
        flash('Solo allenatori e amministratori possono registrare statistiche.', 'danger')
        return redirect(url_for('stats.index'))

    members = _get_society_members()
    templates = StatTemplate.query.order_by(StatTemplate.name).all()

    if request.method == 'POST':
        user_id = request.form.get('user_id', type=int)
        stat_date_str = request.form.get('stat_date', '')
        sport_type = request.form.get('sport_type', '').strip()
        stat_type = request.form.get('stat_type', '').strip()
        season = request.form.get('season', '').strip()
        notes = request.form.get('notes', '').strip()

        if not user_id or not stat_date_str or not sport_type:
            flash('Compilare tutti i campi obbligatori.', 'danger')
            return render_template('stats/create.html', members=members, templates=templates)

        try:
            stat_date = datetime.strptime(stat_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Data non valida.', 'danger')
            return render_template('stats/create.html', members=members, templates=templates)

        default_keys = ['gol', 'assist', 'minuti', 'voto', 'presenze', 'ammonizioni', 'espulsioni']
        metrics = {}
        for key in default_keys:
            val = request.form.get(f'metric_{key}', '').strip()
            if val:
                try:
                    metrics[key] = float(val) if '.' in val else int(val)
                except ValueError:
                    metrics[key] = val

        custom_keys = request.form.getlist('custom_key')
        custom_vals = request.form.getlist('custom_value')
        for k, v in zip(custom_keys, custom_vals):
            k = k.strip()
            v = v.strip()
            if k and v:
                try:
                    metrics[k] = float(v) if '.' in v else int(v)
                except ValueError:
                    metrics[k] = v

        scope_id = get_active_society_id(current_user)
        stat = AthleteStat(
            user_id=user_id,
            society_id=scope_id,
            season=season or None,
            sport_type=sport_type,
            stat_date=stat_date,
            stat_type=stat_type or None,
            metrics=json.dumps(metrics),
            notes=notes or None,
            created_by=current_user.id,
        )
        db.session.add(stat)
        db.session.commit()
        flash('Statistiche registrate con successo!', 'success')
        return redirect(url_for('stats.entry', stat_id=stat.id))

    return render_template('stats/create.html', members=members, templates=templates)


@bp.route('/entry/<int:stat_id>')
@login_required
def entry(stat_id):
    stat = AthleteStat.query.get_or_404(stat_id)
    stat._parsed_metrics = _parse_metrics(stat)
    return render_template('stats/entry.html', stat=stat)


@bp.route('/entry/<int:stat_id>/delete', methods=['POST'])
@login_required
def delete_entry(stat_id):
    stat = AthleteStat.query.get_or_404(stat_id)
    if stat.created_by != current_user.id and not check_permission(current_user, 'admin', 'access'):
        flash('Non hai i permessi per eliminare questa voce.', 'danger')
        return redirect(url_for('stats.entry', stat_id=stat_id))
    db.session.delete(stat)
    db.session.commit()
    flash('Voce eliminata con successo.', 'success')
    return redirect(url_for('stats.index'))


@bp.route('/templates')
@login_required
def templates_list():
    scope_id = get_active_society_id(current_user)
    q = StatTemplate.query
    if scope_id:
        q = q.filter((StatTemplate.society_id == scope_id) | (StatTemplate.is_global == True))
    templates = q.order_by(StatTemplate.name).all()
    for t in templates:
        try:
            fields = json.loads(t.fields) if t.fields else []
            t._fields_count = len(fields) if isinstance(fields, list) else 0
        except (json.JSONDecodeError, TypeError):
            t._fields_count = 0
    return render_template('stats/templates_list.html', templates=templates)


@bp.route('/templates/create', methods=['GET', 'POST'])
@login_required
def template_create():
    if not _is_coach_or_admin():
        flash('Solo allenatori e amministratori possono creare template.', 'danger')
        return redirect(url_for('stats.templates_list'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        sport_type = request.form.get('sport_type', '').strip()
        stat_type = request.form.get('stat_type', '').strip()
        is_global = request.form.get('is_global') == '1'

        field_names = request.form.getlist('field_name')
        field_types = request.form.getlist('field_type')
        fields = []
        for fn, ft in zip(field_names, field_types):
            fn = fn.strip()
            ft = ft.strip()
            if fn:
                fields.append({'name': fn, 'type': ft or 'number'})

        if not name:
            flash('Il nome del template è obbligatorio.', 'danger')
            return render_template('stats/template_create.html')

        scope_id = get_active_society_id(current_user)
        template = StatTemplate(
            name=name,
            sport_type=sport_type or None,
            stat_type=stat_type or None,
            fields=json.dumps(fields),
            society_id=scope_id,
            is_global=is_global,
            created_by=current_user.id,
        )
        db.session.add(template)
        db.session.commit()
        flash('Template creato con successo!', 'success')
        return redirect(url_for('stats.templates_list'))

    return render_template('stats/template_create.html')


@bp.route('/leaderboard')
@login_required
def leaderboard():
    flash('La classifica è stata rimossa.', 'info')
    return redirect(url_for('stats.index'))


@bp.route('/api/chart-data/<int:user_id>')
@login_required
def chart_data(user_id):
    stat_type = request.args.get('stat_type', '')
    season = request.args.get('season', '')
    metric = request.args.get('metric', 'gol')

    q = AthleteStat.query.filter_by(user_id=user_id)
    if stat_type:
        q = q.filter_by(stat_type=stat_type)
    if season:
        q = q.filter_by(season=season)

    stats = q.order_by(AthleteStat.stat_date.asc()).all()

    labels = []
    values = []
    for s in stats:
        labels.append(s.stat_date.strftime('%d/%m/%Y') if s.stat_date else '')
        m = _parse_metrics(s)
        val = m.get(metric, 0)
        try:
            val = float(val)
        except (ValueError, TypeError):
            val = 0
        values.append(val)

    return jsonify({
        'labels': labels,
        'values': values,
        'metric': metric,
        'user_id': user_id,
    })
