"""
Stream Monetization - Donations and Tips
Allows viewers to support streamers with tips/donations
"""
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models import LiveStream, User
from datetime import datetime, timezone
import os
import stripe

bp = Blueprint('stream_donations', __name__, url_prefix='/livestream/donations')


def _init_stripe():
    """Initialize Stripe API key"""
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY') or current_app.config.get('STRIPE_SECRET_KEY')


@bp.route('/<int:stream_id>/tip', methods=['POST'])
@login_required
def send_tip(stream_id):
    """Send a tip/donation to streamer"""
    stream = LiveStream.query.get_or_404(stream_id)
    
    if not stream.is_active:
        return jsonify({'error': 'Stream is not active'}), 400
    
    if stream.user_id == current_user.id:
        return jsonify({'error': 'Cannot tip your own stream'}), 400
    
    try:
        amount = float(request.json.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid amount'}), 400
    
    if amount < 1.0 or amount > 1000.0:
        return jsonify({'error': 'Amount must be between 1 and 1000 EUR'}), 400
    
    message = request.json.get('message', '').strip()
    if len(message) > 200:
        return jsonify({'error': 'Message too long (max 200 characters)'}), 400
    
    _init_stripe()
    if not stripe.api_key:
        return jsonify({'error': 'Payment system not configured'}), 500
    
    amount_cents = int(amount * 100)
    
    try:
        # Create Stripe Payment Intent
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='eur',
            metadata={
                'stream_id': str(stream_id),
                'streamer_id': str(stream.user_id),
                'tipper_id': str(current_user.id),
                'message': message
            },
            description=f'Tip for stream: {stream.title}'
        )
        
        # Create donation record (if we have a Donation model)
        # For now, we'll track it via Stripe metadata
        
        return jsonify({
            'success': True,
            'client_secret': intent.client_secret,
            'amount': amount,
            'message': message
        })
        
    except Exception as e:
        current_app.logger.error(f"Error creating tip payment: {e}")
        return jsonify({'error': 'Payment processing failed'}), 500


@bp.route('/<int:stream_id>/tips')
@login_required  
def get_tips(stream_id):
    """Get tips for a stream (streamer only)"""
    stream = LiveStream.query.get_or_404(stream_id)
    
    if stream.user_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Not authorized'}), 403
    
    # In production, query Donation model or Stripe
    # For now, return placeholder
    return jsonify({
        'stream_id': stream_id,
        'total_tips': 0,
        'tip_count': 0,
        'tips': []
    })


@bp.route('/webhook', methods=['POST'])
def tip_webhook():
    """Stripe webhook for tip completion"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    _init_stripe()
    wh_secret = os.environ.get('STRIPE_TIP_WEBHOOK_SECRET') or current_app.config.get('STRIPE_TIP_WEBHOOK_SECRET')
    
    try:
        if wh_secret and sig_header:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=wh_secret
            )
        else:
            import json
            event = json.loads(payload.decode('utf-8'))
    except Exception as e:
        current_app.logger.error(f"Webhook error: {e}")
        return ('bad payload', 400)
    
    if event.get('type') == 'payment_intent.succeeded':
        intent = event['data']['object']
        metadata = intent.get('metadata', {})
        
        stream_id = metadata.get('stream_id')
        streamer_id = metadata.get('streamer_id')
        tipper_id = metadata.get('tipper_id')
        message = metadata.get('message', '')
        
        if stream_id and streamer_id:
            # Send notification to streamer
            from app.notifications.utils import create_notification
            
            amount = intent.get('amount', 0) / 100.0
            tipper = db.session.get(User, tipper_id) if tipper_id else None
            tipper_name = tipper.get_full_name() if tipper else 'Anonymous'
            
            create_notification(
                user_id=int(streamer_id),
                notification_type='stream_tip',
                title='Nuova Donazione!',
                message=f'{tipper_name} ti ha inviato €{amount:.2f}! "{message}"',
                link=f'/livestream/{stream_id}/broadcast'
            )
            
            # Broadcast to stream room via WebSocket
            try:
                from app import socketio
                if socketio:
                    socketio.emit('new_tip', {
                        'amount': amount,
                        'tipper_name': tipper_name,
                        'message': message
                    }, room=f'stream_{stream_id}')
            except Exception:
                pass
    
    return ('ok', 200)
