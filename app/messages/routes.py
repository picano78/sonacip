"""Direct messages routes - Internal messaging system"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import or_, and_, func
from app import db
from app.messages.forms import MessageForm
from app.models import Message, User
from app.notifications.utils import create_notification
from app.utils import check_permission

bp = Blueprint('messages', __name__, url_prefix='/messages')


def get_conversations():
    """Get all conversations for current user with last message and unread count"""
    conversations = []
    user_ids_seen = set()
    
    all_messages = Message.query.filter(
        or_(
            Message.sender_id == current_user.id,
            Message.recipient_id == current_user.id
        )
    ).order_by(Message.created_at.desc()).all()
    
    for msg in all_messages:
        other_id = msg.recipient_id if msg.sender_id == current_user.id else msg.sender_id
        if other_id not in user_ids_seen:
            user_ids_seen.add(other_id)
            other_user = User.query.get(other_id)
            if other_user:
                unread_count = Message.query.filter(
                    Message.sender_id == other_id,
                    Message.recipient_id == current_user.id,
                    Message.is_read == False
                ).count()
                conversations.append({
                    'user': other_user,
                    'last_message': msg,
                    'unread_count': unread_count
                })
    
    return conversations


@bp.route('/')
@login_required
def inbox():
    """Show conversations list"""
    conversations = get_conversations()
    return render_template('messages/conversations.html', 
                         conversations=conversations,
                         chat_user=None,
                         messages=[])


@bp.route('/chat/<int:user_id>')
@login_required
def chat(user_id):
    """View chat with specific user"""
    chat_user = User.query.get_or_404(user_id)
    
    if chat_user.id == current_user.id:
        flash('Non puoi chattare con te stesso.', 'warning')
        return redirect(url_for('messages.inbox'))
    
    messages = Message.query.filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == user_id),
            and_(Message.sender_id == user_id, Message.recipient_id == current_user.id)
        )
    ).order_by(Message.created_at.asc()).all()
    
    Message.query.filter(
        Message.sender_id == user_id,
        Message.recipient_id == current_user.id,
        Message.is_read == False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    
    conversations = get_conversations()
    
    return render_template('messages/conversations.html',
                         conversations=conversations,
                         chat_user=chat_user,
                         messages=messages)


@bp.route('/chat/<int:user_id>/send', methods=['POST'])
@login_required
def send_message(user_id):
    """Send message to user"""
    recipient = User.query.get_or_404(user_id)
    body = request.form.get('body', '').strip()
    
    if not body:
        flash('Il messaggio non può essere vuoto.', 'warning')
        return redirect(url_for('messages.chat', user_id=user_id))
    
    msg = Message(
        sender_id=current_user.id,
        recipient_id=recipient.id,
        body=body
    )
    db.session.add(msg)
    db.session.commit()
    
    create_notification(
        user_id=recipient.id,
        title='Nuovo messaggio',
        message=f'{current_user.get_full_name()}: {body[:50]}...' if len(body) > 50 else f'{current_user.get_full_name()}: {body}',
        notification_type='message',
        link=url_for('messages.chat', user_id=current_user.id)
    )
    
    return redirect(url_for('messages.chat', user_id=user_id))


@bp.route('/new')
@login_required
def new_chat():
    """Start a new chat - search for users"""
    q = request.args.get('q', '').strip()
    users = []
    
    if q:
        users = User.query.filter(
            User.id != current_user.id,
            or_(
                User.first_name.ilike(f'%{q}%'),
                User.last_name.ilike(f'%{q}%'),
                User.username.ilike(f'%{q}%')
            )
        ).limit(20).all()
    
    return render_template('messages/new_chat.html', users=users)


@bp.route('/start')
@login_required
def start_chat():
    """Redirect to new_chat with search query"""
    return redirect(url_for('messages.new_chat', q=request.args.get('q', '')))


@bp.route('/sent')
@login_required
def sent():
    """Redirect to inbox (conversations view)"""
    return redirect(url_for('messages.inbox'))


@bp.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    """Redirect to new chat"""
    return redirect(url_for('messages.new_chat'))


@bp.route('/view/<int:message_id>')
@login_required
def view_message(message_id):
    """View a single message - redirect to chat"""
    message = Message.query.get_or_404(message_id)
    
    if message.recipient_id != current_user.id and message.sender_id != current_user.id:
        if not check_permission(current_user, 'admin', 'access'):
            flash('Accesso negato.', 'danger')
            return redirect(url_for('messages.inbox'))
    
    other_user_id = message.sender_id if message.recipient_id == current_user.id else message.recipient_id
    return redirect(url_for('messages.chat', user_id=other_user_id))


@bp.route('/unread-count')
@login_required
def unread_count():
    """Get unread messages count (AJAX)"""
    count = Message.query.filter_by(
        recipient_id=current_user.id,
        is_read=False
    ).count()
    return jsonify({'count': count})
