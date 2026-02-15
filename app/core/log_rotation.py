"""
Log Rotation System
Gestisce la rotazione automatica dei file di log
"""

import os
import gzip
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

class LogRotator:
    """Gestisce rotazione e compressione log"""
    
    def __init__(self, log_dir='logs', max_bytes=10*1024*1024, backup_count=10):
        """
        Args:
            log_dir: Directory dei log
            max_bytes: Dimensione massima prima della rotazione (default 10MB)
            backup_count: Numero di backup da mantenere
        """
        self.log_dir = Path(log_dir)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.log_dir.mkdir(exist_ok=True)
    
    def should_rotate(self, log_file):
        """Controlla se il log deve essere ruotato"""
        if not log_file.exists():
            return False
        return log_file.stat().st_size >= self.max_bytes
    
    def rotate_log(self, log_file):
        """Ruota un file di log"""
        if not self.should_rotate(log_file):
            return
        
        # Timestamp per il backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{log_file.stem}_{timestamp}.log.gz"
        backup_path = self.log_dir / backup_name
        
        # Comprimi e salva
        with open(log_file, 'rb') as f_in:
            with gzip.open(backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Svuota il file originale
        log_file.write_text('')
        
        logger.info(f"Log rotated: {log_file} -> {backup_name}")
        print(f"✅ Log rotated: {log_file} -> {backup_name}")
        
        # Pulisci vecchi backup
        self.cleanup_old_backups(log_file.stem)
    
    def cleanup_old_backups(self, log_name):
        """Rimuove backup vecchi oltre il limite"""
        pattern = f"{log_name}_*.log.gz"
        backups = sorted(self.log_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        
        # Rimuovi i backup oltre il limite
        for backup in backups[self.backup_count:]:
            backup.unlink()
            logger.info(f"Removed old backup: {backup.name}")
            print(f"🗑️  Removed old backup: {backup.name}")
    
    def rotate_all(self):
        """Ruota tutti i file di log nella directory"""
        for log_file in self.log_dir.glob('*.log'):
            self.rotate_log(log_file)
    
    def cleanup_old_logs(self, days=30):
        """Rimuove log compressi più vecchi di X giorni"""
        cutoff = datetime.now() - timedelta(days=days)
        
        for gz_file in self.log_dir.glob('*.log.gz'):
            if datetime.fromtimestamp(gz_file.stat().st_mtime) < cutoff:
                gz_file.unlink()
                logger.info(f"Removed old log: {gz_file.name}")
                print(f"🗑️  Removed old log: {gz_file.name}")

# Comando CLI per la rotazione manuale
if __name__ == '__main__':
    rotator = LogRotator()
    print("🔄 Starting log rotation...")
    rotator.rotate_all()
    rotator.cleanup_old_logs(days=30)
    print("✅ Log rotation completed!")
