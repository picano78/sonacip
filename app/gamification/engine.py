from datetime import datetime, date
from app import db


LEVEL_THRESHOLDS = [
    (1, 0),
    (2, 100),
    (3, 300),
    (4, 600),
    (5, 1000),
    (6, 2000),
    (7, 4000),
    (8, 8000),
    (9, 15000),
    (10, 30000),
]


def get_level(points):
    level = 1
    for lvl, threshold in LEVEL_THRESHOLDS:
        if points >= threshold:
            level = lvl
    return level


def get_level_progress(points):
    level = get_level(points)
    current_threshold = 0
    next_threshold = 100
    for lvl, threshold in LEVEL_THRESHOLDS:
        if lvl == level:
            current_threshold = threshold
        if lvl == level + 1:
            next_threshold = threshold
            break
    else:
        if level >= 10:
            return 100
    if next_threshold <= current_threshold:
        return 100
    progress = ((points - current_threshold) / (next_threshold - current_threshold)) * 100
    return min(100, max(0, progress))


def get_next_level_points(points):
    level = get_level(points)
    for lvl, threshold in LEVEL_THRESHOLDS:
        if lvl == level + 1:
            return threshold
    return None


def get_or_create_user_points(user_id):
    from app.models import UserPoints
    try:
        up = UserPoints.query.filter_by(user_id=user_id).first()
        if not up:
            up = UserPoints(user_id=user_id, total_points=0, level=1)
            db.session.add(up)
            db.session.commit()
        return up
    except Exception:
        db.session.rollback()
        return None


def add_points(user_id, points, reason=''):
    try:
        up = get_or_create_user_points(user_id)
        if not up:
            return
        up.total_points = (up.total_points or 0) + points
        up.level = get_level(up.total_points)
        db.session.commit()
    except Exception:
        db.session.rollback()


def update_login_streak(user_id):
    try:
        up = get_or_create_user_points(user_id)
        if not up:
            return
        today = date.today()
        if up.last_login_date:
            diff = (today - up.last_login_date).days
            if diff == 1:
                up.login_streak = (up.login_streak or 0) + 1
            elif diff == 0:
                pass
            else:
                up.login_streak = 1
        else:
            up.login_streak = 1
        up.last_login_date = today
        db.session.commit()
        check_and_award_badges(user_id)
    except Exception:
        db.session.rollback()


def _get_user_stats(user_id):
    from app.models import Post, UserPoints
    stats = {
        'posts_count': 0,
        'events_attended': 0,
        'login_streak': 0,
        'connections': 0,
    }
    try:
        stats['posts_count'] = Post.query.filter_by(user_id=user_id).count()
    except Exception:
        pass
    try:
        from app.models import User
        user = db.session.get(User, user_id)
        if user:
            stats['connections'] = user.followed.count()
    except Exception:
        pass
    try:
        up = UserPoints.query.filter_by(user_id=user_id).first()
        if up:
            stats['events_attended'] = up.events_attended or 0
            stats['login_streak'] = up.login_streak or 0
            stats['posts_count'] = max(stats['posts_count'], up.posts_count or 0)
    except Exception:
        pass
    return stats


def check_and_award_badges(user_id):
    from app.models import Badge, UserBadge
    try:
        stats = _get_user_stats(user_id)
        badges = Badge.query.filter_by(is_active=True).all()
        for badge in badges:
            already = UserBadge.query.filter_by(user_id=user_id, badge_id=badge.id).first()
            if already:
                continue
            req_type = badge.requirement_type
            req_val = badge.requirement_value or 1
            earned = False
            if req_type == 'posts_count' and stats['posts_count'] >= req_val:
                earned = True
            elif req_type == 'events_attended' and stats['events_attended'] >= req_val:
                earned = True
            elif req_type == 'login_streak' and stats['login_streak'] >= req_val:
                earned = True
            elif req_type == 'connections' and stats['connections'] >= req_val:
                earned = True
            if earned:
                ub = UserBadge(user_id=user_id, badge_id=badge.id)
                db.session.add(ub)
                add_points(user_id, badge.points or 0, f'Badge: {badge.name}')
                up = get_or_create_user_points(user_id)
                if up:
                    up.badges_count = UserBadge.query.filter_by(user_id=user_id).count()
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_leaderboard(limit=20):
    from app.models import UserPoints, User
    try:
        entries = db.session.query(UserPoints, User).join(
            User, User.id == UserPoints.user_id
        ).filter(
            User.is_active == True
        ).order_by(UserPoints.total_points.desc()).limit(limit).all()
        return entries
    except Exception:
        return []


def get_badge_progress(user_id, badge):
    stats = _get_user_stats(user_id)
    req_type = badge.requirement_type
    req_val = badge.requirement_value or 1
    current = 0
    if req_type == 'posts_count':
        current = stats['posts_count']
    elif req_type == 'events_attended':
        current = stats['events_attended']
    elif req_type == 'login_streak':
        current = stats['login_streak']
    elif req_type == 'connections':
        current = stats['connections']
    pct = min(100, int((current / req_val) * 100)) if req_val > 0 else 0
    return current, req_val, pct


DEFAULT_BADGES = [
    {'name': 'Primo Post', 'description': 'Pubblica il tuo primo post', 'icon': 'bi-pencil-fill', 'color': '#1877f2', 'category': 'social', 'requirement_type': 'posts_count', 'requirement_value': 1, 'points': 10},
    {'name': 'Scrittore', 'description': 'Pubblica 10 post', 'icon': 'bi-journal-text', 'color': '#1877f2', 'category': 'social', 'requirement_type': 'posts_count', 'requirement_value': 10, 'points': 50},
    {'name': 'Autore Prolifico', 'description': 'Pubblica 50 post', 'icon': 'bi-book-fill', 'color': '#ffc107', 'category': 'social', 'requirement_type': 'posts_count', 'requirement_value': 50, 'points': 200},
    {'name': 'Partecipante', 'description': 'Partecipa al tuo primo evento', 'icon': 'bi-calendar-check-fill', 'color': '#28a745', 'category': 'eventi', 'requirement_type': 'events_attended', 'requirement_value': 1, 'points': 10},
    {'name': 'Sportivo Attivo', 'description': 'Partecipa a 10 eventi', 'icon': 'bi-lightning-fill', 'color': '#28a745', 'category': 'eventi', 'requirement_type': 'events_attended', 'requirement_value': 10, 'points': 100},
    {'name': 'Veterano', 'description': 'Partecipa a 50 eventi', 'icon': 'bi-star-fill', 'color': '#ffc107', 'category': 'eventi', 'requirement_type': 'events_attended', 'requirement_value': 50, 'points': 500},
    {'name': 'Costante', 'description': 'Accedi per 7 giorni consecutivi', 'icon': 'bi-fire', 'color': '#fd7e14', 'category': 'streak', 'requirement_type': 'login_streak', 'requirement_value': 7, 'points': 50},
    {'name': 'Dedicato', 'description': 'Accedi per 30 giorni consecutivi', 'icon': 'bi-flame', 'color': '#fd7e14', 'category': 'streak', 'requirement_type': 'login_streak', 'requirement_value': 30, 'points': 200},
    {'name': 'Leggenda', 'description': 'Accedi per 100 giorni consecutivi', 'icon': 'bi-gem', 'color': '#dc3545', 'category': 'streak', 'requirement_type': 'login_streak', 'requirement_value': 100, 'points': 1000},
    {'name': 'Primo Amico', 'description': 'Segui il tuo primo utente', 'icon': 'bi-person-plus-fill', 'color': '#6f42c1', 'category': 'social', 'requirement_type': 'connections', 'requirement_value': 1, 'points': 10},
    {'name': 'Sociale', 'description': 'Segui 10 utenti', 'icon': 'bi-people-fill', 'color': '#6f42c1', 'category': 'social', 'requirement_type': 'connections', 'requirement_value': 10, 'points': 50},
    {'name': 'Influencer', 'description': 'Segui 50 utenti', 'icon': 'bi-megaphone-fill', 'color': '#e83e8c', 'category': 'social', 'requirement_type': 'connections', 'requirement_value': 50, 'points': 200},
]


def seed_default_badges():
    from app.models import Badge
    count = 0
    try:
        for b_data in DEFAULT_BADGES:
            existing = Badge.query.filter_by(name=b_data['name']).first()
            if not existing:
                badge = Badge(**b_data)
                db.session.add(badge)
                count += 1
        db.session.commit()
    except Exception:
        db.session.rollback()
    return count
