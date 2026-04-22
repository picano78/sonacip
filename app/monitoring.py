"""
System Monitoring and Health Checks
Provides endpoints and utilities to monitor system health
"""
from flask import Blueprint, jsonify, current_app
from app import db
from datetime import datetime, timezone
import psutil
import os


health_bp = Blueprint('health', __name__, url_prefix='/health')


@health_bp.route('/')
def health_check():
    """Basic health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '1.0.0'
    })


@health_bp.route('/detailed')
def detailed_health():
    """Detailed health check with system metrics"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '1.0.0',
        'components': {}
    }
    
    # Database health
    try:
        db.session.execute(db.text('SELECT 1'))
        health_status['components']['database'] = {
            'status': 'healthy',
            'type': current_app.config.get('SQLALCHEMY_DATABASE_URI', '').split(':')[0]
        }
    except Exception as e:
        health_status['components']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'degraded'
    
    # Redis health
    try:
        from app import cache
        cache.set('health_check', 'ok', timeout=1)
        result = cache.get('health_check')
        health_status['components']['cache'] = {
            'status': 'healthy' if result == 'ok' else 'degraded'
        }
    except Exception as e:
        health_status['components']['cache'] = {
            'status': 'unavailable',
            'error': str(e)
        }
    
    # Celery health
    try:
        from celery_app import celery
        inspect = celery.control.inspect()
        active = inspect.active()
        health_status['components']['celery'] = {
            'status': 'healthy' if active else 'unavailable',
            'workers': len(active) if active else 0
        }
    except Exception as e:
        health_status['components']['celery'] = {
            'status': 'unavailable',
            'error': str(e)
        }
    
    # System resources
    try:
        health_status['components']['system'] = {
            'status': 'healthy',
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent
        }
        
        # Mark degraded if resources are high
        if (psutil.cpu_percent() > 80 or 
            psutil.virtual_memory().percent > 85 or 
            psutil.disk_usage('/').percent > 90):
            health_status['status'] = 'degraded'
    except Exception as e:
        health_status['components']['system'] = {
            'status': 'unknown',
            'error': str(e)
        }
    
    return jsonify(health_status)


@health_bp.route('/metrics')
def metrics():
    """System metrics for monitoring"""
    from app.models import User, Post, Event, Notification
    
    metrics_data = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'database': {},
        'system': {},
        'application': {}
    }
    
    # Database metrics
    try:
        metrics_data['database'] = {
            'total_users': User.query.count(),
            'active_users': User.query.filter_by(is_active=True).count(),
            'total_posts': Post.query.count(),
            'total_events': Event.query.count(),
            'unread_notifications': Notification.query.filter_by(is_read=False).count()
        }
    except Exception as e:
        metrics_data['database']['error'] = str(e)
    
    # System metrics
    try:
        metrics_data['system'] = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_used_mb': psutil.virtual_memory().used / (1024 * 1024),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_used_gb': psutil.disk_usage('/').used / (1024 * 1024 * 1024),
            'disk_percent': psutil.disk_usage('/').percent,
            'process_count': len(psutil.pids())
        }
    except Exception as e:
        metrics_data['system']['error'] = str(e)
    
    # Application metrics
    try:
        from app.realtime import get_online_count
        metrics_data['application'] = {
            'online_users': get_online_count(),
            'uptime_seconds': int((datetime.now(timezone.utc) - 
                                  datetime.fromtimestamp(psutil.Process(os.getpid()).create_time(), 
                                                       tz=timezone.utc)).total_seconds())
        }
    except Exception as e:
        metrics_data['application']['error'] = str(e)
    
    return jsonify(metrics_data)


@health_bp.route('/ready')
def readiness():
    """Kubernetes-style readiness probe"""
    try:
        # Check if database is ready
        db.session.execute(db.text('SELECT 1'))
        
        # Check if critical tables exist
        from app.models import User
        User.query.first()
        
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'not ready',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 503


@health_bp.route('/live')
def liveness():
    """Kubernetes-style liveness probe"""
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200


@health_bp.route('/version')
def version():
    """Get application version"""
    return jsonify({
        'version': '1.0.0',
        'name': 'SONACIP',
        'description': 'Social CRM Platform for Sports Organizations',
        'python_version': os.sys.version,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


# Utility functions for monitoring

def check_database_connection():
    """Check if database is accessible"""
    try:
        db.session.execute(db.text('SELECT 1'))
        return True, None
    except Exception as e:
        return False, str(e)


def check_cache_connection():
    """Check if cache is accessible"""
    try:
        from app import cache
        cache.set('health_check', 'ok', timeout=1)
        return cache.get('health_check') == 'ok', None
    except Exception as e:
        return False, str(e)


def check_celery_workers():
    """Check if Celery workers are running"""
    try:
        from celery_app import celery
        inspect = celery.control.inspect()
        active = inspect.active()
        return active is not None and len(active) > 0, active
    except Exception as e:
        return False, str(e)


def get_system_stats():
    """Get current system statistics"""
    try:
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
    except Exception as e:
        return {'error': str(e)}


def alert_if_unhealthy(threshold_cpu=80, threshold_memory=85, threshold_disk=90):
    """
    Check system health and return alerts
    
    Returns:
        List of alert messages
    """
    alerts = []
    
    try:
        stats = get_system_stats()
        
        if stats.get('cpu_percent', 0) > threshold_cpu:
            alerts.append(f"High CPU usage: {stats['cpu_percent']}%")
        
        if stats.get('memory_percent', 0) > threshold_memory:
            alerts.append(f"High memory usage: {stats['memory_percent']}%")
        
        if stats.get('disk_percent', 0) > threshold_disk:
            alerts.append(f"High disk usage: {stats['disk_percent']}%")
        
        # Check database
        db_ok, db_error = check_database_connection()
        if not db_ok:
            alerts.append(f"Database connection failed: {db_error}")
        
        # Check cache
        cache_ok, cache_error = check_cache_connection()
        if not cache_ok:
            alerts.append(f"Cache connection failed: {cache_error}")
        
        # Check Celery
        celery_ok, celery_info = check_celery_workers()
        if not celery_ok:
            alerts.append(f"Celery workers not responding: {celery_info}")
    
    except Exception as e:
        alerts.append(f"Health check failed: {str(e)}")
    
    return alerts
