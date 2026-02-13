"""Direct messages routes - Internal messaging system"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timezone
from sqlalchemy import or_, and_, func
import os
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


@bp.route('/conversations')
@login_required
def conversations():
    """
    Compatibility endpoint.

    Some templates/older links use `messages.conversations` with `?to=<user_id>`.
    Redirect to the proper chat or inbox.
    """
    to_raw = (request.args.get('to') or '').strip()
    if to_raw.isdigit():
        return redirect(url_for('messages.chat', user_id=int(to_raw)))
    return redirect(url_for('messages.inbox'))


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
    ).update({'is_read': True, 'read_at': datetime.now(timezone.utc)})
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


@bp.route('/search')
@login_required
def search():
    """Search messages by content"""
    from app.messages.utils import search_messages
    
    query = request.args.get('q', '').strip()
    results = []
    
    if query:
        results = search_messages(query, current_user.id)
    
    return render_template('messages/search.html', query=query, results=results)


@bp.route('/archive/<int:message_id>', methods=['POST'])
@login_required
def archive_message(message_id):
    """Archive a message"""
    message = Message.query.get_or_404(message_id)
    
    # Check permissions
    if message.sender_id != current_user.id and message.recipient_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    message.is_archived = True
    db.session.commit()
    
    return jsonify({'success': True})


@bp.route('/star/<int:message_id>', methods=['POST'])
@login_required
def star_message(message_id):
    """Star/unstar a message"""
    message = Message.query.get_or_404(message_id)
    
    # Check permissions
    if message.sender_id != current_user.id and message.recipient_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    message.is_starred = not message.is_starred
    db.session.commit()
    
    return jsonify({'success': True, 'starred': message.is_starred})


@bp.route('/delete/<int:message_id>', methods=['POST'])
@login_required
def delete_message(message_id):
    """Soft delete a message for current user"""
    from app.messages.utils import delete_message_for_user
    
    success = delete_message_for_user(message_id, current_user.id)
    
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Message not found or unauthorized'}), 404


@bp.route('/upload-attachment', methods=['POST'])
@login_required
def upload_attachment():
    """Upload file attachment for a message"""
    from app.messages.utils import save_attachment, allowed_file, MAX_FILE_SIZE
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    message_id = request.form.get('message_id', type=int)
    
    if not message_id:
        return jsonify({'error': 'Message ID required'}), 400
    
    message = Message.query.get(message_id)
    if not message or (message.sender_id != current_user.id and message.recipient_id != current_user.id):
        return jsonify({'error': 'Unauthorized'}), 403
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({'error': 'File too large. Maximum size is 10MB'}), 400
    
    # Save attachment
    attachment = save_attachment(file, message_id)
    
    if attachment:
        db.session.add(attachment)
        
        # Update message
        message.has_attachment = True
        message.attachment_count = message.attachments.count() + 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'attachment_id': attachment.id,
            'filename': attachment.original_filename,
            'size': attachment.file_size
        })
    else:
        return jsonify({'error': 'Failed to save attachment'}), 500


@bp.route('/download-attachment/<int:attachment_id>')
@login_required
def download_attachment(attachment_id):
    """Download message attachment"""
    from flask import send_file
    from app.models import MessageAttachment
    
    attachment = MessageAttachment.query.get_or_404(attachment_id)
    message = attachment.message
    
    # Check permissions
    if message.sender_id != current_user.id and message.recipient_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('messages.inbox'))
    
    return send_file(
        attachment.file_path,
        as_attachment=True,
        download_name=attachment.original_filename
    )


@bp.route('/stats')
@login_required
def message_stats():
    """Get message statistics for current user"""
    from app.messages.utils import get_user_message_stats
    
    stats = get_user_message_stats(current_user.id)
    
    if request.args.get('json'):
        return jsonify(stats)
    
    return render_template('messages/stats.html', stats=stats)

