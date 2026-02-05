"""
Backup routes
Create, restore, manage backups
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.backup.utils import (
    create_backup, restore_backup, validate_backup, 
    delete_backup, get_backup_size_formatted, get_backup_settings,
    run_scheduled_backup_if_due
)
from app.models import Backup, AuditLog, BackupSetting
from app.admin.utils import admin_required
from datetime import datetime

bp = Blueprint('backup', __name__, url_prefix='/backup')


@bp.route('/')
@login_required
@admin_required
def index():
    """Backup management page"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    pagination = Backup.query.order_by(Backup.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    backups = pagination.items
    
    # Calculate total backup size
    total_size = db.session.query(db.func.sum(Backup.size)).scalar() or 0
    
    settings = get_backup_settings()
    return render_template('backup/index.html',
                         backups=backups,
                         pagination=pagination,
                         total_size=get_backup_size_formatted(total_size),
                         settings=settings)


@bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    """Create new backup"""
    backup_type = request.form.get('backup_type', 'full')
    notes = request.form.get('notes', '')
    
    if backup_type not in ['full', 'database', 'uploads']:
        flash('Tipo di backup non valido.', 'danger')
        return redirect(url_for('backup.index'))
    
    # Create backup
    backup = create_backup(
        created_by_id=current_user.id,
        backup_type=backup_type,
        notes=notes
    )
    
    if backup:
        # Log the action
        log = AuditLog(
            user_id=current_user.id,
            action='create_backup',
            entity_type='Backup',
            entity_id=backup.id,
            details=f'Created {backup_type} backup: {backup.filename}',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Backup creato con successo: {backup.filename}', 'success')
    else:
        flash('Errore durante la creazione del backup.', 'danger')
    
    return redirect(url_for('backup.index'))


@bp.route('/settings', methods=['POST'])
@login_required
@admin_required
def save_settings():
    """Update auto-backup settings"""
    settings = get_backup_settings()
    settings.auto_enabled = bool(request.form.get('auto_enabled'))
    settings.frequency = request.form.get('frequency', 'weekly')
    settings.backup_type = request.form.get('backup_type', 'full')
    settings.retention_days = request.form.get('retention_days', type=int) or 30
    settings.run_hour_utc = request.form.get('run_hour_utc', type=int) or 2
    settings.updated_by = current_user.id
    settings.updated_at = datetime.utcnow()
    db.session.commit()
    flash('Impostazioni backup aggiornate.', 'success')
    return redirect(url_for('backup.index'))


@bp.route('/run-now', methods=['POST'])
@login_required
@admin_required
def run_now():
    """Manually trigger backup respecting selected type"""
    settings = get_backup_settings()
    backup_type = request.form.get('backup_type') or settings.backup_type or 'full'
    backup = create_backup(created_by_id=current_user.id, backup_type=backup_type, notes='Eseguito manualmente')
    if backup:
        flash(f'Backup creato: {backup.filename}', 'success')
    else:
        flash('Errore nella creazione del backup.', 'danger')
    return redirect(url_for('backup.index'))


@bp.route('/<int:backup_id>/restore', methods=['POST'])
@login_required
@admin_required
def restore(backup_id):
    """Restore from backup"""
    backup = Backup.query.get_or_404(backup_id)
    
    # Validate first
    is_valid, message = validate_backup(backup_id)
    
    if not is_valid:
        flash(f'Backup non valido: {message}', 'danger')
        return redirect(url_for('backup.index'))
    
    # Perform restore
    success, message = restore_backup(backup_id)
    
    if success:
        # Log the action
        log = AuditLog(
            user_id=current_user.id,
            action='restore_backup',
            entity_type='Backup',
            entity_id=backup.id,
            details=f'Restored backup: {backup.filename}',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(message, 'success')
        flash('ATTENZIONE: Il database è stato ripristinato. Ricarica la pagina.', 'warning')
    else:
        flash(f'Errore: {message}', 'danger')
    
    return redirect(url_for('backup.index'))


@bp.route('/<int:backup_id>/validate', methods=['POST'])
@login_required
@admin_required
def validate(backup_id):
    """Validate backup"""
    backup = Backup.query.get_or_404(backup_id)
    
    is_valid, message = validate_backup(backup_id)
    
    # Update backup record
    backup.is_valid = is_valid
    backup.validation_message = message
    db.session.commit()
    
    if is_valid:
        flash(f'Backup valido: {message}', 'success')
    else:
        flash(f'Backup non valido: {message}', 'warning')
    
    return redirect(url_for('backup.index'))


@bp.route('/<int:backup_id>/download')
@login_required
@admin_required
def download(backup_id):
    """Download backup file"""
    backup = Backup.query.get_or_404(backup_id)
    
    import os
    if not os.path.exists(backup.filepath):
        flash('File di backup non trovato.', 'danger')
        return redirect(url_for('backup.index'))
    
    # Log the action
    log = AuditLog(
        user_id=current_user.id,
        action='download_backup',
        entity_type='Backup',
        entity_id=backup.id,
        details=f'Downloaded backup: {backup.filename}',
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    return send_file(
        backup.filepath,
        as_attachment=True,
        download_name=backup.filename
    )


@bp.route('/<int:backup_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(backup_id):
    """Delete backup"""
    backup = Backup.query.get_or_404(backup_id)
    backup_name = backup.filename
    
    success, message = delete_backup(backup_id)
    
    if success:
        # Log the action
        log = AuditLog(
            user_id=current_user.id,
            action='delete_backup',
            entity_type='Backup',
            entity_id=backup_id,
            details=f'Deleted backup: {backup_name}',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(message, 'success')
    else:
        flash(f'Errore: {message}', 'danger')
    
    return redirect(url_for('backup.index'))


@bp.route('/upload-restore', methods=['POST'])
@login_required
@admin_required
def upload_restore():
    """Upload and restore from backup file"""
    import os
    import tempfile
    from werkzeug.utils import secure_filename
    
    if 'backup_file' not in request.files:
        flash('Nessun file selezionato.', 'danger')
        return redirect(url_for('backup.index'))
    
    file = request.files['backup_file']
    if file.filename == '':
        flash('Nessun file selezionato.', 'danger')
        return redirect(url_for('backup.index'))
    
    if not file.filename.endswith('.zip'):
        flash('Il file deve essere un archivio ZIP.', 'danger')
        return redirect(url_for('backup.index'))
    
    try:
        filename = secure_filename(file.filename)
        backup_dir = current_app.config.get('BACKUP_FOLDER') or os.path.join(current_app.root_path, '..', 'backups')
        
        if not os.path.isdir(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)
        
        filepath = os.path.join(backup_dir, filename)
        file.save(filepath)
        
        file_size = os.path.getsize(filepath)
        from app.backup.utils import calculate_checksum
        checksum = calculate_checksum(filepath)
        
        backup = Backup(
            filename=filename,
            filepath=filepath,
            size=file_size,
            backup_type='uploaded',
            checksum=checksum,
            created_by=current_user.id,
            notes='Caricato manualmente per ripristino',
            is_valid=True
        )
        db.session.add(backup)
        db.session.commit()
        
        success, message = restore_backup(backup.id)
        
        if success:
            log = AuditLog(
                user_id=current_user.id,
                action='upload_restore_backup',
                entity_type='Backup',
                entity_id=backup.id,
                details=f'Uploaded and restored backup: {filename}',
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            
            flash(f'Backup caricato e ripristinato con successo: {filename}', 'success')
            flash('ATTENZIONE: Il database è stato ripristinato. Ricarica la pagina.', 'warning')
        else:
            flash(f'Errore durante il ripristino: {message}', 'danger')
    
    except Exception as e:
        flash(f'Errore durante il caricamento: {str(e)}', 'danger')
    
    return redirect(url_for('backup.index'))


@bp.route('/cleanup-old', methods=['POST'])
@login_required
@admin_required
def cleanup_old():
    """Delete backups older than X days"""
    from datetime import datetime, timedelta
    
    days = request.form.get('days', 30, type=int)
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    old_backups = Backup.query.filter(Backup.created_at < cutoff_date).all()
    
    deleted_count = 0
    for backup in old_backups:
        success, _ = delete_backup(backup.id)
        if success:
            deleted_count += 1
    
    flash(f'{deleted_count} backup vecchi eliminati.', 'success')
    return redirect(url_for('backup.index'))


@bp.route('/auto-check', methods=['POST'])
@login_required
@admin_required
def auto_check():
    """Force a scheduled backup check now"""
    ran = run_scheduled_backup_if_due()
    flash('Backup automatico eseguito.' if ran else 'Nessun backup dovuto ora.', 'info')
    return redirect(url_for('backup.index'))
