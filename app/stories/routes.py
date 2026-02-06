from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Story, StoryView, User
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename

bp = Blueprint('stories', __name__, url_prefix='/stories')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov', 'webm'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_story_file(file):
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(current_app.root_path, '..', 'uploads', 'stories')
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, unique_name)
    file.save(filepath)
    return f"uploads/stories/{unique_name}"


def _get_media_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in ('mp4', 'mov', 'webm'):
        return 'video'
    return 'image'


@bp.route('/')
@login_required
def feed():
    now = datetime.utcnow()
    active_stories = Story.query.filter(Story.expires_at > now).order_by(Story.created_at.desc()).all()

    users_with_stories = {}
    for story in active_stories:
        if story.user_id not in users_with_stories:
            users_with_stories[story.user_id] = {
                'user': story.author,
                'stories': [],
                'has_unseen': False
            }
        users_with_stories[story.user_id]['stories'].append(story)
        viewed = StoryView.query.filter_by(story_id=story.id, viewer_id=current_user.id).first()
        if not viewed:
            users_with_stories[story.user_id]['has_unseen'] = True

    return render_template('stories/feed.html', users_with_stories=users_with_stories)


@bp.route('/create', methods=['POST'])
@login_required
def create():
    caption = request.form.get('caption', '').strip()
    background_color = request.form.get('background_color', '#1877f2')
    file = request.files.get('media')

    media_url = None
    media_type = 'image'

    if file and file.filename and _allowed_file(file.filename):
        media_url = _save_story_file(file)
        media_type = _get_media_type(file.filename)
    elif not caption:
        flash('Inserisci un\'immagine o una didascalia per la storia.', 'warning')
        return redirect(url_for('stories.feed'))

    story = Story(
        user_id=current_user.id,
        media_url=media_url,
        media_type=media_type,
        caption=caption,
        background_color=background_color,
    )
    db.session.add(story)
    db.session.commit()
    flash('Storia pubblicata!', 'success')
    return redirect(url_for('stories.feed'))


@bp.route('/view/<int:story_id>')
@login_required
def view_story(story_id):
    story = Story.query.get_or_404(story_id)
    existing = StoryView.query.filter_by(story_id=story.id, viewer_id=current_user.id).first()
    if not existing and story.user_id != current_user.id:
        sv = StoryView(story_id=story.id, viewer_id=current_user.id)
        db.session.add(sv)
        story.views_count = (story.views_count or 0) + 1
        db.session.commit()

    time_ago = ''
    diff = datetime.utcnow() - story.created_at
    if diff.total_seconds() < 60:
        time_ago = 'adesso'
    elif diff.total_seconds() < 3600:
        time_ago = f'{int(diff.total_seconds() // 60)} min fa'
    else:
        time_ago = f'{int(diff.total_seconds() // 3600)} ore fa'

    return jsonify({
        'id': story.id,
        'user_id': story.user_id,
        'author_name': story.author.get_full_name(),
        'author_avatar': story.author.avatar or '',
        'media_url': '/' + story.media_url if story.media_url else None,
        'media_type': story.media_type,
        'caption': story.caption,
        'background_color': story.background_color,
        'time_ago': time_ago,
        'view_count': story.views_count or 0,
        'is_own': story.user_id == current_user.id,
    })


@bp.route('/user/<int:user_id>')
@login_required
def user_stories(user_id):
    now = datetime.utcnow()
    stories = Story.query.filter(
        Story.user_id == user_id,
        Story.expires_at > now
    ).order_by(Story.created_at.asc()).all()

    result = []
    for s in stories:
        viewed = StoryView.query.filter_by(story_id=s.id, viewer_id=current_user.id).first()
        result.append({
            'id': s.id,
            'viewed': viewed is not None,
        })
    return jsonify(result)


@bp.route('/<int:story_id>/delete', methods=['POST'])
@login_required
def delete_story(story_id):
    story = Story.query.get_or_404(story_id)
    if story.user_id != current_user.id and not current_user.is_admin():
        flash('Non puoi eliminare questa storia.', 'danger')
        return redirect(url_for('stories.feed'))

    db.session.delete(story)
    db.session.commit()
    flash('Storia eliminata.', 'success')
    return redirect(url_for('stories.feed'))


@bp.route('/cleanup')
@login_required
def cleanup():
    if not current_user.is_admin():
        flash('Accesso negato.', 'danger')
        return redirect(url_for('stories.feed'))

    now = datetime.utcnow()
    expired = Story.query.filter(Story.expires_at <= now).all()
    count = len(expired)
    for s in expired:
        db.session.delete(s)
    db.session.commit()
    flash(f'{count} storie scadute eliminate.', 'success')
    return redirect(url_for('stories.feed'))
