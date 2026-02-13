"""
Real-time Notification System with WebSockets
Provides instant notifications to users without page refresh
"""
from flask import request
from flask_socketio import emit, join_room, leave_room, rooms
from flask_login import current_user
from app import socketio, db
from app.models import Notification, User
from datetime import datetime, timezone
import json


# Track connected users
connected_users = {}


@socketio.on('connect', namespace='/notifications')
def handle_connect():
    """Handle client connection"""
    if current_user.is_authenticated:
        user_id = str(current_user.id)
        room = f"user_{user_id}"
        
        # Join user-specific room
        join_room(room)
        
        # Track connection
        if user_id not in connected_users:
            connected_users[user_id] = []
        connected_users[user_id].append(request.sid)
        
        # Send unread count
        unread_count = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).count()
        
        emit('connected', {
            'status': 'connected',
            'user_id': user_id,
            'unread_count': unread_count
        })
        
        print(f"User {user_id} connected to notifications (session: {request.sid})")
    else:
        emit('error', {'message': 'Authentication required'})
        return False


@socketio.on('disconnect', namespace='/notifications')
def handle_disconnect():
    """Handle client disconnection"""
    if current_user.is_authenticated:
        user_id = str(current_user.id)
        room = f"user_{user_id}"
        
        # Leave room
        leave_room(room)
        
        # Remove from tracking
        if user_id in connected_users:
            if request.sid in connected_users[user_id]:
                connected_users[user_id].remove(request.sid)
            if not connected_users[user_id]:
                del connected_users[user_id]
        
        print(f"User {user_id} disconnected from notifications")


@socketio.on('mark_read', namespace='/notifications')
def handle_mark_read(data):
    """Mark notification as read"""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'})
        return
    
    notification_id = data.get('notification_id')
    
    try:
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=current_user.id
        ).first()
        
        if notification:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            db.session.commit()
            
            # Send updated unread count
            unread_count = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count()
            
            emit('notification_read', {
                'notification_id': notification_id,
                'unread_count': unread_count
            })
        else:
            emit('error', {'message': 'Notification not found'})
    
    except Exception as e:
        db.session.rollback()
        emit('error', {'message': str(e)})


@socketio.on('mark_all_read', namespace='/notifications')
def handle_mark_all_read():
    """Mark all notifications as read"""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'})
        return
    
    try:
        Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).update({
            'is_read': True,
            'read_at': datetime.now(timezone.utc)
        })
        db.session.commit()
        
        emit('all_notifications_read', {'unread_count': 0})
    
    except Exception as e:
        db.session.rollback()
        emit('error', {'message': str(e)})


@socketio.on('get_notifications', namespace='/notifications')
def handle_get_notifications(data):
    """Get user notifications"""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'})
        return
    
    limit = data.get('limit', 20)
    offset = data.get('offset', 0)
    
    try:
        notifications = Notification.query.filter_by(
            user_id=current_user.id
        ).order_by(
            Notification.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        notifications_data = [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'notification_type': n.notification_type,
            'link': n.link,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat() if n.created_at else None
        } for n in notifications]
        
        emit('notifications_list', {
            'notifications': notifications_data,
            'count': len(notifications_data)
        })
    
    except Exception as e:
        emit('error', {'message': str(e)})


# Helper functions to send real-time notifications

def send_realtime_notification(user_id, notification_data):
    """
    Send real-time notification to a user
    
    Args:
        user_id: User ID to send notification to
        notification_data: Dictionary with notification details
    """
    room = f"user_{user_id}"
    
    # Get updated unread count
    unread_count = Notification.query.filter_by(
        user_id=user_id,
        is_read=False
    ).count()
    
    notification_data['unread_count'] = unread_count
    
    socketio.emit('new_notification', notification_data, 
                  room=room, namespace='/notifications')


def broadcast_notification(user_ids, notification_data):
    """
    Broadcast notification to multiple users
    
    Args:
        user_ids: List of user IDs
        notification_data: Dictionary with notification details
    """
    for user_id in user_ids:
        send_realtime_notification(user_id, notification_data)


def notify_followers_realtime(user, notification_data):
    """
    Send real-time notification to all followers
    
    Args:
        user: User object
        notification_data: Dictionary with notification details
    """
    if not hasattr(user, 'followers'):
        return
    
    follower_ids = [follower.id for follower in user.followers]
    broadcast_notification(follower_ids, notification_data)


def is_user_online(user_id):
    """Check if user is connected to WebSocket"""
    return str(user_id) in connected_users


def get_online_users():
    """Get list of online user IDs"""
    return list(connected_users.keys())


def get_online_count():
    """Get count of online users"""
    return len(connected_users)


# Typing indicator support

@socketio.on('typing_start', namespace='/notifications')
def handle_typing_start(data):
    """User started typing"""
    if not current_user.is_authenticated:
        return
    
    target_user_id = data.get('target_user_id')
    if target_user_id:
        room = f"user_{target_user_id}"
        emit('user_typing', {
            'user_id': current_user.id,
            'username': current_user.username
        }, room=room)


@socketio.on('typing_stop', namespace='/notifications')
def handle_typing_stop(data):
    """User stopped typing"""
    if not current_user.is_authenticated:
        return
    
    target_user_id = data.get('target_user_id')
    if target_user_id:
        room = f"user_{target_user_id}"
        emit('user_stopped_typing', {
            'user_id': current_user.id
        }, room=room)


# Presence system

@socketio.on('update_presence', namespace='/notifications')
def handle_update_presence(data):
    """Update user presence status"""
    if not current_user.is_authenticated:
        return
    
    status = data.get('status', 'online')  # online, away, busy, offline
    
    try:
        current_user.presence_status = status
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()
        
        # Notify followers about presence change
        if hasattr(current_user, 'followers'):
            follower_ids = [f.id for f in current_user.followers]
            for follower_id in follower_ids:
                room = f"user_{follower_id}"
                emit('presence_update', {
                    'user_id': current_user.id,
                    'username': current_user.username,
                    'status': status
                }, room=room)
    
    except Exception as e:
        db.session.rollback()
        emit('error', {'message': str(e)})
