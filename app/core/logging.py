"""
Logging configuration for SONACIP.

Goals:
- Human-readable logs by default
- Optional JSON logs for production aggregation
- Separate namespaces: startup/app/db
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    level_name = (os.getenv("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    json_logs = (os.getenv("JSON_LOGS") or "false").lower() in ("1", "true", "on", "yes")

    root = logging.getLogger()
    root.setLevel(level)

    # Clear default handlers to avoid duplicate logs under gunicorn preload
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter() if json_logs else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)

    # DB logging is noisy; default to WARNING unless explicitly requested
    db_level_name = (os.getenv("DB_LOG_LEVEL") or "WARNING").upper()
    db_level = getattr(logging, db_level_name, logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(db_level)
    logging.getLogger("alembic").setLevel(level)


def setup_file_logging(app):
    """Configura logging con rotazione automatica"""
    from logging.handlers import RotatingFileHandler
    import os
    
    log_folder = app.config.get('LOGS_FOLDER') or 'logs'
    if not os.path.exists(log_folder):
        os.makedirs(log_folder, exist_ok=True)
    
    # Application log
    file_handler = RotatingFileHandler(
        os.path.join(log_folder, 'sonacip.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('SONACIP startup')

