"""
Notification routes
"""
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db, csrf
from app.models import Notification, PushSubscription
from datetime import datetime, timezone

bp = Blueprint('notifications', __name__, url_prefix='/notifications')


@bp.route('/')
@login_required
def index():
    """List all notifications"""
    page = request.args.get('page', 1, type=int)
    per_page = 30
    
    # Filter
    filter_type = request.args.get('filter', 'all')
    
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'read':
        query = query.filter_by(is_read=True)
    
    pagination = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    notifications = pagination.items
    
    return render_template('notifications/index.html',
                         notifications=notifications,
                         pagination=pagination,
                         filter_type=filter_type)


@bp.route('/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_read(notification_id):
    """Mark notification as read"""
    notification = Notification.query.get_or_404(notification_id)
    
    # Check ownership
    if notification.user_id != current_user.id:
        return jsonify({'success': False}), 403
    
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    return redirect(request.referrer or url_for('notifications.index'))


@bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications as read"""
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({
        'is_read': True,
        'read_at': datetime.now(timezone.utc)
    })
    db.session.commit()
    
    flash('Tutte le notifiche sono state contrassegnate come lette.', 'success')
    return redirect(url_for('notifications.index'))


@bp.route('/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete(notification_id):
    """Delete notification"""
    notification = Notification.query.get_or_404(notification_id)
    
    # Check ownership
    if notification.user_id != current_user.id:
        flash('Non autorizzato.', 'danger')
        return redirect(url_for('notifications.index'))
    
    db.session.delete(notification)
    db.session.commit()
    
    flash('Notifica eliminata.', 'success')
    return redirect(request.referrer or url_for('notifications.index'))


@bp.route('/clear-all', methods=['POST'])
@login_required
def clear_all():
    """Delete all read notifications"""
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=True
    ).delete()
    db.session.commit()
    
    flash('Notifiche lette eliminate.', 'success')
    return redirect(url_for('notifications.index'))


@bp.route('/unread-count')
@login_required
def unread_count():
    """Get unread notifications count (AJAX)"""
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return jsonify({'count': count})


@bp.route('/recent')
@login_required
def recent():
    """Get recent notifications (AJAX)"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'link': n.link,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat()
        } for n in notifications]
    })


@bp.route('/push/subscribe', methods=['POST'])
@csrf.exempt
@login_required
def push_subscribe():
    """Save push subscription for current user"""
    try:
        data = request.get_json(silent=True)
        if not data or not data.get('endpoint'):
            return jsonify({'success': False, 'error': 'Endpoint richiesto'}), 400

        endpoint = data['endpoint']
        keys = data.get('keys', {})
        p256dh = keys.get('p256dh', '')
        auth = keys.get('auth', '')

        existing = PushSubscription.query.filter_by(
            user_id=current_user.id,
            endpoint=endpoint
        ).first()

        if existing:
            existing.p256dh_key = p256dh
            existing.auth_key = auth
            existing.is_active = True
        else:
            sub = PushSubscription(
                user_id=current_user.id,
                endpoint=endpoint,
                p256dh_key=p256dh,
                auth_key=auth,
                is_active=True
            )
            db.session.add(sub)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/push/unsubscribe', methods=['POST'])
@csrf.exempt
@login_required
def push_unsubscribe():
    """Remove push subscription for current user"""
    try:
        data = request.get_json(silent=True)
        if not data or not data.get('endpoint'):
            return jsonify({'success': False, 'error': 'Endpoint richiesto'}), 400

        sub = PushSubscription.query.filter_by(
            user_id=current_user.id,
            endpoint=data['endpoint']
        ).first()

        if sub:
            db.session.delete(sub)
            db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/push/vapid-key')
@login_required
def push_vapid_key():
    """Return the VAPID public key"""
    vapid_key = os.environ.get('VAPID_PUBLIC_KEY', '')
    return jsonify({'publicKey': vapid_key})
