"""
WebSocket Events for Live Streaming
Handles WebRTC signaling and real-time chat
"""
from flask import request
from flask_login import current_user
from app import db
from app.models import LiveStream, LiveStreamViewer, User
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Import SocketIO if available
try:
    from flask_socketio import emit, join_room, leave_room, rooms
    from app import socketio
    SOCKETIO_AVAILABLE = socketio is not None
except Exception:
    SOCKETIO_AVAILABLE = False
    socketio = None


if SOCKETIO_AVAILABLE and socketio:
    
    @socketio.on('join_stream')
    def handle_join_stream(data):
        """Join a livestream room for WebRTC signaling and chat"""
        try:
            stream_id = data.get('stream_id')
            if not stream_id:
                return {'error': 'Stream ID required'}
            
            stream = LiveStream.query.get(stream_id)
            if not stream or not stream.is_active:
                return {'error': 'Stream not found or inactive'}
            
            room = f'stream_{stream_id}'
            join_room(room)
            
            # Track viewer if not the streamer
            if current_user.is_authenticated and current_user.id != stream.user_id:
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
                    active_count = LiveStreamViewer.query.filter_by(
                        stream_id=stream_id,
                        left_at=None
                    ).count() + 1
                    
                    stream.viewer_count = active_count
                    if stream.viewer_count > stream.peak_viewers:
                        stream.peak_viewers = stream.viewer_count
                    
                    db.session.commit()
            
            # Notify room about new viewer
            user_name = current_user.get_full_name() if current_user.is_authenticated else 'Guest'
            emit('viewer_joined', {
                'viewer_name': user_name,
                'viewer_count': stream.viewer_count
            }, room=room, include_self=False)
            
            return {'success': True, 'viewer_count': stream.viewer_count}
            
        except Exception as e:
            logger.error(f"Error joining stream: {e}")
            return {'error': str(e)}
    
    
    @socketio.on('leave_stream')
    def handle_leave_stream(data):
        """Leave a livestream room"""
        try:
            stream_id = data.get('stream_id')
            if not stream_id:
                return {'error': 'Stream ID required'}
            
            room = f'stream_{stream_id}'
            leave_room(room)
            
            # Update viewer record
            if current_user.is_authenticated:
                viewer = LiveStreamViewer.query.filter_by(
                    stream_id=stream_id,
                    viewer_id=current_user.id,
                    left_at=None
                ).first()
                
                if viewer:
                    viewer.left_at = datetime.now(timezone.utc)
                    
                    # Update viewer count
                    stream = LiveStream.query.get(stream_id)
                    if stream:
                        active_count = LiveStreamViewer.query.filter_by(
                            stream_id=stream_id,
                            left_at=None
                        ).count()
                        stream.viewer_count = max(0, active_count)
                    
                    db.session.commit()
                    
                    # Notify room
                    user_name = current_user.get_full_name()
                    emit('viewer_left', {
                        'viewer_name': user_name,
                        'viewer_count': stream.viewer_count if stream else 0
                    }, room=room)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error leaving stream: {e}")
            return {'error': str(e)}
    
    
    @socketio.on('webrtc_offer')
    def handle_webrtc_offer(data):
        """Relay WebRTC offer from broadcaster to viewers"""
        try:
            stream_id = data.get('stream_id')
            offer = data.get('offer')
            
            if not stream_id or not offer:
                return {'error': 'Invalid data'}
            
            room = f'stream_{stream_id}'
            emit('webrtc_offer', {
                'offer': offer,
                'from': current_user.id if current_user.is_authenticated else None
            }, room=room, include_self=False)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error relaying WebRTC offer: {e}")
            return {'error': str(e)}
    
    
    @socketio.on('webrtc_answer')
    def handle_webrtc_answer(data):
        """Relay WebRTC answer from viewer to broadcaster"""
        try:
            stream_id = data.get('stream_id')
            answer = data.get('answer')
            to_user = data.get('to')
            
            if not stream_id or not answer:
                return {'error': 'Invalid data'}
            
            room = f'stream_{stream_id}'
            emit('webrtc_answer', {
                'answer': answer,
                'from': current_user.id if current_user.is_authenticated else None
            }, room=room, include_self=False)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error relaying WebRTC answer: {e}")
            return {'error': str(e)}
    
    
    @socketio.on('webrtc_ice_candidate')
    def handle_ice_candidate(data):
        """Relay ICE candidates for WebRTC connection"""
        try:
            stream_id = data.get('stream_id')
            candidate = data.get('candidate')
            
            if not stream_id or not candidate:
                return {'error': 'Invalid data'}
            
            room = f'stream_{stream_id}'
            emit('webrtc_ice_candidate', {
                'candidate': candidate,
                'from': current_user.id if current_user.is_authenticated else None
            }, room=room, include_self=False)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error relaying ICE candidate: {e}")
            return {'error': str(e)}
    
    
    @socketio.on('stream_chat_message')
    def handle_chat_message(data):
        """Handle chat messages during livestream"""
        try:
            if not current_user.is_authenticated:
                return {'error': 'Authentication required'}
            
            stream_id = data.get('stream_id')
            message = data.get('message', '').strip()
            
            if not stream_id or not message:
                return {'error': 'Invalid data'}
            
            if len(message) > 500:
                return {'error': 'Message too long'}
            
            stream = LiveStream.query.get(stream_id)
            if not stream or not stream.is_active:
                return {'error': 'Stream not found or inactive'}
            
            room = f'stream_{stream_id}'
            emit('stream_chat_message', {
                'user_id': current_user.id,
                'user_name': current_user.get_full_name(),
                'user_avatar': current_user.avatar,
                'message': message,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }, room=room)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error sending chat message: {e}")
            return {'error': str(e)}
    
    
    @socketio.on('stream_quality_change')
    def handle_quality_change(data):
        """Notify when broadcaster changes stream quality"""
        try:
            stream_id = data.get('stream_id')
            quality = data.get('quality')
            
            if not stream_id or not quality:
                return {'error': 'Invalid data'}
            
            stream = LiveStream.query.get(stream_id)
            if not stream or stream.user_id != current_user.id:
                return {'error': 'Unauthorized'}
            
            room = f'stream_{stream_id}'
            emit('stream_quality_changed', {
                'quality': quality
            }, room=room, include_self=False)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error changing stream quality: {e}")
            return {'error': str(e)}
    
    
    @socketio.on('stream_stats_update')
    def handle_stats_update(data):
        """Broadcaster sends stream statistics"""
        try:
            stream_id = data.get('stream_id')
            stats = data.get('stats', {})
            
            if not stream_id:
                return {'error': 'Stream ID required'}
            
            stream = LiveStream.query.get(stream_id)
            if not stream or stream.user_id != current_user.id:
                return {'error': 'Unauthorized'}
            
            # Could store stats in database if needed
            # For now, just relay to monitoring dashboards
            room = f'stream_{stream_id}_admin'
            emit('stream_stats', {
                'stream_id': stream_id,
                'stats': stats,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }, room=room)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error updating stream stats: {e}")
            return {'error': str(e)}
