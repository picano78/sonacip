"""
Live Streaming Routes
Handles live stream creation, viewing, and management
No video storage on server - uses WebRTC for peer-to-peer streaming
Enhanced with WebSocket support for real-time features
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import LiveStream, LiveStreamViewer, User
from datetime import datetime, timezone
import secrets
import json

bp = Blueprint('livestream', __name__, url_prefix='/livestream')

# Import WebSocket events to register them
try:
    from app.livestream import events
except Exception:
    pass  # WebSocket events not available


@bp.before_request
def _check_feature():
    """Check if live streaming feature is enabled"""
    from app.utils import check_feature_enabled
    if not check_feature_enabled('livestream'):
        flash('La funzionalità di live streaming non è attualmente disponibile.', 'warning')
        return redirect(url_for('main.dashboard'))


@bp.route('/')
@login_required
def index():
    """Show active live streams"""
    active_streams = LiveStream.query.filter_by(is_active=True).order_by(LiveStream.started_at.desc()).all()
    user_stream = LiveStream.query.filter_by(user_id=current_user.id, is_active=True).first()
    return render_template('livestream/index.html', 
                         active_streams=active_streams,
                         user_stream=user_stream)


@bp.route('/start', methods=['POST'])
@login_required
def start_stream():
    """Start a new live stream"""
    # Check if user already has an active stream
    existing = LiveStream.query.filter_by(user_id=current_user.id, is_active=True).first()
    if existing:
        return jsonify({'error': 'Hai già una diretta attiva'}), 400
    
    title = request.json.get('title', '').strip()
    description = request.json.get('description', '').strip()
    
    if not title:
        title = f"Diretta di {current_user.get_full_name()}"
    
    # Generate unique room ID for WebRTC signaling
    room_id = secrets.token_urlsafe(32)
    
    stream = LiveStream(
        user_id=current_user.id,
        title=title,
        description=description,
        room_id=room_id,
        is_active=True
    )
    
    db.session.add(stream)
    db.session.commit()
    
    current_app.logger.info(f"Live stream started: user={current_user.id} stream={stream.id} room={room_id}")
    
    return jsonify({
        'success': True,
        'stream_id': stream.id,
        'room_id': room_id,
        'stream_url': url_for('livestream.broadcast', stream_id=stream.id)
    })


@bp.route('/<int:stream_id>/stop', methods=['POST'])
@login_required
def stop_stream(stream_id):
    """Stop an active live stream"""
    stream = LiveStream.query.get_or_404(stream_id)
    
    # Only the streamer can stop their own stream
    if stream.user_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Non autorizzato'}), 403
    
    stream.is_active = False
    stream.ended_at = datetime.now(timezone.utc)
    
    # Close all viewer sessions
    active_viewers = LiveStreamViewer.query.filter_by(
        stream_id=stream_id,
        left_at=None
    ).all()
    
    for viewer in active_viewers:
        viewer.left_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    current_app.logger.info(f"Live stream stopped: stream={stream_id} duration={stream.duration_seconds}s")
    
    return jsonify({
        'success': True,
        'duration': stream.duration_seconds
    })


@bp.route('/<int:stream_id>/broadcast')
@login_required
def broadcast(stream_id):
    """Broadcaster view - stream your video"""
    stream = LiveStream.query.get_or_404(stream_id)
    
    # Only the streamer can access the broadcast page
    if stream.user_id != current_user.id:
        flash('Non sei autorizzato ad accedere a questa diretta.', 'danger')
        return redirect(url_for('livestream.index'))
    
    if not stream.is_active:
        flash('Questa diretta è terminata.', 'warning')
        return redirect(url_for('livestream.index'))
    
    return render_template('livestream/broadcast.html', stream=stream)


@bp.route('/<int:stream_id>/watch')
@login_required
def watch(stream_id):
    """Viewer page - watch a live stream"""
    stream = LiveStream.query.get_or_404(stream_id)
    
    if not stream.is_active:
        flash('Questa diretta è terminata.', 'warning')
        return redirect(url_for('livestream.index'))
    
    # Track viewer
    existing_viewer = LiveStreamViewer.query.filter_by(
        stream_id=stream_id,
        viewer_id=current_user.id,
        left_at=None
    ).first()
    
    if not existing_viewer:
        viewer = LiveStreamViewer(
            stream_id=stream_id,
            viewer_id=current_user.id
        )
        db.session.add(viewer)
        
        # Update viewer count
        stream.viewer_count = LiveStreamViewer.query.filter_by(
            stream_id=stream_id,
            left_at=None
        ).count() + 1
        
        if stream.viewer_count > stream.peak_viewers:
            stream.peak_viewers = stream.viewer_count
        
        db.session.commit()
    
    return render_template('livestream/watch.html', stream=stream)


@bp.route('/<int:stream_id>/leave', methods=['POST'])
@login_required
def leave_stream(stream_id):
    """Mark viewer as having left the stream"""
    viewer = LiveStreamViewer.query.filter_by(
        stream_id=stream_id,
        viewer_id=current_user.id,
        left_at=None
    ).first()
    
    if viewer:
        viewer.left_at = datetime.now(timezone.utc)
        
        # Update viewer count
        stream = db.session.get(LiveStream, stream_id)
        if stream:
            active_count = LiveStreamViewer.query.filter_by(
                stream_id=stream_id,
                left_at=None
            ).count()
            stream.viewer_count = max(0, active_count)
        
        db.session.commit()
    
    return jsonify({'success': True})


@bp.route('/<int:stream_id>/info')
@login_required
def stream_info(stream_id):
    """Get stream information"""
    stream = LiveStream.query.get_or_404(stream_id)
    
    active_viewers = LiveStreamViewer.query.filter_by(
        stream_id=stream_id,
        left_at=None
    ).count()
    
    return jsonify({
        'id': stream.id,
        'title': stream.title,
        'description': stream.description,
        'is_active': stream.is_active,
        'streamer': {
            'id': stream.streamer.id,
            'name': stream.streamer.get_full_name(),
            'avatar': stream.streamer.avatar
        },
        'viewer_count': active_viewers,
        'peak_viewers': stream.peak_viewers,
        'duration': stream.duration_seconds,
        'started_at': stream.started_at.isoformat(),
        'room_id': stream.room_id if stream.user_id == current_user.id else None
    })


@bp.route('/active')
@login_required
def active_streams():
    """Get list of active streams"""
    streams = LiveStream.query.filter_by(is_active=True).order_by(LiveStream.started_at.desc()).all()
    
    result = []
    for stream in streams:
        active_viewers = LiveStreamViewer.query.filter_by(
            stream_id=stream.id,
            left_at=None
        ).count()
        
        result.append({
            'id': stream.id,
            'title': stream.title,
            'streamer': {
                'id': stream.streamer.id,
                'name': stream.streamer.get_full_name(),
                'avatar': stream.streamer.avatar
            },
            'viewer_count': active_viewers,
            'duration': stream.duration_seconds
        })
    
    return jsonify(result)


@bp.route('/<int:stream_id>/signal', methods=['POST'])
@login_required
def signal(stream_id):
    """WebRTC signaling endpoint"""
    stream = LiveStream.query.get_or_404(stream_id)
    
    if not stream.is_active:
        return jsonify({'error': 'Stream not active'}), 400
    
    # WebSocket signaling is now handled by events.py
    # This endpoint is kept for compatibility
    data = request.json
    
    return jsonify({
        'success': True,
        'message': 'Use WebSocket connection for real-time signaling',
        'relay': data
    })


@bp.route('/<int:stream_id>/quality', methods=['POST'])
@login_required
def set_quality(stream_id):
    """Set stream quality preference"""
    stream = LiveStream.query.get_or_404(stream_id)
    
    if stream.user_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    
    quality = request.json.get('quality', 'auto')
    allowed_qualities = ['low', 'medium', 'high', 'auto']
    
    if quality not in allowed_qualities:
        return jsonify({'error': 'Invalid quality setting'}), 400
    
    # Store quality preference (could add field to model if needed)
    current_app.logger.info(f"Stream {stream_id} quality set to {quality}")
    
    return jsonify({
        'success': True,
        'quality': quality
    })


@bp.route('/<int:stream_id>/analytics')
@login_required
def stream_analytics(stream_id):
    """Get detailed stream analytics"""
    stream = LiveStream.query.get_or_404(stream_id)
    
    # Only streamer and admins can see analytics
    if stream.user_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Not authorized'}), 403
    
    # Get viewer statistics
    total_viewers = LiveStreamViewer.query.filter_by(stream_id=stream_id).count()
    active_viewers = LiveStreamViewer.query.filter_by(
        stream_id=stream_id,
        left_at=None
    ).count()
    
    # Calculate average watch time
    completed_viewers = LiveStreamViewer.query.filter(
        LiveStreamViewer.stream_id == stream_id,
        LiveStreamViewer.left_at.is_not(None)
    ).all()
    
    if completed_viewers:
        total_watch_time = sum(
            (v.left_at - v.joined_at).total_seconds()
            for v in completed_viewers
        )
        avg_watch_time = total_watch_time / len(completed_viewers)
    else:
        avg_watch_time = 0
    
    return jsonify({
        'stream_id': stream.id,
        'title': stream.title,
        'total_viewers': total_viewers,
        'active_viewers': active_viewers,
        'peak_viewers': stream.peak_viewers,
        'duration_seconds': stream.duration_seconds,
        'average_watch_time': round(avg_watch_time, 2),
        'is_active': stream.is_active
    })
