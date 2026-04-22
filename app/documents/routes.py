from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app, Response
from flask_login import login_required, current_user
from app import db
from app.models import Document, DocumentFolder, User
from app.utils import admin_required, log_action, get_active_society_id
from datetime import datetime
import os
import uuid
import io
from werkzeug.utils import secure_filename

bp = Blueprint('documents', __name__, url_prefix='/documents')

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'jpeg', 'png', 'gif', 'zip', 'txt', 'csv'}


@bp.before_request
def _check_feature():
    from app.utils import check_feature_enabled
    if not check_feature_enabled('documents'):
        flash('Questa funzionalità non è attualmente disponibile.', 'warning')
        return redirect(url_for('main.dashboard'))


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


def _get_society_filter():
    """Get society filter for document queries."""
    society_id = get_active_society_id(current_user)
    if society_id:
        return society_id
    # If user is a society, use their ID
    if current_user.is_society():
        society = current_user.get_primary_society()
        if society:
            return society.id
    return None


def _generate_pdf_export(data, filename='export.pdf', title='Data Export'):
    """
    Generate a PDF export of document data using reportlab.
    
    Args:
        data: List of dictionaries with document information
        filename: Output filename
        title: PDF title
        
    Returns:
        Flask Response with PDF file
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
    except ImportError:
        flash('Impossibile generare PDF. Libreria reportlab non disponibile.', 'danger')
        return redirect(url_for('documents.index'))
    
    if not data:
        data = [{}]
    
    # Auto-detect columns
    columns = list(data[0].keys()) if data else []
    
    if not columns:
        flash('Nessun documento da esportare.', 'info')
        return redirect(url_for('documents.index'))
    
    # Create PDF in memory
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#366092'),
        spaceAfter=20,
        alignment=1  # Center
    )
    
    # Add title
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Prepare table data
    table_data = [columns]
    for row in data:
        table_row = []
        for col in columns:
            value = row.get(col, '')
            if isinstance(value, datetime):
                value = value.strftime('%d/%m/%Y %H:%M')
            # Truncate long values
            str_value = str(value)
            if len(str_value) > 40:
                str_value = str_value[:37] + '...'
            table_row.append(str_value)
        table_data.append(table_row)
    
    # Create table with auto column widths
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#366092')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    elements.append(table)
    
    # Add footer
    elements.append(Spacer(1, 0.3 * inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1
    )
    footer_text = f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    elements.append(Paragraph(footer_text, footer_style))
    
    # Build PDF
    doc.build(elements)
    output.seek(0)
    
    # Create response
    response = Response(
        output.getvalue(),
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )
    
    return response


@bp.route('/')
@login_required
def index():
    society_id = _get_society_filter()
    
    # Filter by society if applicable
    if society_id:
        folders = DocumentFolder.query.filter_by(parent_id=None, society_id=society_id).order_by(DocumentFolder.name).all()
        documents = Document.query.filter_by(folder_id=None, society_id=society_id).order_by(Document.created_at.desc()).all()
    else:
        # Admin or users without society see all or their own
        if current_user.is_admin():
            folders = DocumentFolder.query.filter_by(parent_id=None).order_by(DocumentFolder.name).all()
            documents = Document.query.filter_by(folder_id=None).order_by(Document.created_at.desc()).all()
        else:
            folders = DocumentFolder.query.filter_by(parent_id=None, created_by=current_user.id).order_by(DocumentFolder.name).all()
            documents = Document.query.filter_by(folder_id=None, uploaded_by=current_user.id).order_by(Document.created_at.desc()).all()
    
    return render_template('documents/index.html',
                           folders=folders, documents=documents,
                           current_folder=None, breadcrumbs=[],
                           file_icon=_file_icon, format_size=_format_size)


@bp.route('/folder/<int:folder_id>')
@login_required
def folder_view(folder_id):
    folder = DocumentFolder.query.get_or_404(folder_id)
    
    # Check access: verify user can access this folder's society
    society_id = _get_society_filter()
    if society_id and folder.society_id and folder.society_id != society_id:
        if not current_user.is_admin():
            flash('Non hai i permessi per accedere a questa cartella.', 'danger')
            return redirect(url_for('documents.index'))
    
    # Filter subfolders and documents by society
    if society_id:
        folders = DocumentFolder.query.filter_by(parent_id=folder.id, society_id=society_id).order_by(DocumentFolder.name).all()
        documents = Document.query.filter_by(folder_id=folder.id, society_id=society_id).order_by(Document.created_at.desc()).all()
    else:
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

    society_id = _get_society_filter()
    
    folder = DocumentFolder(
        name=name,
        description=description or None,
        parent_id=parent_id if parent_id else None,
        society_id=society_id,
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
    society_id = _get_society_filter()

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
            society_id=society_id,
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
    
    # Check access permissions
    society_id = _get_society_filter()
    if doc.society_id and society_id and doc.society_id != society_id:
        if not current_user.is_admin():
            flash('Non hai i permessi per scaricare questo documento.', 'danger')
            return redirect(url_for('documents.index'))
    
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
    
    # Check access permissions
    society_id = _get_society_filter()
    if doc.society_id and society_id and doc.society_id != society_id:
        if not current_user.is_admin():
            flash('Non hai i permessi per visualizzare questo documento.', 'danger')
            return redirect(url_for('documents.index'))
    
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
        society_id = _get_society_filter()
        query = Document.query.filter(
            (Document.title.ilike(f'%{q}%')) | (Document.description.ilike(f'%{q}%'))
        )
        
        # Filter by society if applicable
        if society_id:
            query = query.filter_by(society_id=society_id)
        elif not current_user.is_admin():
            query = query.filter_by(uploaded_by=current_user.id)
        
        results = query.order_by(Document.created_at.desc()).limit(50).all()
    
    return render_template('documents/index.html',
                           folders=[], documents=results,
                           current_folder=None, breadcrumbs=[],
                           search_query=q,
                           file_icon=_file_icon, format_size=_format_size)


@bp.route('/export-pdf')
@login_required
def export_pdf():
    """Export society documents list to PDF"""
    society_id = _get_society_filter()
    
    # Get society information
    society_name = "Tutti i Documenti"
    if society_id:
        from app.models import Society
        society = db.session.get(Society, society_id)
        if society:
            society_name = society.legal_name
        else:
            flash('Società non trovata.', 'danger')
            return redirect(url_for('documents.index'))
    elif not current_user.is_admin():
        flash('Funzionalità disponibile solo per le società.', 'warning')
        return redirect(url_for('documents.index'))
    
    # Query documents for this society
    if society_id:
        documents = Document.query.filter_by(society_id=society_id).order_by(Document.created_at.desc()).all()
    elif current_user.is_admin():
        documents = Document.query.order_by(Document.created_at.desc()).all()
    else:
        documents = Document.query.filter_by(uploaded_by=current_user.id).order_by(Document.created_at.desc()).all()
    
    # Prepare data for PDF export
    data = []
    for doc in documents:
        # Get folder path
        folder_path = ""
        if doc.folder:
            breadcrumbs = _build_breadcrumbs(doc.folder)
            folder_path = " / ".join([f.name for f in breadcrumbs])
        
        data.append({
            'Titolo': doc.title,
            'Cartella': folder_path or '-',
            'Tipo': doc.file_type.upper() if doc.file_type else '-',
            'Dimensione': _format_size(doc.file_size),
            'Download': doc.download_count or 0,
            'Caricato da': doc.uploader.username if doc.uploader else '-',
            'Data': doc.created_at.strftime('%d/%m/%Y %H:%M') if doc.created_at else '-'
        })
    
    # Generate PDF
    columns = ['Titolo', 'Cartella', 'Tipo', 'Dimensione', 'Download', 'Caricato da', 'Data']
    filename = f'documenti_{society_name.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    title = f'Elenco Documenti - {society_name}'
    
    log_action('export_documents_pdf', 'Document', None, f'Esportati {len(documents)} documenti in PDF')
    
    return _generate_pdf_export(data, filename=filename, title=title)
