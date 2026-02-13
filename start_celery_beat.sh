#!/bin/bash
# Start Celery Beat scheduler for periodic tasks

cd "$(dirname "$0")"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set default Celery broker URL if not set
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:6379/0}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://localhost:6379/0}"

echo "⏰ Starting Celery Beat Scheduler..."
echo "Broker: $CELERY_BROKER_URL"

# Start Celery beat scheduler
celery -A celery_app.celery beat \
    --loglevel=info \
    --schedule=/tmp/celerybeat-schedule
