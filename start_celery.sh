#!/bin/bash
# Start Celery worker for background tasks

cd "$(dirname "$0")"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set default Celery broker URL if not set
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:6379/0}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://localhost:6379/0}"

echo "🚀 Starting Celery Worker..."
echo "Broker: $CELERY_BROKER_URL"
echo "Backend: $CELERY_RESULT_BACKEND"

# Start Celery worker with auto-reload for development
celery -A celery_app.celery worker \
    --loglevel=info \
    --concurrency=4 \
    --max-tasks-per-child=1000 \
    --task-events \
    --without-gossip \
    --without-mingle \
    --without-heartbeat
