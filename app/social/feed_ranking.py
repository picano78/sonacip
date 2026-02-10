"""Feed ranking helpers shared by feed and admin preview."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import or_

from app.models import Connection, Post, SocialSetting, User


def _is_aware(dt) -> bool:
    try:
        return dt is not None and dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None
    except Exception:
        return False


def get_connection_ids(user: User) -> set[int]:
    try:
        connections = Connection.query.filter(
            or_(
                Connection.requester_id == user.id,
                Connection.addressee_id == user.id,
            ),
            Connection.status == 'accepted'
        ).all()
    except Exception:
        return set()

    ids: set[int] = set()
    for conn in connections:
        if conn.requester_id == user.id:
            ids.add(conn.addressee_id)
        else:
            ids.add(conn.requester_id)
    return ids


def _get_setting(settings: SocialSetting | None, name: str, default):
    if settings is None:
        return default
    val = getattr(settings, name, None)
    return default if val is None else val


def _engagement_score(post: Post, settings: SocialSetting | None) -> float:
    boosted_types = []
    muted_types = []
    if settings:
        try:
            import json
            boosted_types = json.loads(settings.boosted_types or '[]')
            muted_types = json.loads(settings.muted_types or '[]')
        except Exception:
            boosted_types = []
            muted_types = []

    # created_at can be naive depending on DB/backend; avoid aware/naive subtraction.
    created_at = getattr(post, "created_at", None)
    if created_at is None:
        age_hours = 9999.0
    else:
        if _is_aware(created_at):
            now = datetime.now(timezone.utc)
            try:
                created_norm = created_at.astimezone(timezone.utc)
            except Exception:
                created_norm = created_at
            age_hours = max((now - created_norm).total_seconds() / 3600, 0.1)
        else:
            now = datetime.utcnow()
            age_hours = max((now - created_at).total_seconds() / 3600, 0.1)
    recency = max(0, 48 - age_hours) / 48
    base_engagement = (post.likes_count * 2) + (post.comments_count * 3)
    score = (base_engagement * _get_setting(settings, 'weight_engagement', 1.0))
    score += (recency * 5 * _get_setting(settings, 'weight_recency', 1.0))

    promo_end = getattr(post, "promotion_ends_at", None)
    if post.is_promoted and promo_end:
        if _is_aware(promo_end):
            is_active_promo = promo_end > datetime.now(timezone.utc)
        else:
            is_active_promo = promo_end > datetime.utcnow()
    else:
        is_active_promo = False

    if is_active_promo:
        score += _get_setting(settings, 'weight_promoted', 20.0)
    if post.is_promoted and settings and settings.boost_official:
        score += 5
    if post.author and post.author.is_society():
        score += _get_setting(settings, 'weight_official', 30.0)
    if post.post_type and any(token in post.post_type for token in ['tournament', 'match']):
        score += _get_setting(settings, 'weight_tournament', 20.0)
    if post.post_type and 'automation' in post.post_type:
        score += _get_setting(settings, 'weight_automation', 10.0)
    if boosted_types and post.post_type:
        for t in boosted_types:
            if t in post.post_type:
                score += 5
    if muted_types and post.post_type:
        for t in muted_types:
            if t in post.post_type:
                score -= 10

    return score


def _priority_for(post: Post, user: User, followed_ids: set[int], friend_ids: set[int], settings: SocialSetting | None) -> int:
    followed_priority = _get_setting(settings, 'priority_followed', 0)
    friends_priority = _get_setting(settings, 'priority_friends', 1)
    others_priority = _get_setting(settings, 'priority_others', 2)

    if post.user_id == user.id or post.user_id in followed_ids:
        return int(followed_priority)
    if post.user_id in friend_ids:
        return int(friends_priority)
    return int(others_priority)


def score_feed_posts(
    posts: Iterable[Post],
    user: User,
    followed_ids: set[int],
    friend_ids: set[int],
    settings: SocialSetting | None,
) -> list[Post]:
    def sort_key(post: Post):
        ts = post.created_at.timestamp() if post.created_at else 0
        priority = _priority_for(post, user, followed_ids, friend_ids, settings)
        return (priority, -_engagement_score(post, settings), -ts)

    return sorted(posts, key=sort_key)


def rank_feed_posts(
    posts: Iterable[Post],
    user: User,
    followed_ids: set[int],
    friend_ids: set[int],
    settings: SocialSetting | None,
) -> list[dict]:
    ranked = []
    for post in posts:
        ranked.append({
            'post': post,
            'priority': _priority_for(post, user, followed_ids, friend_ids, settings),
            'score': _engagement_score(post, settings),
        })

    ranked.sort(key=lambda item: (
        item['priority'],
        -(item['score'] or 0),
        -(item['post'].created_at.timestamp() if item['post'].created_at else 0),
    ))
    return ranked
