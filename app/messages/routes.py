p"""Direct messages routes"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import or_
from app import db
from app.messages.forms import MessageForm
from app.models import Message, User
from app.notifications.utils import create_notification
from app.utils import check_permission

bp = Blueprint('messages', __name__, url_prefix='/messages')


@bp.route('/')
@login_required
def inbox():
    """List received messages"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    pagination = Message.query.filter_by(recipient_id=current_user.id).order_by(Message.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    messages = pagination.items
    return render_template('messages/inbox.html', messages=messages, pagination=pagination)


@bp.route('/sent')
@login_required
def sent():
    """List sent messages"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    pagination = Message.query.filter_by(sender_id=current_user.id).order_by(Message.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    messages = pagination.items
    return render_template('messages/sent.html', messages=messages, pagination=pagination)


@bp.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    """Compose a new message"""
    form = MessageForm()
    if form.validate_on_submit():
        recipient = User.query.filter(
            or_(
                User.email == form.recipient.data,
                User.username == form.recipient.data
            )
        ).first()
        if not recipient:
            flash('Destinatario non trovato.', 'danger')
            return redirect(url_for('messages.compose'))

        msg = Message(
            sender_id=current_user.id,
            recipient_id=recipient.id,
            subject=form.subject.data,
            body=form.body.data
        )
        db.session.add(msg)
        db.session.commit()

        create_notification(
            user_id=recipient.id,
            title='Nuovo messaggio',
            message=f'Hai ricevuto un nuovo messaggio da {current_user.get_full_name()}',
            notification_type='message',
            link=url_for('messages.view_message', message_id=msg.id)
        )

        flash('Messaggio inviato.', 'success')
        return redirect(url_for('messages.inbox'))

    return render_template('messages/compose.html', form=form)


@bp.route('/view/<int:message_id>')
@login_required
def view_message(message_id):
    """View a single message and mark as read"""
    message = Message.query.get_or_404(message_id)

    if message.recipient_id != current_user.id and message.sender_id != current_user.id and not check_permission(current_user, 'admin', 'access'):
        flash('Accesso negato.', 'danger')
        return redirect(url_for('messages.inbox'))

    if not message.is_read and message.recipient_id == current_user.id:
        message.is_read = True
        message.read_at = datetime.utcnow()
        db.session.commit()

    return render_template('messages/view.html', message=message)
