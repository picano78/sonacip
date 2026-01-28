"""
Backup utilities
"""
import os
import shutil
import zipfile
import hashlib
from datetime import datetime, timedelta
from flask import current_app
from app import db
from app.models import Backup as BackupModel, BackupSetting
import tempfile


def create_backup(created_by_id, backup_type='full', notes=None):
    """
    Create a backup
    backup_type: 'full', 'database', 'uploads'
    Returns: Backup model instance or None if failed
    """
    try:
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'sonacip_backup_{backup_type}_{timestamp}.zip'
        backup_path = os.path.join(current_app.config['BACKUP_FOLDER'], backup_filename)
        
        # Ensure backup folder exists
        os.makedirs(current_app.config['BACKUP_FOLDER'], exist_ok=True)
        
        # Create temporary directory for organizing files
        with tempfile.TemporaryDirectory() as temp_dir:
            
            if backup_type in ['full', 'database']:
                # Backup database
                db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
                if os.path.exists(db_path):
                    shutil.copy2(db_path, os.path.join(temp_dir, 'sonacip.db'))
            
            if backup_type in ['full', 'uploads']:
                # Backup uploads folder
                uploads_folder = current_app.config['UPLOAD_FOLDER']
                if os.path.exists(uploads_folder):
                    shutil.copytree(
                        uploads_folder,
                        os.path.join(temp_dir, 'uploads'),
                        dirs_exist_ok=True
                    )
            
            if backup_type == 'full':
                # Backup app code (optional - for complete restore)
                app_folder = os.path.join(current_app.root_path)
                if os.path.exists(app_folder):
                    # Only backup essential files, not the entire venv
                    essential_files = ['models.py', 'config.py', 'run.py']
                    app_backup_dir = os.path.join(temp_dir, 'app_code')
                    os.makedirs(app_backup_dir, exist_ok=True)
                    
                    for file in essential_files:
                        src = os.path.join(os.path.dirname(app_folder), file)
                        if os.path.exists(src):
                            shutil.copy2(src, os.path.join(app_backup_dir, file))
            
            # Create zip archive
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
        
        # Get file size and checksum
        file_size = os.path.getsize(backup_path)
        checksum = calculate_checksum(backup_path)
        
        # Create backup record
        backup = BackupModel(
            filename=backup_filename,
            filepath=backup_path,
            size=file_size,
            backup_type=backup_type,
            checksum=checksum,
            created_by=created_by_id,
            notes=notes,
            is_valid=True
        )
        
        db.session.add(backup)
        db.session.commit()
        
        return backup
        
    except Exception as e:
        current_app.logger.error(f'Backup failed: {str(e)}')
        return None


def get_backup_settings(create_if_missing=True):
    """Return BackupSetting singleton"""
    settings = BackupSetting.query.first()
    if not settings and create_if_missing:
        settings = BackupSetting()
        db.session.add(settings)
        db.session.commit()
    return settings


def run_scheduled_backup_if_due(now=None):
    """Run automated backup if enabled and schedule is due. Returns bool indicating execution."""
    from datetime import datetime
    now = now or datetime.utcnow()
    settings = get_backup_settings(create_if_missing=False)
    if not settings or not settings.auto_enabled:
        return False

    # Check hour match and last run
    if settings.run_hour_utc is not None and now.hour != settings.run_hour_utc:
        return False

    if settings.last_run_at:
        delta_days = (now.date() - settings.last_run_at.date()).days
        if settings.frequency == 'daily' and delta_days < 1:
            return False
        if settings.frequency == 'weekly' and delta_days < 7:
            return False

    backup = create_backup(
        created_by_id=settings.updated_by or 1,  # fallback to super admin ID 1
        backup_type=settings.backup_type or 'full',
        notes='Auto-backup'
    )
    if backup:
        settings.last_run_at = now
        db.session.commit()
        cleanup_old_backups(settings.retention_days)
        return True
    return False


def cleanup_old_backups(retention_days):
    """Delete backups older than retention_days"""
    if not retention_days or retention_days <= 0:
        return 0
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    old_backups = BackupModel.query.filter(BackupModel.created_at < cutoff).all()
    count = 0
    for b in old_backups:
        success, _ = delete_backup(b.id)
        if success:
            count += 1
    return count


def calculate_checksum(file_path):
    """Return SHA256 hex digest for a file"""
    sha = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha.update(chunk)
    return sha.hexdigest()


def restore_backup(backup_id):
    """
    Restore from backup
    Returns: (success: bool, message: str)
    """
    try:
        backup = BackupModel.query.get(backup_id)
        if not backup:
            return False, 'Backup non trovato'
        
        if not os.path.exists(backup.filepath):
            backup.is_valid = False
            backup.validation_message = 'File non trovato'
            db.session.commit()
            return False, 'File di backup non trovato'
        
        # Validate zip file
        if not zipfile.is_zipfile(backup.filepath):
            backup.is_valid = False
            backup.validation_message = 'File zip non valido'
            db.session.commit()
            return False, 'File di backup corrotto'
        
        # Create temporary directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract backup
            with zipfile.ZipFile(backup.filepath, 'r') as zipf:
                zipf.extractall(temp_dir)
            
            # Restore database
            db_backup_path = os.path.join(temp_dir, 'sonacip.db')
            if os.path.exists(db_backup_path):
                db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
                
                # Create backup of current database before restoring
                if os.path.exists(db_path):
                    backup_current = f"{db_path}.before_restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(db_path, backup_current)
                
                # Restore database
                shutil.copy2(db_backup_path, db_path)
            
            # Restore uploads
            uploads_backup_path = os.path.join(temp_dir, 'uploads')
            if os.path.exists(uploads_backup_path):
                uploads_folder = current_app.config['UPLOAD_FOLDER']
                
                # Backup current uploads
                if os.path.exists(uploads_folder):
                    backup_uploads = f"{uploads_folder}_before_restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copytree(uploads_folder, backup_uploads, dirs_exist_ok=True)
                    # Remove old uploads
                    shutil.rmtree(uploads_folder)
                
                # Restore uploads
                shutil.copytree(uploads_backup_path, uploads_folder, dirs_exist_ok=True)
        
        return True, 'Backup ripristinato con successo'
        
    except Exception as e:
        current_app.logger.error(f'Restore failed: {str(e)}')
        return False, f'Errore durante il ripristino: {str(e)}'


def validate_backup(backup_id):
    """
    Validate backup file
    Returns: (is_valid: bool, message: str)
    """
    try:
        backup = BackupModel.query.get(backup_id)
        if not backup:
            return False, 'Backup non trovato'
        
        if not os.path.exists(backup.filepath):
            return False, 'File non trovato'
        
        if not zipfile.is_zipfile(backup.filepath):
            return False, 'File zip non valido'

        # Verify checksum if stored
        if backup.checksum:
            current_sum = calculate_checksum(backup.filepath)
            if current_sum != backup.checksum:
                return False, 'Checksum non corrisponde'
        
        # Check if zip can be opened and contains expected files
        with zipfile.ZipFile(backup.filepath, 'r') as zipf:
            file_list = zipf.namelist()
            
            if backup.backup_type in ['full', 'database']:
                if 'sonacip.db' not in file_list:
                    return False, 'Database non trovato nel backup'
            
            if backup.backup_type in ['full', 'uploads']:
                has_uploads = any('uploads/' in f for f in file_list)
                if not has_uploads:
                    return False, 'Cartella uploads non trovata nel backup'
        
        return True, 'Backup valido'
        
    except Exception as e:
        return False, f'Errore durante la validazione: {str(e)}'


def delete_backup(backup_id):
    """
    Delete backup file and record
    Returns: (success: bool, message: str)
    """
    try:
        backup = BackupModel.query.get(backup_id)
        if not backup:
            return False, 'Backup non trovato'
        
        # Delete file if exists
        if os.path.exists(backup.filepath):
            os.remove(backup.filepath)
        
        # Delete record
        db.session.delete(backup)
        db.session.commit()
        
        return True, 'Backup eliminato'
        
    except Exception as e:
        current_app.logger.error(f'Delete backup failed: {str(e)}')
        return False, f'Errore durante l\'eliminazione: {str(e)}'


def get_backup_size_formatted(size_bytes):
    """Format backup size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"
