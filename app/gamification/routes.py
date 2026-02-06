from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from app import db
from app.utils import check_permission

bp = Blueprint('gamification', __name__, url_prefix='/gamification')


@bp.before_request
def _check_feature():
    from app.utils import check_feature_enabled
    if not check_feature_enabled('gamification'):
        from flask import flash
        flash('Questa funzionalità non è attualmente disponibile.', 'warning')
        return redirect(url_for('main.dashboard'))


@bp.route('/')
@login_required
def index():
    from app.gamification.engine import (
        get_or_create_user_points, get_level, get_level_progress,
        get_next_level_points, get_leaderboard, check_and_award_badges
    )
    from app.models import UserBadge, Badge

    check_and_award_badges(current_user.id)
    up = get_or_create_user_points(current_user.id)
    points = up.total_points if up else 0
    level = get_level(points)
    progress = get_level_progress(points)
    next_lvl_pts = get_next_level_points(points)

    recent_badges = []
    try:
        recent_badges = db.session.query(UserBadge, Badge).join(
            Badge, Badge.id == UserBadge.badge_id
        ).filter(UserBadge.user_id == current_user.id).order_by(
            UserBadge.earned_at.desc()
        ).limit(6).all()
    except Exception:
        pass

    leaderboard = get_leaderboard(limit=10)

    return render_template('gamification/index.html',
        user_points=up, level=level, progress=progress,
        next_lvl_pts=next_lvl_pts, points=points,
        recent_badges=recent_badges, leaderboard=leaderboard)


@bp.route('/badges')
@login_required
def badges():
    from app.models import Badge, UserBadge
    from app.gamification.engine import get_badge_progress

    all_badges = Badge.query.filter_by(is_active=True).order_by(Badge.category, Badge.requirement_value).all()
    earned_ids = set()
    try:
        earned = UserBadge.query.filter_by(user_id=current_user.id).all()
        earned_ids = {ub.badge_id for ub in earned}
    except Exception:
        pass

    badge_data = []
    for b in all_badges:
        current, req_val, pct = get_badge_progress(current_user.id, b)
        badge_data.append({
            'badge': b,
            'earned': b.id in earned_ids,
            'current': current,
            'required': req_val,
            'progress': pct,
        })

    return render_template('gamification/badges.html',
        badge_data=badge_data, earned_count=len(earned_ids), total_count=len(all_badges))


@bp.route('/leaderboard')
@login_required
def leaderboard():
    from app.gamification.engine import get_leaderboard, get_level
    entries = get_leaderboard(limit=50)
    return render_template('gamification/leaderboard.html',
        entries=entries, get_level=get_level)


@bp.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    from app.models import User, UserBadge, Badge
    from app.gamification.engine import (
        get_or_create_user_points, get_level, get_level_progress,
        get_next_level_points, get_badge_progress
    )

    user = User.query.get_or_404(user_id)
    up = get_or_create_user_points(user_id)
    points = up.total_points if up else 0
    level = get_level(points)
    progress = get_level_progress(points)
    next_lvl_pts = get_next_level_points(points)

    user_badges = []
    try:
        user_badges = db.session.query(UserBadge, Badge).join(
            Badge, Badge.id == UserBadge.badge_id
        ).filter(UserBadge.user_id == user_id).order_by(
            UserBadge.earned_at.desc()
        ).all()
    except Exception:
        pass

    return render_template('gamification/profile.html',
        profile_user=user, user_points=up, level=level,
        progress=progress, next_lvl_pts=next_lvl_pts,
        points=points, user_badges=user_badges)


@bp.route('/admin')
@login_required
def admin():
    if not current_user.is_admin():
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('gamification.index'))
    from app.models import Badge
    badges = Badge.query.order_by(Badge.category, Badge.name).all()
    return render_template('gamification/admin.html', badges=badges)


@bp.route('/admin/badge/create', methods=['POST'])
@login_required
def create_badge():
    if not current_user.is_admin():
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('gamification.index'))
    from app.models import Badge
    try:
        badge = Badge(
            name=request.form.get('name', '').strip(),
            description=request.form.get('description', '').strip(),
            icon=request.form.get('icon', 'bi-award').strip(),
            color=request.form.get('color', '#1877f2').strip(),
            category=request.form.get('category', 'custom').strip(),
            requirement_type=request.form.get('requirement_type', 'posts_count').strip(),
            requirement_value=int(request.form.get('requirement_value', 1)),
            points=int(request.form.get('points', 10)),
            is_active=True,
        )
        db.session.add(badge)
        db.session.commit()
        flash(f'Badge "{badge.name}" creato con successo!', 'success')
    except Exception:
        db.session.rollback()
        flash('Errore nella creazione del badge.', 'danger')
    return redirect(url_for('gamification.admin'))


@bp.route('/admin/badge/<int:badge_id>/toggle', methods=['POST'])
@login_required
def toggle_badge(badge_id):
    if not current_user.is_admin():
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('gamification.index'))
    from app.models import Badge
    badge = Badge.query.get_or_404(badge_id)
    badge.is_active = not badge.is_active
    db.session.commit()
    status = 'attivato' if badge.is_active else 'disattivato'
    flash(f'Badge "{badge.name}" {status}.', 'success')
    return redirect(url_for('gamification.admin'))


@bp.route('/admin/seed-defaults', methods=['POST'])
@login_required
def seed_defaults():
    if not current_user.is_admin():
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('gamification.index'))
    from app.gamification.engine import seed_default_badges
    count = seed_default_badges()
    flash(f'{count} badge predefiniti aggiunti.', 'success')
    return redirect(url_for('gamification.admin'))
