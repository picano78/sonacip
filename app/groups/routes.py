"""
Groups & Community routes
"""
import os
import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_
from app import db, csrf
from app.models import Group, GroupMembership, GroupMessage, User
from werkzeug.utils import secure_filename

bp = Blueprint('groups', __name__, url_prefix='/groups')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def save_group_picture(form_picture, subfolder='groups'):
    if not form_picture or not hasattr(form_picture, 'filename') or not form_picture.filename:
        return None
    filename = secure_filename(form_picture.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'png'
    if ext not in ALLOWED_EXTENSIONS:
        return None
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(current_app.root_path, '..', 'uploads', subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, unique_name)
    form_picture.save(filepath)
    return f"uploads/{subfolder}/{unique_name}"


@bp.route('/')
def index():
    search = request.args.get('q', '').strip()
    query = Group.query

    if search:
        query = query.filter(Group.name.ilike(f'%{search}%'))

    if current_user.is_authenticated:
        user_group_ids = [m.group_id for m in GroupMembership.query.filter_by(user_id=current_user.id).all()]
        query = query.filter(
            or_(Group.is_private == False, Group.id.in_(user_group_ids))
        )
    else:
        query = query.filter(Group.is_private == False)

    groups = query.order_by(Group.created_at.desc()).all()

    user_memberships = {}
    if current_user.is_authenticated:
        for m in GroupMembership.query.filter_by(user_id=current_user.id).all():
            user_memberships[m.group_id] = m.role

    return render_template('groups/index.html', groups=groups, search=search, user_memberships=user_memberships)


@bp.route('/my')
@login_required
def my_groups():
    memberships = GroupMembership.query.filter_by(user_id=current_user.id).all()
    groups_data = []
    for m in memberships:
        group = Group.query.get(m.group_id)
        if group:
            groups_data.append({'group': group, 'role': m.role})
    return render_template('groups/my_groups.html', groups_data=groups_data)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        is_private = request.form.get('is_private') == 'on'
        max_members = request.form.get('max_members', 100, type=int)

        if not name:
            flash('Il nome del gruppo è obbligatorio.', 'danger')
            return redirect(url_for('groups.create'))

        if len(name) > 120:
            flash('Il nome del gruppo non può superare 120 caratteri.', 'danger')
            return redirect(url_for('groups.create'))

        avatar_path = None
        if 'avatar' in request.files:
            avatar_path = save_group_picture(request.files['avatar'])

        group = Group(
            name=name,
            description=description,
            creator_id=current_user.id,
            is_private=is_private,
            max_members=max_members if max_members and max_members > 0 else 100,
            avatar=avatar_path,
        )
        db.session.add(group)
        db.session.flush()

        membership = GroupMembership(
            group_id=group.id,
            user_id=current_user.id,
            role='admin',
        )
        db.session.add(membership)
        db.session.commit()

        flash('Gruppo creato con successo!', 'success')
        return redirect(url_for('groups.detail', group_id=group.id))

    return render_template('groups/create.html')


@bp.route('/<int:group_id>')
def detail(group_id):
    group = Group.query.get_or_404(group_id)

    if group.is_private and current_user.is_authenticated:
        membership = GroupMembership.query.filter_by(group_id=group.id, user_id=current_user.id).first()
        if not membership:
            flash('Questo gruppo è privato.', 'warning')
            return redirect(url_for('groups.index'))
    elif group.is_private:
        flash('Questo gruppo è privato.', 'warning')
        return redirect(url_for('groups.index'))

    messages = GroupMessage.query.filter_by(group_id=group.id).order_by(GroupMessage.created_at.asc()).all()
    members = GroupMembership.query.filter_by(group_id=group.id).all()

    member_users = []
    for m in members:
        user = User.query.get(m.user_id)
        if user:
            member_users.append({'user': user, 'role': m.role, 'membership': m})

    is_member = False
    user_role = None
    if current_user.is_authenticated:
        user_membership = GroupMembership.query.filter_by(group_id=group.id, user_id=current_user.id).first()
        if user_membership:
            is_member = True
            user_role = user_membership.role

    return render_template('groups/detail.html',
                           group=group,
                           messages=messages,
                           member_users=member_users,
                           is_member=is_member,
                           user_role=user_role)


@bp.route('/<int:group_id>/join', methods=['POST'])
@login_required
def join(group_id):
    group = Group.query.get_or_404(group_id)

    existing = GroupMembership.query.filter_by(group_id=group.id, user_id=current_user.id).first()
    if existing:
        flash('Sei già membro di questo gruppo.', 'info')
        return redirect(url_for('groups.detail', group_id=group.id))

    member_count = GroupMembership.query.filter_by(group_id=group.id).count()
    if group.max_members and member_count >= group.max_members:
        flash('Il gruppo ha raggiunto il numero massimo di membri.', 'warning')
        return redirect(url_for('groups.detail', group_id=group.id))

    membership = GroupMembership(
        group_id=group.id,
        user_id=current_user.id,
        role='member',
    )
    db.session.add(membership)
    db.session.commit()

    flash('Sei entrato nel gruppo!', 'success')
    return redirect(url_for('groups.detail', group_id=group.id))


@bp.route('/<int:group_id>/leave', methods=['POST'])
@login_required
def leave(group_id):
    group = Group.query.get_or_404(group_id)

    membership = GroupMembership.query.filter_by(group_id=group.id, user_id=current_user.id).first()
    if not membership:
        flash('Non sei membro di questo gruppo.', 'warning')
        return redirect(url_for('groups.detail', group_id=group.id))

    if membership.role == 'admin' and group.creator_id == current_user.id:
        flash('Il creatore del gruppo non può abbandonarlo. Elimina il gruppo se necessario.', 'warning')
        return redirect(url_for('groups.detail', group_id=group.id))

    db.session.delete(membership)
    db.session.commit()

    flash('Hai lasciato il gruppo.', 'info')
    return redirect(url_for('groups.index'))


@bp.route('/<int:group_id>/message', methods=['POST'])
@login_required
def post_message(group_id):
    group = Group.query.get_or_404(group_id)

    membership = GroupMembership.query.filter_by(group_id=group.id, user_id=current_user.id).first()
    if not membership:
        flash('Devi essere membro per inviare messaggi.', 'danger')
        return redirect(url_for('groups.detail', group_id=group.id))

    content = request.form.get('content', '').strip()
    if not content:
        flash('Il messaggio non può essere vuoto.', 'warning')
        return redirect(url_for('groups.detail', group_id=group.id))

    image_path = None
    if 'image' in request.files:
        image_path = save_group_picture(request.files['image'], subfolder='groups')

    message = GroupMessage(
        group_id=group.id,
        user_id=current_user.id,
        content=content,
        image=image_path,
    )
    db.session.add(message)
    db.session.commit()

    return redirect(url_for('groups.detail', group_id=group.id))


@bp.route('/<int:group_id>/remove-member/<int:user_id>', methods=['POST'])
@login_required
def remove_member(group_id, user_id):
    group = Group.query.get_or_404(group_id)

    admin_membership = GroupMembership.query.filter_by(group_id=group.id, user_id=current_user.id).first()
    if not admin_membership or admin_membership.role not in ('admin', 'moderator'):
        flash('Non hai i permessi per rimuovere membri.', 'danger')
        return redirect(url_for('groups.detail', group_id=group.id))

    if user_id == group.creator_id:
        flash('Non puoi rimuovere il creatore del gruppo.', 'danger')
        return redirect(url_for('groups.detail', group_id=group.id))

    membership = GroupMembership.query.filter_by(group_id=group.id, user_id=user_id).first()
    if not membership:
        flash('Utente non trovato nel gruppo.', 'warning')
        return redirect(url_for('groups.detail', group_id=group.id))

    db.session.delete(membership)
    db.session.commit()

    flash('Membro rimosso dal gruppo.', 'success')
    return redirect(url_for('groups.detail', group_id=group.id))


@bp.route('/<int:group_id>/promote/<int:user_id>', methods=['POST'])
@login_required
def promote_member(group_id, user_id):
    group = Group.query.get_or_404(group_id)

    admin_membership = GroupMembership.query.filter_by(group_id=group.id, user_id=current_user.id).first()
    if not admin_membership or admin_membership.role != 'admin':
        flash('Solo gli admin possono promuovere membri.', 'danger')
        return redirect(url_for('groups.detail', group_id=group.id))

    membership = GroupMembership.query.filter_by(group_id=group.id, user_id=user_id).first()
    if not membership:
        flash('Utente non trovato nel gruppo.', 'warning')
        return redirect(url_for('groups.detail', group_id=group.id))

    if membership.role == 'member':
        membership.role = 'moderator'
        flash('Membro promosso a Moderatore.', 'success')
    elif membership.role == 'moderator':
        membership.role = 'admin'
        flash('Membro promosso ad Admin.', 'success')
    else:
        flash('Questo membro è già Admin.', 'info')

    db.session.commit()
    return redirect(url_for('groups.detail', group_id=group.id))
