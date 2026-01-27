# Gunicorn configuration for SONACIP
import os

bind = "127.0.0.1:8000"
workers = 2
threads = 4
timeout = 120
preload_app = True

logs_folder = os.environ.get("LOGS_FOLDER", "logs")
os.makedirs(logs_folder, exist_ok=True)
accesslog = os.path.join(logs_folder, "gunicorn_access.log")
errorlog = os.path.join(logs_folder, "gunicorn_error.log")
loglevel = "info"
