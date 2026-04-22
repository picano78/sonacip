"""
Message utilities for threading, search, and attachment handling
"""
import os
from werkzeug.utils import secure_filename
from flask import current_app
from app.models import Message, MessageThread, MessageAttachment
from app.storage import save_image_light
from app import db
from datetime import datetime, timezone


ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png', 'gif', 'zip', 'xlsx', 'xls'}
IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_attachment(file, message_id):
    """
    Save message attachment and create database record.
    Image attachments are automatically optimized.
    Returns MessageAttachment object or None if failed
    """
    if not file or not allowed_file(file.filename):
        return None

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    # Optimize image attachments through centralized storage
    if ext in IMAGE_EXTENSIONS:
        try:
            rel_path = save_image_light(file, folder='message_attachments', size=(1280, 1280))
            optimized_filename = os.path.basename(rel_path)
            upload_dir = os.path.join(current_app.root_path, 'uploads', 'message_attachments')
            file_path = os.path.join(upload_dir, optimized_filename)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            attachment = MessageAttachment(
                message_id=message_id,
                filename=optimized_filename,
                original_filename=filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=file.content_type
            )
            return attachment
        except (ValueError, RuntimeError):
            # Fall through to standard save if optimization fails
            file.seek(0)

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"

    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join(
        current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, 'uploads')),
        'message_attachments'
    )
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, unique_filename)
    file.save(file_path)

    # Get file size
    file_size = os.path.getsize(file_path)

    # Create attachment record
    attachment = MessageAttachment(
        message_id=message_id,
        filename=unique_filename,
        original_filename=filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type
    )

    return attachment


def get_or_create_thread(user1_id, user2_id):
    """
    Get existing thread or create new one for two users
    """
    # Ensure user1_id is always smaller for consistent lookup
    if user1_id > user2_id:
        user1_id, user2_id = user2_id, user1_id
    
    thread = MessageThread.query.filter_by(
        user1_id=user1_id,
        user2_id=user2_id
    ).first()
    
    if not thread:
        # Create new thread
        import hashlib
        thread_str = f"{user1_id}-{user2_id}"
        thread_id = hashlib.md5(thread_str.encode(), usedforsecurity=False).hexdigest()[:16]
        
        thread = MessageThread(
            thread_id=thread_id,
            user1_id=user1_id,
            user2_id=user2_id,
            message_count=0
        )
        db.session.add(thread)
    
    return thread


def update_thread_info(thread, message):
    """Update thread with latest message info"""
    thread.last_message_at = message.created_at
    thread.message_count += 1
    if message.subject and not thread.subject:
        thread.subject = message.subject


def search_messages(query_string, user_id):
    """
    Search messages for a user by content or sender name
    """
    from app.models import User
    from sqlalchemy import or_
    
    # Search in message body and subject
    messages = Message.query.filter(
        or_(
            Message.sender_id == user_id,
            Message.recipient_id == user_id
        ),
        or_(
            Message.body.ilike(f'%{query_string}%'),
            Message.subject.ilike(f'%{query_string}%')
        )
    ).order_by(Message.created_at.desc()).all()
    
    return messages


def get_thread_messages(thread_id, user_id):
    """Get all messages in a thread for a user"""
    from sqlalchemy import or_
    
    messages = Message.query.filter(
        Message.thread_id == thread_id,
        or_(
            Message.sender_id == user_id,
            Message.recipient_id == user_id
        )
    ).order_by(Message.created_at.asc()).all()
    
    return messages


def mark_thread_as_read(thread_id, user_id):
    """Mark all unread messages in a thread as read"""
    Message.query.filter(
        Message.thread_id == thread_id,
        Message.recipient_id == user_id,
        Message.is_read == False
    ).update({'is_read': True, 'read_at': datetime.now(timezone.utc)})
    
    db.session.commit()


def delete_message_for_user(message_id, user_id):
    """Soft delete message for a specific user"""
    message = db.session.get(Message, message_id)
    if not message:
        return False
    
    if message.sender_id == user_id:
        message.is_deleted_by_sender = True
    elif message.recipient_id == user_id:
        message.is_deleted_by_recipient = True
    else:
        return False
    
    db.session.commit()
    return True


def archive_thread_for_user(thread_id, user_id):
    """Archive thread for a specific user"""
    thread = MessageThread.query.filter_by(thread_id=thread_id).first()
    if not thread:
        return False
    
    if thread.user1_id == user_id:
        thread.user1_archived = True
    elif thread.user2_id == user_id:
        thread.user2_archived = True
    else:
        return False
    
    db.session.commit()
    return True


def get_user_message_stats(user_id):
    """Get message statistics for a user"""
    total_sent = Message.query.filter_by(sender_id=user_id).count()
    total_received = Message.query.filter_by(recipient_id=user_id).count()
    unread = Message.query.filter_by(recipient_id=user_id, is_read=False).count()
    
    return {
        'total_sent': total_sent,
        'total_received': total_received,
        'unread': unread,
        'total': total_sent + total_received
    }


def cleanup_expired_photos():
    """
    Delete expired ephemeral message photos from disk and database.
    Called by the Celery periodic task and can be invoked directly in tests.
    """
    import os
    from app.models import MessageGroupMessage

    now = datetime.now(timezone.utc)
    deleted_dm = 0
    deleted_group = 0

    # Clean up direct message photo attachments
    expired_attachments = MessageAttachment.query.filter(
        MessageAttachment.expires_at.isnot(None),
        MessageAttachment.expires_at <= now
    ).all()

    for att in expired_attachments:
        try:
            if att.file_path and os.path.exists(att.file_path):
                os.remove(att.file_path)
        except OSError:
            pass
        db.session.delete(att)
        deleted_dm += 1

    # Clean up group message photos
    expired_group_msgs = MessageGroupMessage.query.filter(
        MessageGroupMessage.photo_path.isnot(None),
        MessageGroupMessage.photo_expires_at.isnot(None),
        MessageGroupMessage.photo_expires_at <= now
    ).all()

    for msg in expired_group_msgs:
        try:
            from app.storage import _media_root
            full_path = os.path.join(_media_root(), msg.photo_path)
            if os.path.exists(full_path):
                os.remove(full_path)
        except (OSError, RuntimeError):
            pass
        msg.photo_path = None
        msg.photo_expires_at = None
        deleted_group += 1

    db.session.commit()
    return {'dm_photos_deleted': deleted_dm, 'group_photos_deleted': deleted_group}
