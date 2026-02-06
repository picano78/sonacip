from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Document, DocumentFolder, User
from app.utils import admin_required, log_action
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename

bp = Blueprint('documents', __name__, url_prefix='/documents')

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'jpeg', 'png', 'gif', 'zip', 'txt', 'csv'}
MAX_FILE_SIZE = 50 * 1024 * 1024
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'uploads', 'documents')


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _file_icon(file_type):
    icons = {
        'pdf': 'bi-file-earmark-pdf-fill text-danger',
        'doc': 'bi-file-earmark-word-fill text-primary',
        'docx': 'bi-file-earmark-word-fill text-primary',
        'xls': 'bi-file-earmark-excel-fill text-success',
        'xlsx': 'bi-file-earmark-excel-fill text-success',
        'ppt': 'bi-file-earmark-ppt-fill text-warning',
        'pptx': 'bi-file-earmark-ppt-fill text-warning',
        'jpg': 'bi-file-earmark-image-fill text-info',
        'jpeg': 'bi-file-earmark-image-fill text-info',
        'png': 'bi-file-earmark-image-fill text-info',
        'gif': 'bi-file-earmark-image-fill text-info',
        'zip': 'bi-file-earmark-zip-fill text-secondary',
        'txt': 'bi-file-earmark-text-fill text-muted',
        'csv': 'bi-file-earmark-spreadsheet-fill text-success',
    }
    return icons.get((file_type or '').lower(), 'bi-file-earmark-fill text-secondary')


def _format_size(size_bytes):
    if not size_bytes:
        return '0 B'
    if size_bytes < 1024:
        return f'{size_bytes} B'
    if size_bytes < 1024 * 1024:
        return f'{size_bytes / 1024:.1f} KB'
    return f'{size_bytes / (1024 * 1024):.1f} MB'


def _build_breadcrumbs(folder):
    crumbs = []
    current = folder
    while current:
        crumbs.insert(0, current)
        current = current.parent
    return crumbs


@bp.route('/')
@login_required
def index():
    folders = DocumentFolder.query.filter_by(parent_id=None).order_by(DocumentFolder.name).all()
    documents = Document.query.filter_by(folder_id=None).order_by(Document.created_at.desc()).all()
    return render_template('documents/index.html',
                           folders=folders, documents=documents,
                           current_folder=None, breadcrumbs=[],
                           file_icon=_file_icon, format_size=_format_size)


@bp.route('/folder/<int:folder_id>')
@login_required
def folder_view(folder_id):
    folder = DocumentFolder.query.get_or_404(folder_id)
    folders = DocumentFolder.query.filter_by(parent_id=folder.id).order_by(DocumentFolder.name).all()
    documents = Document.query.filter_by(folder_id=folder.id).order_by(Document.created_at.desc()).all()
    breadcrumbs = _build_breadcrumbs(folder)
    return render_template('documents/index.html',
                           folders=folders, documents=documents,
                           current_folder=folder, breadcrumbs=breadcrumbs,
                           file_icon=_file_icon, format_size=_format_size)


@bp.route('/folder/create', methods=['POST'])
@login_required
def create_folder():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    parent_id = request.form.get('parent_id', type=int)

    if not name:
        flash('Il nome della cartella è obbligatorio.', 'danger')
        if parent_id:
            return redirect(url_for('documents.folder_view', folder_id=parent_id))
        return redirect(url_for('documents.index'))

    folder = DocumentFolder(
        name=name,
        description=description or None,
        parent_id=parent_id if parent_id else None,
        created_by=current_user.id,
    )
    db.session.add(folder)
    db.session.commit()
    log_action('create_folder', 'DocumentFolder', folder.id, f'Cartella "{name}" creata')
    flash(f'Cartella "{name}" creata con successo.', 'success')

    if parent_id:
        return redirect(url_for('documents.folder_view', folder_id=parent_id))
    return redirect(url_for('documents.index'))


@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    folder_id = request.form.get('folder_id', type=int)
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    is_public = request.form.get('is_public') == 'on'

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        flash('Seleziona almeno un file da caricare.', 'danger')
        if folder_id:
            return redirect(url_for('documents.folder_view', folder_id=folder_id))
        return redirect(url_for('documents.index'))

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    uploaded = 0

    for f in files:
        if not f or f.filename == '':
            continue
        if not _allowed_file(f.filename):
            flash(f'Tipo di file non consentito: {f.filename}', 'warning')
            continue

        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        if size > MAX_FILE_SIZE:
            flash(f'File troppo grande: {f.filename} (max 50MB)', 'warning')
            continue

        original_name = secure_filename(f.filename)
        ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else ''
        unique_name = f'{uuid.uuid4().hex}.{ext}' if ext else uuid.uuid4().hex
        save_path = os.path.join(UPLOAD_DIR, unique_name)
        f.save(save_path)

        doc_title = title if title and uploaded == 0 else (title + f' ({uploaded + 1})' if title else original_name)

        doc = Document(
            title=doc_title,
            description=description or None,
            file_path=save_path,
            file_name=original_name,
            file_size=size,
            file_type=ext,
            folder_id=folder_id if folder_id else None,
            uploaded_by=current_user.id,
            is_public=is_public,
        )
        db.session.add(doc)
        uploaded += 1

    if uploaded:
        db.session.commit()
        log_action('upload_document', 'Document', None, f'{uploaded} file caricati')
        flash(f'{uploaded} file caricati con successo.', 'success')

    if folder_id:
        return redirect(url_for('documents.folder_view', folder_id=folder_id))
    return redirect(url_for('documents.index'))


@bp.route('/download/<int:doc_id>')
@login_required
def download(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if not os.path.exists(doc.file_path):
        flash('File non trovato sul server.', 'danger')
        return redirect(url_for('documents.index'))

    doc.download_count = (doc.download_count or 0) + 1
    db.session.commit()

    return send_file(doc.file_path, as_attachment=True, download_name=doc.file_name)


@bp.route('/view/<int:doc_id>')
@login_required
def view(doc_id):
    doc = Document.query.get_or_404(doc_id)
    is_image = (doc.file_type or '').lower() in ('jpg', 'jpeg', 'png', 'gif')
    is_pdf = (doc.file_type or '').lower() == 'pdf'
    can_delete = (doc.uploaded_by == current_user.id) or current_user.is_admin()
    return render_template('documents/detail.html',
                           doc=doc, is_image=is_image, is_pdf=is_pdf,
                           can_delete=can_delete,
                           file_icon=_file_icon, format_size=_format_size)


@bp.route('/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.uploaded_by != current_user.id and not current_user.is_admin():
        flash('Non hai i permessi per eliminare questo documento.', 'danger')
        return redirect(url_for('documents.view', doc_id=doc_id))

    folder_id = doc.folder_id
    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception:
        pass

    log_action('delete_document', 'Document', doc.id, f'Documento "{doc.title}" eliminato')
    db.session.delete(doc)
    db.session.commit()
    flash('Documento eliminato con successo.', 'success')

    if folder_id:
        return redirect(url_for('documents.folder_view', folder_id=folder_id))
    return redirect(url_for('documents.index'))


@bp.route('/folder/<int:folder_id>/delete', methods=['POST'])
@login_required
def delete_folder(folder_id):
    folder = DocumentFolder.query.get_or_404(folder_id)
    if folder.created_by != current_user.id and not current_user.is_admin():
        flash('Non hai i permessi per eliminare questa cartella.', 'danger')
        return redirect(url_for('documents.folder_view', folder_id=folder_id))

    if folder.documents.count() > 0 or folder.children.count() > 0:
        flash('La cartella non è vuota. Elimina prima il contenuto.', 'warning')
        return redirect(url_for('documents.folder_view', folder_id=folder_id))

    parent_id = folder.parent_id
    log_action('delete_folder', 'DocumentFolder', folder.id, f'Cartella "{folder.name}" eliminata')
    db.session.delete(folder)
    db.session.commit()
    flash('Cartella eliminata con successo.', 'success')

    if parent_id:
        return redirect(url_for('documents.folder_view', folder_id=parent_id))
    return redirect(url_for('documents.index'))


@bp.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    results = []
    if q:
        results = Document.query.filter(
            (Document.title.ilike(f'%{q}%')) | (Document.description.ilike(f'%{q}%'))
        ).order_by(Document.created_at.desc()).limit(50).all()
    return render_template('documents/index.html',
                           folders=[], documents=results,
                           current_folder=None, breadcrumbs=[],
                           search_query=q,
                           file_icon=_file_icon, format_size=_format_size)
