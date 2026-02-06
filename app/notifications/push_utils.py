"""
Push notification utilities
"""
import json
import os


def send_push_notification(user_id, title, body, url=None, icon=None):
    """Send push notification to all user's subscriptions.
    Gracefully skip if pywebpush not installed or VAPID keys not configured."""
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return

    vapid_private_key = os.environ.get('VAPID_PRIVATE_KEY')
    vapid_public_key = os.environ.get('VAPID_PUBLIC_KEY')

    if not vapid_private_key or not vapid_public_key:
        return

    from app import db
    from app.models import PushSubscription

    subscriptions = PushSubscription.query.filter_by(
        user_id=user_id,
        is_active=True
    ).all()

    if not subscriptions:
        return

    payload = json.dumps({
        'title': title,
        'body': body,
        'url': url or '/',
        'icon': icon or '/static/icons/icon-192x192.png'
    })

    vapid_claims = {
        'sub': 'mailto:noreply@sonacip.it'
    }

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {
                        'p256dh': sub.p256dh_key,
                        'auth': sub.auth_key
                    }
                },
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims
            )
        except WebPushException as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 410:
                sub.is_active = False
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception:
            continue
