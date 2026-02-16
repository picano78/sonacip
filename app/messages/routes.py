"""Direct messages routes - Internal messaging system"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, timezone
from sqlalchemy import or_, and_, func
import os
import secrets
from werkzeug.utils import secure_filename
from app import db
from app.messages.forms import MessageForm, MessageGroupForm
from app.models import Message, User, MessageGroup, MessageGroupMembership, MessageGroupMessage
from app.notifications.utils import create_notification
from app.utils import check_permission
from app.storage import save_image_light

bp = Blueprint('messages', __name__, url_prefix='/messages')


def get_conversations():
    """Get all conversations for current user with last message and unread count"""
    conversations = []
    user_ids_seen = set()
    
    # Get direct message conversations
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
            other_user = db.session.get(User, other_id)
            if other_user:
                unread_count = Message.query.filter(
                    Message.sender_id == other_id,
                    Message.recipient_id == current_user.id,
                    Message.is_read == False
                ).count()
                conversations.append({
                    'type': 'direct',
                    'user': other_user,
                    'last_message': msg,
                    'unread_count': unread_count,
                    'sort_time': msg.created_at
                })
    
    # Get group chat conversations with eager loading
    from sqlalchemy.orm import joinedload
    group_memberships = MessageGroupMembership.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).options(joinedload(MessageGroupMembership.group)).all()
    
    for membership in group_memberships:
        group = membership.group
        if group:
            last_message = MessageGroupMessage.query.filter_by(
                group_id=group.id
            ).options(joinedload(MessageGroupMessage.sender)).order_by(
                MessageGroupMessage.created_at.desc()
            ).first()
            
            # Count unread messages (simplified - in real app would track read status per user)
            unread_count = 0
            
            conversations.append({
                'type': 'group',
                'group': group,
                'last_message': last_message,
                'unread_count': unread_count,
                'member_count': group.member_count(),
                'sort_time': last_message.created_at if last_message else group.created_at
            })
    
    # Sort all conversations by last message time
    conversations.sort(key=lambda x: x['sort_time'], reverse=True)
    
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
    """Redirect to chat with user or new chat search"""
    to_user_id = request.args.get('to', type=int)
    if to_user_id:
        # Redirect to chat with specific user
        recipient = db.session.get(User, to_user_id)
        if recipient:
            return redirect(url_for('messages.chat', user_id=to_user_id))
        flash('Utente non trovato.', 'warning')
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
    
    message = db.session.get(Message, message_id)
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


# ==================== GROUP CHAT ROUTES ====================

def save_group_avatar(file):
    """Save group avatar image with optimization."""
    if not file or not file.filename:
        return None

    try:
        return save_image_light(file, folder='group_avatars', size=(300, 300))
    except (ValueError, RuntimeError) as e:
        current_app.logger.warning(f"Group avatar save failed: {e}")
        return None


@bp.route('/groups/create', methods=['GET', 'POST'])
@login_required
def create_group():
    """Create a new message group"""
    form = MessageGroupForm()
    
    if form.validate_on_submit():
        # Save avatar if provided
        avatar_path = None
        if form.avatar.data:
            avatar_path = save_group_avatar(form.avatar.data)
        
        # Create group
        group = MessageGroup(
            name=form.name.data,
            description=form.description.data,
            avatar=avatar_path,
            creator_id=current_user.id,
            max_members=form.max_members.data or 256,
            is_announcement_only=form.is_announcement_only.data
        )
        db.session.add(group)
        db.session.flush()
        
        # Add creator as admin member
        membership = MessageGroupMembership(
            group_id=group.id,
            user_id=current_user.id,
            is_admin=True
        )
        db.session.add(membership)
        
        # Create system message
        system_msg = MessageGroupMessage(
            group_id=group.id,
            sender_id=current_user.id,
            body=f"Gruppo creato da {current_user.get_full_name()}",
            is_system_message=True
        )
        db.session.add(system_msg)
        
        db.session.commit()
        
        flash(f'Gruppo "{group.name}" creato con successo!', 'success')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    return render_template('messages/create_group.html', form=form)


@bp.route('/groups/<int:group_id>')
@login_required
def group_chat(group_id):
    """View a group chat"""
    group = MessageGroup.query.get_or_404(group_id)
    
    # Check if user is a member
    membership = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not membership:
        flash('Non sei membro di questo gruppo.', 'warning')
        return redirect(url_for('messages.inbox'))
    
    # Get messages with sender info (eager loading)
    from sqlalchemy.orm import joinedload
    messages = MessageGroupMessage.query.filter_by(
        group_id=group.id
    ).options(joinedload(MessageGroupMessage.sender)).order_by(
        MessageGroupMessage.created_at.asc()
    ).all()
    
    # Get members with user info (eager loading)
    members = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        is_active=True
    ).options(joinedload(MessageGroupMembership.user)).all()
    
    member_users = []
    for m in members:
        if m.user:
            member_users.append({
                'user': m.user,
                'is_admin': m.is_admin,
                'membership': m
            })
    
    # Get conversations for sidebar
    conversations = get_conversations()
    
    return render_template('messages/group_chat.html',
                         group=group,
                         messages=messages,
                         members=member_users,
                         membership=membership,
                         conversations=conversations)


@bp.route('/groups/<int:group_id>/send', methods=['POST'])
@login_required
def send_group_message(group_id):
    """Send a message to a group"""
    group = MessageGroup.query.get_or_404(group_id)
    
    # Check membership
    membership = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not membership:
        flash('Non sei membro di questo gruppo.', 'danger')
        return redirect(url_for('messages.inbox'))
    
    # Check if announcement only
    if group.is_announcement_only and not membership.is_admin:
        flash('Solo gli amministratori possono inviare messaggi in questo gruppo.', 'warning')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    body = request.form.get('body', '').strip()
    if not body:
        flash('Il messaggio non può essere vuoto.', 'warning')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    # Create message
    msg = MessageGroupMessage(
        group_id=group.id,
        sender_id=current_user.id,
        body=body
    )
    db.session.add(msg)
    
    # Update group's last message time
    group.last_message_at = datetime.now(timezone.utc)
    db.session.commit()
    
    # Notify other members (simplified - would use proper notification system)
    other_members = MessageGroupMembership.query.filter(
        MessageGroupMembership.group_id == group.id,
        MessageGroupMembership.user_id != current_user.id,
        MessageGroupMembership.is_active == True,
        MessageGroupMembership.is_muted == False
    ).all()
    
    for member in other_members:
        create_notification(
            user_id=member.user_id,
            title=f'Nuovo messaggio in {group.name}',
            message=f'{current_user.get_full_name()}: {body[:50]}...' if len(body) > 50 else f'{current_user.get_full_name()}: {body}',
            notification_type='group_message',
            link=url_for('messages.group_chat', group_id=group.id)
        )
    
    return redirect(url_for('messages.group_chat', group_id=group.id))


@bp.route('/groups/<int:group_id>/add-members', methods=['GET', 'POST'])
@login_required
def add_group_members(group_id):
    """Add members to a group"""
    group = MessageGroup.query.get_or_404(group_id)
    
    # Check if user is admin
    membership = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not membership or not membership.is_admin:
        flash('Solo gli amministratori possono aggiungere membri.', 'danger')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    if request.method == 'POST':
        user_ids = request.form.getlist('user_ids')
        
        if not user_ids:
            flash('Seleziona almeno un utente.', 'warning')
            return redirect(url_for('messages.add_group_members', group_id=group.id))
        
        # Check max members
        current_count = MessageGroupMembership.query.filter_by(
            group_id=group.id,
            is_active=True
        ).count()
        
        if current_count + len(user_ids) > group.max_members:
            flash(f'Il gruppo può avere massimo {group.max_members} membri.', 'warning')
            return redirect(url_for('messages.add_group_members', group_id=group.id))
        
        added_count = 0
        for user_id in user_ids:
            # Check if already a member
            existing = MessageGroupMembership.query.filter_by(
                group_id=group.id,
                user_id=int(user_id)
            ).first()
            
            if not existing:
                new_member = MessageGroupMembership(
                    group_id=group.id,
                    user_id=int(user_id),
                    is_admin=False
                )
                db.session.add(new_member)
                
                # Create system message
                user = db.session.get(User, int(user_id))
                if user:
                    system_msg = MessageGroupMessage(
                        group_id=group.id,
                        sender_id=current_user.id,
                        body=f"{user.get_full_name()} è stato aggiunto al gruppo",
                        is_system_message=True
                    )
                    db.session.add(system_msg)
                    added_count += 1
                    
                    # Notify the new member
                    create_notification(
                        user_id=int(user_id),
                        title=f'Aggiunto a {group.name}',
                        message=f'{current_user.get_full_name()} ti ha aggiunto al gruppo {group.name}',
                        notification_type='group_added',
                        link=url_for('messages.group_chat', group_id=group.id)
                    )
            elif not existing.is_active:
                # Reactivate membership
                existing.is_active = True
                existing.joined_at = datetime.now(timezone.utc)
                existing.left_at = None
                added_count += 1
        
        db.session.commit()
        
        flash(f'{added_count} membri aggiunti al gruppo.', 'success')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    # GET request - show user selection
    # Get users that are not already members
    existing_member_ids = [m.user_id for m in MessageGroupMembership.query.filter_by(
        group_id=group.id,
        is_active=True
    ).all()]
    
    available_users = User.query.filter(
        User.id != current_user.id,
        ~User.id.in_(existing_member_ids)
    ).order_by(User.first_name, User.last_name).limit(100).all()
    
    return render_template('messages/add_group_members.html', 
                         group=group, 
                         available_users=available_users)


@bp.route('/groups/<int:group_id>/leave', methods=['POST'])
@login_required
def leave_group(group_id):
    """Leave a group"""
    group = MessageGroup.query.get_or_404(group_id)
    
    membership = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not membership:
        flash('Non sei membro di questo gruppo.', 'warning')
        return redirect(url_for('messages.inbox'))
    
    # Don't allow creator to leave if they're the only admin
    if group.creator_id == current_user.id:
        admin_count = MessageGroupMembership.query.filter_by(
            group_id=group.id,
            is_admin=True,
            is_active=True
        ).count()
        
        if admin_count == 1:
            flash('Non puoi lasciare il gruppo perché sei l\'unico amministratore. Promuovi prima un altro membro.', 'warning')
            return redirect(url_for('messages.group_chat', group_id=group.id))
    
    # Mark as inactive
    membership.is_active = False
    membership.left_at = datetime.now(timezone.utc)
    
    # Create system message
    system_msg = MessageGroupMessage(
        group_id=group.id,
        sender_id=current_user.id,
        body=f"{current_user.get_full_name()} ha lasciato il gruppo",
        is_system_message=True
    )
    db.session.add(system_msg)
    db.session.commit()
    
    flash('Hai lasciato il gruppo.', 'info')
    return redirect(url_for('messages.inbox'))


@bp.route('/groups/<int:group_id>/remove-member/<int:user_id>', methods=['POST'])
@login_required
def remove_group_member(group_id, user_id):
    """Remove a member from a group"""
    group = MessageGroup.query.get_or_404(group_id)
    
    # Check if current user is admin
    admin_membership = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not admin_membership or not admin_membership.is_admin:
        flash('Solo gli amministratori possono rimuovere membri.', 'danger')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    # Can't remove creator
    if user_id == group.creator_id:
        flash('Non puoi rimuovere il creatore del gruppo.', 'danger')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    membership = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        user_id=user_id,
        is_active=True
    ).first()
    
    if not membership:
        flash('Utente non trovato nel gruppo.', 'warning')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    # Mark as inactive
    membership.is_active = False
    membership.left_at = datetime.now(timezone.utc)
    
    # Create system message
    user = db.session.get(User, user_id)
    if user:
        system_msg = MessageGroupMessage(
            group_id=group.id,
            sender_id=current_user.id,
            body=f"{user.get_full_name()} è stato rimosso dal gruppo",
            is_system_message=True
        )
        db.session.add(system_msg)
    
    db.session.commit()
    
    flash('Membro rimosso dal gruppo.', 'success')
    return redirect(url_for('messages.group_chat', group_id=group.id))


@bp.route('/groups/<int:group_id>/promote/<int:user_id>', methods=['POST'])
@login_required
def promote_group_member(group_id, user_id):
    """Promote a member to admin"""
    group = MessageGroup.query.get_or_404(group_id)
    
    # Check if current user is admin
    admin_membership = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not admin_membership or not admin_membership.is_admin:
        flash('Solo gli amministratori possono promuovere membri.', 'danger')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    membership = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        user_id=user_id,
        is_active=True
    ).first()
    
    if not membership:
        flash('Utente non trovato nel gruppo.', 'warning')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    if membership.is_admin:
        # Demote
        membership.is_admin = False
        flash('Amministratore degradato a membro.', 'info')
    else:
        # Promote
        membership.is_admin = True
        flash('Membro promosso ad amministratore.', 'success')
    
    db.session.commit()
    
    return redirect(url_for('messages.group_chat', group_id=group.id))


@bp.route('/groups/<int:group_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_group(group_id):
    """Edit group settings"""
    group = MessageGroup.query.get_or_404(group_id)
    
    # Check if user is admin
    membership = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not membership or not membership.is_admin:
        flash('Solo gli amministratori possono modificare il gruppo.', 'danger')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    form = MessageGroupForm(obj=group)
    
    if form.validate_on_submit():
        group.name = form.name.data
        group.description = form.description.data
        group.is_announcement_only = form.is_announcement_only.data
        
        # Update avatar if provided
        if form.avatar.data:
            avatar_path = save_group_avatar(form.avatar.data)
            if avatar_path:
                group.avatar = avatar_path
        
        group.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        flash('Gruppo aggiornato con successo.', 'success')
        return redirect(url_for('messages.group_chat', group_id=group.id))
    
    return render_template('messages/edit_group.html', form=form, group=group)


# ==================== VIDEO CALL ROUTES ====================


@bp.route('/chat/<int:user_id>/video-call')
@login_required
def video_call(user_id):
    """Start a video call with another user in direct messaging"""
    other_user = User.query.get_or_404(user_id)
    
    if other_user.id == current_user.id:
        flash('Non puoi chiamare te stesso.', 'warning')
        return redirect(url_for('messages.inbox'))
    
    # Generate a unique room ID for the call
    room_id = secrets.token_urlsafe(16)
    
    return render_template('messages/video_call.html',
                         call_type='direct',
                         other_user=other_user,
                         room_id=room_id,
                         group=None)


@bp.route('/groups/<int:group_id>/video-call')
@login_required
def group_video_call(group_id):
    """Start a video call in a group chat"""
    group = MessageGroup.query.get_or_404(group_id)
    
    # Check membership
    membership = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not membership:
        flash('Non sei membro di questo gruppo.', 'warning')
        return redirect(url_for('messages.inbox'))
    
    # Generate a unique room ID for the group call
    room_id = secrets.token_urlsafe(16)
    
    # Get active members for the call
    from sqlalchemy.orm import joinedload
    members = MessageGroupMembership.query.filter_by(
        group_id=group.id,
        is_active=True
    ).options(joinedload(MessageGroupMembership.user)).all()
    
    member_users = [m.user for m in members if m.user]
    
    return render_template('messages/video_call.html',
                         call_type='group',
                         other_user=None,
                         room_id=room_id,
                         group=group,
                         members=member_users)

