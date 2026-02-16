"""
Database Models
All SQLAlchemy models for SONACIP platform
"""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.hybrid import hybrid_property
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.utils import check_permission

logger = logging.getLogger(__name__)


def utc_now():
    """Helper function for SQLAlchemy default timestamps."""
    return datetime.now(timezone.utc)


# Association tables for many-to-many relationships
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=utc_now)
)

post_likes = db.Table('post_likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=utc_now)
)

event_athletes = db.Table('event_athletes',
    db.Column('event_id', db.Integer, db.ForeignKey('event.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('status', db.String(20), default='pending'),  # pending, accepted, rejected
    db.Column('created_at', db.DateTime, default=utc_now),
    db.Column('responded_at', db.DateTime)
)

# Society Calendar association tables (director-level calendar, not field planner)
society_calendar_event_staff = db.Table('society_calendar_event_staff',
    db.Column('event_id', db.Integer, db.ForeignKey('society_calendar_event.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=utc_now)
)

society_calendar_event_athletes = db.Table('society_calendar_event_athletes',
    db.Column('event_id', db.Integer, db.ForeignKey('society_calendar_event.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=utc_now)
)


class SocietyCalendarAttendance(db.Model):
    """
    RSVP tracking for society calendar convocations (per athlete).
    """
    __tablename__ = 'society_calendar_attendance'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('society_calendar_event.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, accepted, declined
    responded_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    __table_args__ = (
        db.UniqueConstraint('event_id', 'user_id', name='uq_society_calendar_attendance'),
    )


class SocietyCalendarReminderSent(db.Model):
    """
    Idempotency for calendar reminder jobs (per event/user/kind).
    """
    __tablename__ = 'society_calendar_reminder_sent'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('society_calendar_event.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    kind = db.Column(db.String(50), nullable=False)  # e.g. '24h', '1h'
    sent_at = db.Column(db.DateTime, default=utc_now, index=True)

    __table_args__ = (
        db.UniqueConstraint('event_id', 'user_id', 'kind', name='uq_society_calendar_reminder_sent'),
    )


class User(UserMixin, db.Model):
    """
    User model - handles all user types
    Roles live in the Role table (super_admin, society_admin, coach, athlete, staff, etc.)
    """
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Profile information
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    bio = db.Column(db.Text)
    avatar = db.Column(db.String(255))  # path to avatar image
    cover_photo = db.Column(db.String(255))  # path to cover photo
    
    # Role and type (database-driven)
    role_legacy = db.Column('role', db.String(50), nullable=True, server_default='super_admin')  # Legacy compatibility
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    
    # For Società Sportiva
    company_name = db.Column(db.String(200))  # Nome società
    company_type = db.Column(db.String(50))   # ASD, SSD, etc.
    vat_number = db.Column(db.String(50))     # Partita IVA
    fiscal_code = db.Column(db.String(50))    # Codice fiscale
    address = db.Column(db.String(255))
    city = db.Column(db.String(100))
    province = db.Column(db.String(2))
    postal_code = db.Column(db.String(10))
    website = db.Column(db.String(255))
    
    # For Staff
    staff_role = db.Column(db.String(50))     # coach, dirigente, etc.
    society_id = db.Column(db.Integer, db.ForeignKey('society.id', use_alter=True))  # Link to società
    
    # For Atleta
    birth_date = db.Column(db.Date)
    sport = db.Column(db.String(100))
    athlete_society_id = db.Column(db.Integer, db.ForeignKey('society.id', use_alter=True))  # Link to società
    
    # Account status
    is_active = db.Column(db.Boolean, default=True)
    is_banned = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    email_confirmed = db.Column(db.Boolean, default=False)
    email_confirm_token = db.Column(db.String(128), index=True)
    email_confirm_sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    last_seen = db.Column(db.DateTime, default=utc_now)
    
    # Language preference
    language = db.Column(db.String(5), default='it')  # 'it' or 'en'
    
    # Relationships
    role_obj = db.relationship('Role', foreign_keys=[role_id])
    permission_overrides = db.relationship('UserPermissionOverride', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    society = db.relationship('Society', foreign_keys=[society_id], backref=db.backref('staff_members', lazy='dynamic'))
    athlete_society = db.relationship('Society', foreign_keys=[athlete_society_id], backref=db.backref('athletes', lazy='dynamic'))
    posts = db.relationship('Post', backref='author', lazy='dynamic', 
                           foreign_keys='Post.user_id')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    notifications = db.relationship('Notification', backref='recipient', 
                                   lazy='dynamic', foreign_keys='Notification.user_id')
    
    # Following/Followers relationship
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'),
        lazy='dynamic'
    )
    
    # Events created (for società/staff)
    events_created = db.relationship('Event', backref='creator', lazy='dynamic',
                                    foreign_keys='Event.creator_id')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    def follow(self, user):
        """Follow another user"""
        if not self.is_following(user):
            self.followed.append(user)
    
    def unfollow(self, user):
        """Unfollow a user"""
        if self.is_following(user):
            self.followed.remove(user)
    
    def is_following(self, user):
        """Check if following a user"""
        return self.followed.filter(
            followers.c.followed_id == user.id).count() > 0
    
    def get_feed_posts(self):
        """Get posts for user's feed"""
        followed_posts = Post.query.join(
            followers, (followers.c.followed_id == Post.user_id)).filter(
            followers.c.follower_id == self.id)
        own_posts = Post.query.filter_by(user_id=self.id)
        return followed_posts.union(own_posts).order_by(Post.created_at.desc())
    
    @hybrid_property
    def role(self):
        """Return role name (derived from Role table)."""
        return self.role_obj.name if self.role_obj else None

    @role.expression
    def role(cls):
        return (
            db.select(Role.name)
            .where(Role.id == cls.role_id)
            .scalar_subquery()
        )

    @role.setter
    def role(self, role_name):
        from app.models import Role
        role_obj = Role.query.filter_by(name=role_name).first()
        if not role_obj:
            # Fallback to base role to avoid invalid references
            role_obj = Role.query.filter_by(name='appassionato').first()
        self.role_obj = role_obj
        self.role_legacy = role_name

    @property
    def role_display_name(self):
        return self.role_obj.display_name if self.role_obj else None

    def is_admin(self):
        """Check if user is super admin"""
        return self.role == 'super_admin'

    def is_society(self):
        """Check if user is a società/society admin"""
        return self.role in ('societa', 'society_admin')

    def is_society_admin(self):
        """Check if user is society admin"""
        return self.role in ('society_admin', 'societa')

    def is_staff(self):
        """Check if user is staff or coach"""
        return self.role in ('staff', 'coach')

    def is_coach(self):
        """Check if user is coach"""
        return self.role == 'coach'

    def is_athlete(self):
        """Check if user is an athlete"""
        return self.role in ('atleta', 'athlete')
    
    def get_full_name(self):
        """Get full name or company name"""
        if self.is_society() and self.society_profile and self.society_profile.legal_name:
            return self.society_profile.legal_name
        if self.is_society() and self.company_name:
            return self.company_name
        elif self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def has_permission(self, resource, action):
        """
        Check if user has a specific permission
        Super admin always has all permissions
        """
        if self.is_admin():
            return True
        
        # Get role object from database
        if not self.role_obj:
            return False
        
        # Check if role has the permission
        perm = Permission.query.filter_by(resource=resource, action=action).first()
        if not perm:
            return False
        
        base_allowed = perm in self.role_obj.permissions.all()
        override = UserPermissionOverride.query.filter_by(user_id=self.id, permission_id=perm.id).first()
        if override:
            return True if override.effect == 'allow' else False

        return base_allowed

    def can_access_society(self, society_id: int | None) -> bool:
        """Return True if user is scoped to the given society (or no scope requested)."""
        if not society_id:
            return True
        # Society owners can always access their own society scope.
        if self.is_society() and self.society_profile and self.society_profile.id == society_id:
            return True
        # Staff/athletes can access if they have an active membership for that society.
        try:
            from app.models import SocietyMembership
            return (
                SocietyMembership.query.filter_by(
                    society_id=society_id, user_id=self.id, status='active'
                ).first()
                is not None
            )
        except Exception:
            # Fallback to legacy fields if DB isn't ready yet.
            society = self.get_primary_society()
            if not society:
                return False
            return society.id == society_id

    def get_society_role(self, society_id: int | None) -> str | None:
        """Return the society-specific role_name (from SocietyMembership) for a given society."""
        if not society_id:
            return None
        if self.is_society() and self.society_profile and self.society_profile.id == society_id:
            return 'societa'
        try:
            from app.models import SocietyMembership
            m = SocietyMembership.query.filter_by(
                society_id=society_id, user_id=self.id, status='active'
            ).first()
            return m.role_name if m else None
        except Exception:
            return None

    def get_primary_society(self):
        """Return Society entity for this user, if any."""
        if self.is_society() and self.society_profile:
            return self.society_profile
        # Prefer explicit memberships (canonical) when present.
        try:
            from app.models import SocietyMembership
            m = SocietyMembership.query.filter_by(user_id=self.id, status='active').order_by(SocietyMembership.created_at.desc()).first()
            if m and m.society:
                return m.society
        except Exception:
            pass
        if self.society_id:
            return self.society
        if self.athlete_society_id:
            return self.athlete_society
        return None
    
    def get_active_subscription(self):
        """Get user's active subscription"""
        from app.models import Subscription
        society = self.get_primary_society()
        if society:
            sub = Subscription.query.filter_by(
                society_id=society.id,
                status='active'
            ).first()
            if sub:
                return sub
        return Subscription.query.filter_by(
            user_id=self.id,
            status='active'
        ).first()
    
    def has_feature(self, feature_name):
        """
        Check if user has access to a specific feature based on their plan.
        Super admin controls which features are premium vs free via PlatformFeature.
        """
        if self.is_admin():
            return True

        try:
            from app.models import PlatformFeature
            pf = PlatformFeature.query.filter_by(key=feature_name).first()
            if pf:
                if not pf.is_enabled:
                    return False
                if not pf.is_premium:
                    return True
        except Exception:
            pass

        # 1) Plan-based features (if a subscription exists)
        subscription = self.get_active_subscription()
        if subscription and subscription.plan:
            plan = subscription.plan
            feature_map = {
                'crm': bool(plan.has_crm),
                'advanced_stats': bool(plan.has_advanced_stats),
                'api_access': bool(plan.has_api_access),
                'white_label': bool(plan.has_white_label),
                'priority_support': bool(plan.has_priority_support),
            }
            if bool(feature_map.get(feature_name, False)):
                return True

        # 2) Add-on entitlements (paid add-ons can unlock features even if the plan doesn't)
        try:
            from app.models import AddOnEntitlement
            now = datetime.now(timezone.utc)
            scope = self.get_primary_society()
            q = AddOnEntitlement.query.filter_by(feature_key=feature_name, status='active')
            if scope:
                q = q.filter(AddOnEntitlement.society_id == scope.id)
            else:
                q = q.filter(AddOnEntitlement.user_id == self.id)
            ent = q.order_by(AddOnEntitlement.created_at.desc()).first()
            if not ent:
                return False
            if ent.end_date and ent.end_date <= now:
                return False
            return True
        except Exception:
            return False
    
    def can_add_athlete(self):
        """Check if user can add more athletes based on plan limits"""
        if self.is_admin():
            return True
        
        if not self.is_society():
            return False
        
        subscription = self.get_active_subscription()
        if not subscription or not subscription.plan:
            return False
        
        plan = subscription.plan
        if plan.max_athletes is None:  # Unlimited
            return True
        
        current_athletes = User.query.filter_by(
            athlete_society_id=self.id,
            is_active=True
        ).count()
        
        return current_athletes < plan.max_athletes
    
    def __repr__(self):
        return f'<User {self.username}>'


class Post(db.Model):
    """
    Social post model - LinkedIn-style posts with hashtags and scheduling
    """
    __tablename__ = 'post'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255))  # optional image
    
    # Visibility
    is_public = db.Column(db.Boolean, default=True)
    # New: explicit audience/scoping (for society CRM communications)
    audience = db.Column(db.String(20), default='public')  # public, followers, society, direct
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))  # owning society for scoped comms
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # direct-to user comms
    post_type = db.Column(db.String(50), default='personal')  # personal, official, tournament, match, automation

    # Scheduling
    is_scheduled = db.Column(db.Boolean, default=False)
    scheduled_for = db.Column(db.DateTime, index=True)  # When to publish scheduled post
    published_at = db.Column(db.DateTime)  # Actual publication time
    
    # Status
    status = db.Column(db.String(20), default='published')  # draft, scheduled, published, archived

    # Promotion/ads
    is_promoted = db.Column(db.Boolean, default=False)
    promotion_starts_at = db.Column(db.DateTime)
    promotion_ends_at = db.Column(db.DateTime)
    promotion_views_target = db.Column(db.Integer)
    promotion_views = db.Column(db.Integer, default=0)
    promotion_amount = db.Column(db.Float)  # amount paid for promotion
    
    # Engagement
    likes_count = db.Column(db.Integer, default=0)
    comments_count = db.Column(db.Integer, default=0)
    shares_count = db.Column(db.Integer, default=0)
    views_count = db.Column(db.Integer, default=0)
    
    # Link preview (for external URLs like YouTube, Instagram, TikTok)
    link_url = db.Column(db.String(500))  # The extracted URL
    link_title = db.Column(db.String(255))  # Title from metadata
    link_description = db.Column(db.Text)  # Description from metadata
    link_image = db.Column(db.String(500))  # Preview image URL
    link_provider = db.Column(db.String(50))  # Provider name (youtube, instagram, tiktok, etc.)
    
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    comments = db.relationship('Comment', backref='post', lazy='dynamic',
                              cascade='all, delete-orphan')
    liked_by = db.relationship('User', secondary=post_likes,
                              backref=db.backref('liked_posts', lazy='dynamic'),
                              lazy='dynamic')

    society = db.relationship('Society', foreign_keys=[society_id])
    target_user = db.relationship('User', foreign_keys=[target_user_id])
    
    def is_liked_by(self, user):
        """Check if user liked this post"""
        return self.liked_by.filter(post_likes.c.user_id == user.id).count() > 0
    
    def extract_hashtags(self):
        """Extract hashtags from post content"""
        import re
        return re.findall(r'#(\w+)', self.content)
    
    @property
    def engagement_rate(self):
        """Calculate engagement rate (likes + comments + shares) / views"""
        if self.views_count == 0:
            return 0.0
        total_engagement = self.likes_count + self.comments_count + self.shares_count
        return (total_engagement / self.views_count) * 100
    
    def __repr__(self):
        return f'<Post {self.id} by {self.user_id}>'


class Hashtag(db.Model):
    """
    Hashtag model for social posts
    """
    __tablename__ = 'hashtag'
    
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(100), unique=True, nullable=False, index=True)
    use_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utc_now)
    last_used_at = db.Column(db.DateTime, default=utc_now)
    
    def __repr__(self):
        return f'<Hashtag #{self.tag} ({self.use_count} uses)>'


# Association table for posts and hashtags
post_hashtags = db.Table('post_hashtags',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('hashtag_id', db.Integer, db.ForeignKey('hashtag.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=utc_now)
)


class PostAnalytics(db.Model):
    """
    Analytics tracking for individual posts
    """
    __tablename__ = 'post_analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False, index=True)
    
    # Daily metrics
    date = db.Column(db.Date, nullable=False, index=True)
    views = db.Column(db.Integer, default=0)
    unique_views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    comments = db.Column(db.Integer, default=0)
    shares = db.Column(db.Integer, default=0)
    
    # Audience insights
    viewer_roles = db.Column(db.Text)  # JSON: breakdown by user role
    viewer_locations = db.Column(db.Text)  # JSON: breakdown by location
    
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationship
    post = db.relationship('Post', backref=db.backref('analytics', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('post_id', 'date', name='uq_post_analytics_date'),
    )
    
    def __repr__(self):
        return f'<PostAnalytics post={self.post_id} date={self.date}>'


class UserSocialStats(db.Model):
    """
    Aggregated social statistics for users
    """
    __tablename__ = 'user_social_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True, index=True)
    
    # Follower stats
    followers_count = db.Column(db.Integer, default=0)
    following_count = db.Column(db.Integer, default=0)
    
    # Content stats
    posts_count = db.Column(db.Integer, default=0)
    total_likes_received = db.Column(db.Integer, default=0)
    total_comments_received = db.Column(db.Integer, default=0)
    total_shares_received = db.Column(db.Integer, default=0)
    total_views = db.Column(db.Integer, default=0)
    
    # Engagement metrics
    avg_engagement_rate = db.Column(db.Float, default=0.0)
    most_popular_post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    
    # Activity
    last_post_at = db.Column(db.DateTime)
    last_updated = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('social_stats', uselist=False))
    most_popular_post = db.relationship('Post', foreign_keys=[most_popular_post_id])
    
    def __repr__(self):
        return f'<UserSocialStats user={self.user_id}>'


class SocietyMembership(db.Model):
    """
    Link between a Society and a User (staff/athlete/coach/dirigente/appassionato).
    This powers CRM+planner scoping and "who sees what".
    """
    __tablename__ = 'society_membership'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    role_name = db.Column(db.String(50), nullable=False, default='appassionato')  # atleta, staff, coach, dirigente, appassionato
    status = db.Column(db.String(20), nullable=False, default='active')  # pending, active, rejected, revoked

    # Visibility and permission controls
    can_see_all_events = db.Column(db.Boolean, default=False)  # Can see all society events
    can_manage_planner = db.Column(db.Boolean, default=False)  # Can manage field planner
    receive_planner_notifications = db.Column(db.Boolean, default=True)  # Receive notifications for planner changes

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    society = db.relationship('Society', foreign_keys=[society_id], backref=db.backref('memberships', lazy='dynamic'))
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('society_memberships', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by])
    updater = db.relationship('User', foreign_keys=[updated_by])

    __table_args__ = (
        db.UniqueConstraint('society_id', 'user_id', name='uq_society_membership'),
    )

    def __repr__(self):
        return f'<SocietyMembership society={self.society_id} user={self.user_id} role={self.role_name} status={self.status}>'


class SocietyRolePermission(db.Model):
    """
    Society-scoped RBAC: per-society permissions granted/denied to society roles
    (atleta, coach, staff, dirigente, etc.)
    """
    __tablename__ = 'society_role_permission'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    role_name = db.Column(db.String(50), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission.id'), nullable=False, index=True)
    effect = db.Column(db.String(10), nullable=False, default='allow')  # allow / deny

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    society = db.relationship('Society', foreign_keys=[society_id])
    permission = db.relationship('Permission', foreign_keys=[permission_id])
    creator = db.relationship('User', foreign_keys=[created_by])

    __table_args__ = (
        db.UniqueConstraint('society_id', 'role_name', 'permission_id', name='uq_society_role_permission'),
    )

    def __repr__(self):
        return f'<SocietyRolePermission society={self.society_id} role={self.role_name} perm={self.permission_id} {self.effect}>'


class Comment(db.Model):
    """
    Comment model for posts
    """
    __tablename__ = 'comment'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    def __repr__(self):
        return f'<Comment {self.id} on Post {self.post_id}>'


class Event(db.Model):
    """
    Event model - allenamento, partita, torneo
    """
    __tablename__ = 'event'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_type = db.Column(db.String(50), nullable=False)  # allenamento, partita, torneo

    # Tournament/Match metadata
    tournament_name = db.Column(db.String(200))
    tournament_phase = db.Column(db.String(50))  # girone, quarti, semifinale, finale
    opponent_name = db.Column(db.String(200))
    home_away = db.Column(db.String(10))  # home, away, neutral
    score_for = db.Column(db.Integer)
    score_against = db.Column(db.Integer)
    bracket_url = db.Column(db.String(255))
    
    # Date and time
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)
    
    # Location
    location = db.Column(db.String(255))
    address = db.Column(db.String(255))
    
    # Creator (società or staff)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Status
    status = db.Column(db.String(20), default='scheduled')  # scheduled, ongoing, completed, cancelled
    
    # Field planner integration
    facility_id = db.Column(db.Integer, db.ForeignKey('facility.id'), nullable=True, index=True)
    color = db.Column(db.String(20), default='#212529')  # hex color for calendar display
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships - convocated athletes
    convocated_athletes = db.relationship('User', secondary=event_athletes,
                                         backref=db.backref('events', lazy='dynamic'),
                                         lazy='dynamic')
    facility = db.relationship('Facility', foreign_keys=[facility_id])
    
    def get_athlete_status(self, user_id):
        """Get athlete response status for this event"""
        result = db.session.execute(
            db.select(event_athletes.c.status).where(
                db.and_(
                    event_athletes.c.event_id == self.id,
                    event_athletes.c.user_id == user_id
                )
            )
        ).first()
        return result[0] if result else None
    
    def set_athlete_status(self, user_id, status):
        """Set athlete response status (accepted/rejected)"""
        db.session.execute(
            db.update(event_athletes).where(
                db.and_(
                    event_athletes.c.event_id == self.id,
                    event_athletes.c.user_id == user_id
                )
            ).values(status=status, responded_at=datetime.now(timezone.utc))
        )
        db.session.commit()
    
    def get_accepted_count(self):
        """Get count of accepted athletes"""
        result = db.session.execute(
            db.select(db.func.count()).select_from(event_athletes).where(
                db.and_(
                    event_athletes.c.event_id == self.id,
                    event_athletes.c.status == 'accepted'
                )
            )
        ).scalar()
        return result or 0
    
    def get_pending_count(self):
        """Get count of pending responses"""
        result = db.session.execute(
            db.select(db.func.count()).select_from(event_athletes).where(
                db.and_(
                    event_athletes.c.event_id == self.id,
                    event_athletes.c.status == 'pending'
                )
            )
        ).scalar()
        return result or 0
    
    def __repr__(self):
        return f'<Event {self.title}>'


class SocietyCalendarEvent(db.Model):
    """
    Director-level society calendar (separate from field planner)
    Allows multiple concurrent events across locations for a society.
    """
    __tablename__ = 'society_calendar_event'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    facility_id = db.Column(db.Integer, db.ForeignKey('facility.id'), index=True)
    
    # Link to Event if this calendar event was created from an Event
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True, index=True)

    title = db.Column(db.String(200), nullable=False)
    team = db.Column(db.String(100))  # textual team/category label
    category = db.Column(db.String(100))
    event_type = db.Column(db.String(50), nullable=False)  # match, tournament, meeting, travel, other
    competition_name = db.Column(db.String(200))

    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime)

    color = db.Column(db.String(20), default='#212529')  # hex or css color token

    location_text = db.Column(db.String(255))
    notes = db.Column(db.Text)

    share_to_social = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    society = db.relationship('Society', backref=db.backref('calendar_events', lazy='dynamic'))
    facility = db.relationship('Facility', foreign_keys=[facility_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    linked_event = db.relationship('Event', foreign_keys=[event_id], backref='calendar_event')
    staff_members = db.relationship(
        'User', secondary=society_calendar_event_staff,
        backref=db.backref('calendar_events_as_staff', lazy='dynamic'),
        lazy='dynamic'
    )
    athletes = db.relationship(
        'User', secondary=society_calendar_event_athletes,
        backref=db.backref('calendar_events_as_athlete', lazy='dynamic'),
        lazy='dynamic'
    )

    def is_visible_to(self, user):
        """Apply role-based visibility rules for the society calendar."""
        if not user or not user.is_authenticated:
            return False
        scope_id = self.society_id
        if check_permission(user, 'admin', 'access'):
            return True
        if check_permission(user, 'calendar', 'manage', scope_id):
            return True
        if not check_permission(user, 'calendar', 'view', scope_id):
            return False
        if self.created_by == user.id:
            return True
        if self.staff_members.filter_by(id=user.id).count() > 0:
            return True
        if self.athletes.filter_by(id=user.id).count() > 0:
            return True
        return False

    def __repr__(self):
        return f'<SocietyCalendarEvent {self.title} ({self.event_type})>'


class Facility(db.Model):
    """
    Society facilities/resources (palestre/campi/sale) used for occupancy planning.
    """
    __tablename__ = 'facility'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(255))
    capacity = db.Column(db.Integer)
    color = db.Column(db.String(20), default='#0d6efd')  # default color for this facility

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    society = db.relationship('Society', foreign_keys=[society_id], backref=db.backref('facilities', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<Facility {self.name} society={self.society_id}>'


class FieldPlannerEvent(db.Model):
    """
    Field Planner Events - Only for field/facility usage (training, matches)
    Enforces single occupancy per field per time slot (no overlaps allowed)
    Distinct from SocietyCalendarEvent which allows multiple concurrent events
    """
    __tablename__ = 'field_planner_event'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    facility_id = db.Column(db.Integer, db.ForeignKey('facility.id'), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    event_type = db.Column(db.String(50), nullable=False)  # training, match
    title = db.Column(db.String(200), nullable=False)
    team = db.Column(db.String(100))
    category = db.Column(db.String(100))
    
    start_datetime = db.Column(db.DateTime, nullable=False, index=True)
    end_datetime = db.Column(db.DateTime, nullable=False)

    # For recurring events (e.g., training sessions for entire season)
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_pattern = db.Column(db.String(50))  # weekly, daily
    recurrence_end_date = db.Column(db.Date)  # When recurring pattern ends
    parent_event_id = db.Column(db.Integer, db.ForeignKey('field_planner_event.id'), nullable=True)  # For recurring instances

    notes = db.Column(db.Text)
    color = db.Column(db.String(20), default='#28a745')

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    society = db.relationship('Society', backref=db.backref('field_planner_events', lazy='dynamic'))
    facility = db.relationship('Facility', backref=db.backref('field_events', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def is_visible_to(self, user):
        """Check if user can view this field planner event."""
        if not user or not user.is_authenticated:
            return False
        if check_permission(user, 'admin', 'access'):
            return True
        if check_permission(user, 'field_planner', 'view', self.society_id):
            return True
        return False

    def __repr__(self):
        return f'<FieldPlannerEvent {self.title} ({self.event_type}) facility={self.facility_id}>'


class Notification(db.Model):
    """
    Internal notification system
    """
    __tablename__ = 'notification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Notification content
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50))  # event, social, system, etc.
    
    # Link to related object
    link = db.Column(db.String(255))  # URL to relevant page
    
    # Status
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    read_at = db.Column(db.DateTime)
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def __repr__(self):
        return f'<Notification {self.id} for User {self.user_id}>'


class AuditLog(db.Model):
    """
    Audit log for admin actions and important events
    """
    __tablename__ = 'audit_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Who performed the action
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), index=True)  # Optional scope
    action = db.Column(db.String(100), nullable=False)  # Action type
    entity_type = db.Column(db.String(50))  # User, Post, Event, etc.
    entity_id = db.Column(db.Integer)  # ID of affected entity
    details = db.Column(db.Text)  # JSON or text details
    ip_address = db.Column(db.String(45))  # IPv4 or IPv6
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    # Relationship
    user = db.relationship('User', backref='audit_logs')
    society = db.relationship('Society', foreign_keys=[society_id])
    
    def __repr__(self):
        return f'<AuditLog {self.action} by User {self.user_id}>'


class SocietyHealthSnapshot(db.Model):
    """
    Retention health snapshot (weekly) for a society.
    Used to surface adoption KPIs and next-best actions.
    """
    __tablename__ = 'society_health_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    week_key = db.Column(db.String(12), nullable=False, index=True)  # e.g. "2026-W05"

    score = db.Column(db.Integer, default=0)  # 0-100
    details = db.Column(db.Text)  # JSON blob

    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    society = db.relationship('Society', foreign_keys=[society_id])

    __table_args__ = (
        db.UniqueConstraint('society_id', 'week_key', name='uq_society_health_snapshot_week'),
    )


class MaintenanceRun(db.Model):
    """
    Observability for scheduled jobs (maintenance_job.py).
    """
    __tablename__ = 'maintenance_run'

    id = db.Column(db.Integer, primary_key=True)
    run_type = db.Column(db.String(50), default='maintenance')  # maintenance, compliance, calendar, etc.
    status = db.Column(db.String(20), default='running')  # running, success, failed
    summary = db.Column(db.Text)  # JSON

    started_at = db.Column(db.DateTime, default=utc_now, index=True)
    finished_at = db.Column(db.DateTime)

    def __repr__(self):
        return f"<MaintenanceRun {self.id} {self.run_type} {self.status}>"


class UserOnboardingStep(db.Model):
    """
    Onboarding checklist completion for a user in a society scope.
    """
    __tablename__ = 'user_onboarding_step'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    step_key = db.Column(db.String(80), nullable=False, index=True)
    completed_at = db.Column(db.DateTime, default=utc_now, index=True)

    society = db.relationship('Society', foreign_keys=[society_id])
    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        db.UniqueConstraint('society_id', 'user_id', 'step_key', name='uq_user_onboarding_step'),
    )


class SocietySuggestionDismissal(db.Model):
    """
    Persisted dismissal state for next-best-action suggestions.
    """
    __tablename__ = 'society_suggestion_dismissal'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    key = db.Column(db.String(120), nullable=False, index=True)
    dismissed_at = db.Column(db.DateTime, default=utc_now, index=True)

    society = db.relationship('Society', foreign_keys=[society_id])
    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        db.UniqueConstraint('society_id', 'user_id', 'key', name='uq_society_suggestion_dismissal'),
    )


class SocietyInvite(db.Model):
    """
    Society invites a user to join as a specific role (athlete/staff/coach/dirigente).
    Acceptance activates a SocietyMembership and updates user role fields.
    """
    __tablename__ = 'society_invite'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    invited_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    invited_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    requested_role = db.Column(db.String(50), nullable=False)  # atleta, coach, staff, dirigente
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, accepted, rejected, revoked

    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    responded_at = db.Column(db.DateTime)

    society = db.relationship('Society', foreign_keys=[society_id])
    invited_user = db.relationship('User', foreign_keys=[invited_user_id])
    inviter = db.relationship('User', foreign_keys=[invited_by])

    __table_args__ = (
        db.UniqueConstraint('society_id', 'invited_user_id', 'status', name='uq_society_invite_active'),
    )

    def __repr__(self):
        return f'<SocietyInvite society={self.society_id} user={self.invited_user_id} role={self.requested_role} status={self.status}>'


class Backup(db.Model):
    """
    Backup tracking model
    """
    __tablename__ = 'backup'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    size = db.Column(db.Integer)  # Size in bytes
    backup_type = db.Column(db.String(20), default='full')  # full, database, uploads
    checksum = db.Column(db.String(64))  # SHA256
    storage_location = db.Column(db.String(50), default='local')  # local, remote
    remote_url = db.Column(db.String(500))
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now)
    notes = db.Column(db.Text)
    
    # Validation
    is_valid = db.Column(db.Boolean, default=True)
    validation_message = db.Column(db.Text)
    
    # Relationship
    creator = db.relationship('User', backref='backups_created')
    
    def __repr__(self):
        return f'<Backup {self.filename}>'


class BackupSetting(db.Model):
    """
    Settings for automated backups
    """
    __tablename__ = 'backup_setting'

    id = db.Column(db.Integer, primary_key=True)
    auto_enabled = db.Column(db.Boolean, default=False)
    frequency = db.Column(db.String(20), default='weekly')  # daily, weekly
    backup_type = db.Column(db.String(20), default='full')
    retention_days = db.Column(db.Integer, default=30)
    last_run_at = db.Column(db.DateTime)
    run_hour_utc = db.Column(db.Integer, default=2)  # 0-23 UTC
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<BackupSetting enabled={self.auto_enabled} freq={self.frequency}>'


class AdsSetting(db.Model):
    """
    Settings for paid insertions/promoted posts
    """
    __tablename__ = 'ads_setting'

    id = db.Column(db.Integer, primary_key=True)
    price_per_day = db.Column(db.Float, default=5.0)  # EUR per day
    price_per_thousand_views = db.Column(db.Float, default=2.0)  # CPM
    default_duration_days = db.Column(db.Integer, default=7)
    default_views = db.Column(db.Integer, default=500)
    min_duration_days = db.Column(db.Integer, default=1)   # minimum ad duration
    max_duration_days = db.Column(db.Integer, default=90)  # maximum ad duration
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<AdsSetting CPM={self.price_per_thousand_views}>'


class AdCampaign(db.Model):
    """
    Ad campaign (Facebook-like): groups creatives and controls delivery.
    For now: managed by super admin (global) or scoped to a society.
    """
    __tablename__ = 'ad_campaign'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    objective = db.Column(db.String(50), default='traffic')  # traffic, awareness, conversions (future)

    # Scope: if set, ads show only inside that society scope.
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))

    # Self-serve sponsor mode (advertisers)
    is_self_serve = db.Column(db.Boolean, default=False, index=True)
    advertiser_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)

    # Budgeting (CPM-based spend tracking)
    budget_cents = db.Column(db.Integer, default=0)
    spend_cents = db.Column(db.Integer, default=0)

    is_active = db.Column(db.Boolean, default=True, index=True)
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)

    # Audience targeting: all, societies, users, athletes, coaches
    target_audience = db.Column(db.String(50), default='all')

    # Payment status for self-serve: pending, completed, failed
    payment_status = db.Column(db.String(20), default='completed')

    # Basic caps (autopilot safety)
    max_impressions = db.Column(db.Integer)
    max_clicks = db.Column(db.Integer)

    # Autopilot: if true, delivery uses bandit (CTR) instead of fixed weights.
    autopilot = db.Column(db.Boolean, default=True)

    # Counters (fast stats)
    impressions_count = db.Column(db.Integer, default=0)
    clicks_count = db.Column(db.Integer, default=0)

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    society = db.relationship('Society', foreign_keys=[society_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    advertiser = db.relationship('User', foreign_keys=[advertiser_user_id])

    def __repr__(self):
        return f'<AdCampaign {self.id} {self.name} active={self.is_active}>'


class AdCreative(db.Model):
    """Ad creative: what gets displayed and clicked."""
    __tablename__ = 'ad_creative'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('ad_campaign.id'), nullable=False, index=True)

    placement = db.Column(db.String(50), nullable=False, index=True)  # e.g. feed_inline, sidebar_card
    headline = db.Column(db.String(120))
    body = db.Column(db.String(500))
    image_url = db.Column(db.String(500))
    link_url = db.Column(db.String(800), nullable=False)
    cta_label = db.Column(db.String(50), default='Scopri di più')

    is_active = db.Column(db.Boolean, default=True, index=True)
    weight = db.Column(db.Integer, default=100)  # used when autopilot disabled

    impressions_count = db.Column(db.Integer, default=0)
    clicks_count = db.Column(db.Integer, default=0)
    last_served_at = db.Column(db.DateTime)

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    campaign = db.relationship('AdCampaign', foreign_keys=[campaign_id], backref=db.backref('creatives', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<AdCreative {self.id} placement={self.placement} active={self.is_active}>'


class AdEvent(db.Model):
    """Event log for impressions/clicks (for analytics and debugging)."""
    __tablename__ = 'ad_event'

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False)  # impression, click
    campaign_id = db.Column(db.Integer, db.ForeignKey('ad_campaign.id'), nullable=False, index=True)
    creative_id = db.Column(db.Integer, db.ForeignKey('ad_creative.id'), nullable=False, index=True)
    placement = db.Column(db.String(50), nullable=False, index=True)

    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)

    ip = db.Column(db.String(80))
    user_agent = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    campaign = db.relationship('AdCampaign', foreign_keys=[campaign_id])
    creative = db.relationship('AdCreative', foreign_keys=[creative_id])
    society = db.relationship('Society', foreign_keys=[society_id])
    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<AdEvent {self.kind} creative={self.creative_id} at={self.created_at}>'


class SocialSetting(db.Model):
    """Global social governance controlled by super admin."""
    __tablename__ = 'social_setting'

    id = db.Column(db.Integer, primary_key=True)
    feed_enabled = db.Column(db.Boolean, default=True)
    allow_likes = db.Column(db.Boolean, default=True)
    allow_comments = db.Column(db.Boolean, default=True)
    allow_shares = db.Column(db.Boolean, default=True)
    allow_photos = db.Column(db.Boolean, default=True)
    allow_videos = db.Column(db.Boolean, default=True)
    boost_official = db.Column(db.Boolean, default=True)
    mute_user_posts = db.Column(db.Boolean, default=False)
    max_posts_per_day = db.Column(db.Integer, default=20)
    boosted_types = db.Column(db.Text)
    muted_types = db.Column(db.Text)

    # Feed algorithm tuning (super admin)
    priority_followed = db.Column(db.Integer, default=0)
    priority_friends = db.Column(db.Integer, default=1)
    priority_others = db.Column(db.Integer, default=2)
    weight_engagement = db.Column(db.Float, default=1.0)
    weight_recency = db.Column(db.Float, default=1.0)
    weight_promoted = db.Column(db.Float, default=20.0)
    weight_official = db.Column(db.Float, default=30.0)
    weight_tournament = db.Column(db.Float, default=20.0)
    weight_automation = db.Column(db.Float, default=10.0)

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<SocialSetting feed={self.feed_enabled}>'


class StorageSetting(db.Model):
    """Media storage governance (path, formats, quality)."""
    __tablename__ = 'storage_setting'

    id = db.Column(db.Integer, primary_key=True)
    storage_backend = db.Column(db.String(50), default='local')
    base_path = db.Column(db.String(255))
    preferred_image_format = db.Column(db.String(10), default='webp')
    preferred_video_format = db.Column(db.String(10), default='mp4')
    image_quality = db.Column(db.Integer, default=75)
    video_bitrate = db.Column(db.Integer, default=1200000)  # bps
    video_max_width = db.Column(db.Integer, default=1280)
    max_image_mb = db.Column(db.Integer, default=8)
    max_video_mb = db.Column(db.Integer, default=64)
    max_upload_mb = db.Column(db.Integer, default=16)  # overall upload limit (MAX_CONTENT_LENGTH)

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<StorageSetting backend={self.storage_backend}>'


class AppearanceSetting(db.Model):
    """Global and per-society visual customization."""
    __tablename__ = 'appearance_setting'

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(20), default='global')  # global or society
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))

    primary_color = db.Column(db.String(7), default='#0d6efd')
    secondary_color = db.Column(db.String(7), default='#6c757d')
    accent_color = db.Column(db.String(7), default='#20c997')
    font_family = db.Column(db.String(100), default='Inter, system-ui, -apple-system, sans-serif')
    logo_url = db.Column(db.String(255))
    favicon_url = db.Column(db.String(255))
    # PWA / mobile app icon (used for manifest + iOS home screen icon)
    app_icon_url = db.Column(db.String(255))
    layout_style = db.Column(db.String(50), default='standard')

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    society = db.relationship('Society', backref=db.backref('appearance_settings', lazy='dynamic'))
    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<AppearanceSetting {self.scope}>'


class PrivacySetting(db.Model):
    """
    Privacy and cookie consent configuration managed by super admin
    """
    __tablename__ = 'privacy_setting'

    id = db.Column(db.Integer, primary_key=True)
    banner_enabled = db.Column(db.Boolean, default=True)
    consent_message = db.Column(db.Text, nullable=False, default='Usiamo cookie tecnici per migliorare la tua esperienza. Leggi l\'informativa privacy per i dettagli.')
    privacy_url = db.Column(db.String(255))
    cookie_url = db.Column(db.String(255))

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<PrivacySetting {self.id}>'


class SiteCustomization(db.Model):
    """
    Global UI/content customization (super admin controlled).
    Keep it intentionally small and safe: branding + footer + optional custom CSS.
    """
    __tablename__ = 'site_customization'

    id = db.Column(db.Integer, primary_key=True)

    navbar_brand_text = db.Column(db.String(100), default='SONACIP')
    navbar_brand_icon = db.Column(db.String(50), default='bi-trophy-fill')  # Bootstrap Icons class

    footer_html = db.Column(db.Text)
    custom_css = db.Column(db.Text)

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<SiteCustomization {self.id}>'


class PageCustomization(db.Model):
    """
    Per-page editable content controlled by super admin.
    `slug` should match a stable page identifier (e.g. 'main.index', 'main.about').
    """
    __tablename__ = 'page_customization'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)

    title = db.Column(db.String(200))
    hero_title = db.Column(db.String(200))
    hero_subtitle = db.Column(db.String(500))
    body_html = db.Column(db.Text)

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<PageCustomization {self.slug}>'


class CustomizationKV(db.Model):
    """
    Generic customization key/value storage (JSON as text).
    Designed to scale "everything customizable" without schema churn.
    """
    __tablename__ = 'customization_kv'
    __table_args__ = (
        db.UniqueConstraint('scope', 'scope_key', 'key', name='uq_customization_scope_key'),
    )

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(20), nullable=False, index=True)  # site, page, user, role
    scope_key = db.Column(db.String(120), index=True)  # e.g. endpoint for page, user_id for user
    key = db.Column(db.String(120), nullable=False, index=True)
    value_json = db.Column(db.Text, nullable=False, default='{}')

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def get_value(self, default=None):
        import json
        try:
            return json.loads(self.value_json or 'null')
        except Exception:
            return default

    def set_value(self, value):
        import json
        self.value_json = json.dumps(value)

    def __repr__(self):
        return f'<CustomizationKV {self.scope}:{self.scope_key}:{self.key}>'


class SmtpSetting(db.Model):
    """SMTP settings editable by super admin."""
    __tablename__ = 'smtp_setting'

    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=False)

    host = db.Column(db.String(255))
    port = db.Column(db.Integer, default=587)
    use_tls = db.Column(db.Boolean, default=True)

    username = db.Column(db.String(255))
    password = db.Column(db.String(255))
    default_sender = db.Column(db.String(255), default='noreply@sonacip.it')

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<SmtpSetting enabled={self.enabled}>'


class EnterpriseSSOSetting(db.Model):
    """
    Enterprise SSO (OIDC) settings controlled by super admin.
    When enabled and configured, users can login via /auth/sso/login.
    """
    __tablename__ = 'enterprise_sso_setting'

    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=False)

    issuer_url = db.Column(db.String(500))
    client_id = db.Column(db.String(255))
    client_secret = db.Column(db.String(255))
    scopes = db.Column(db.String(255), default='openid email profile')

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])


class WhatsappSetting(db.Model):
    """
    WhatsApp integration settings (super admin).
    Generic webhook-style provider to avoid hard dependency on a specific vendor.
    """
    __tablename__ = 'whatsapp_setting'

    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=False)

    provider = db.Column(db.String(50), default='webhook')  # webhook, twilio, meta, ...
    api_url = db.Column(db.String(500))  # webhook endpoint URL
    api_token = db.Column(db.String(500))  # bearer token (optional)
    from_number = db.Column(db.String(50))  # optional sender identifier

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<WhatsappSetting enabled={self.enabled} provider={self.provider}>'


class WhatsappTemplate(db.Model):
    """
    WhatsApp Business template registry (admin-managed).
    For Meta Cloud API, `provider_template_name` is the approved template name.
    """
    __tablename__ = 'whatsapp_template'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False, index=True)  # internal key (stable)
    provider_template_name = db.Column(db.String(200), nullable=False)
    language_code = db.Column(db.String(20), default='it')  # e.g. it, it_IT, en_US
    category = db.Column(db.String(50), default='utility')
    body_preview = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)


class WhatsappOptIn(db.Model):
    """
    Explicit opt-in/out per society to satisfy WhatsApp policy/compliance.
    """
    __tablename__ = 'whatsapp_optin'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    phone_number = db.Column(db.String(30))

    is_opted_in = db.Column(db.Boolean, default=False)
    opted_in_at = db.Column(db.DateTime)
    opted_out_at = db.Column(db.DateTime)
    source = db.Column(db.String(50), default='user')

    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    society = db.relationship('Society', foreign_keys=[society_id])
    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        db.UniqueConstraint('society_id', 'user_id', name='uq_whatsapp_optin_scope'),
    )


class WhatsappMessageLog(db.Model):
    """
    Delivery/audit log for WhatsApp messages (for troubleshooting and compliance).
    """
    __tablename__ = 'whatsapp_message_log'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)

    to_number = db.Column(db.String(30))
    template_key = db.Column(db.String(120))
    body = db.Column(db.Text)
    status = db.Column(db.String(30), default='queued')  # queued, sent, failed
    provider = db.Column(db.String(50))
    provider_response = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    sent_at = db.Column(db.DateTime)

    society = db.relationship('Society', foreign_keys=[society_id])
    user = db.relationship('User', foreign_keys=[user_id])


class Message(db.Model):
    """
    Direct messaging between users with threading and attachment support
    """
    __tablename__ = 'message'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    
    # Threading support
    thread_id = db.Column(db.String(50), index=True)  # Groups related messages
    parent_id = db.Column(db.Integer, db.ForeignKey('message.id'))  # Reply to message
    
    # Attachment support
    has_attachment = db.Column(db.Boolean, default=False)
    attachment_count = db.Column(db.Integer, default=0)
    
    # Status
    is_read = db.Column(db.Boolean, default=False, index=True)
    is_archived = db.Column(db.Boolean, default=False)
    is_starred = db.Column(db.Boolean, default=False)
    is_deleted_by_sender = db.Column(db.Boolean, default=False)
    is_deleted_by_recipient = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    read_at = db.Column(db.DateTime)
    
    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='messages_sent')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='messages_received')
    parent = db.relationship('Message', remote_side=[id], backref='replies')
    
    def __repr__(self):
        return f'<Message {self.id} from {self.sender_id} to {self.recipient_id}>'
    
    def generate_thread_id(self):
        """Generate unique thread ID for message conversation"""
        import hashlib
        # Create consistent thread ID based on sender and recipient
        ids = sorted([self.sender_id, self.recipient_id])
        thread_str = f"{ids[0]}-{ids[1]}-{self.created_at.strftime('%Y%m%d')}"
        return hashlib.md5(thread_str.encode(), usedforsecurity=False).hexdigest()[:16]


class MessageAttachment(db.Model):
    """
    File attachments for messages
    """
    __tablename__ = 'message_attachment'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False, index=True)
    
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)  # Size in bytes
    mime_type = db.Column(db.String(100))
    
    uploaded_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationship
    message = db.relationship('Message', backref=db.backref('attachments', lazy='dynamic'))
    
    def __repr__(self):
        return f'<MessageAttachment {self.id}: {self.original_filename}>'


class MessageThread(db.Model):
    """
    Message thread/conversation tracking for improved organization
    """
    __tablename__ = 'message_thread'
    
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Participants
    user1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Thread info
    subject = db.Column(db.String(200))
    last_message_at = db.Column(db.DateTime, default=utc_now, index=True)
    message_count = db.Column(db.Integer, default=0)
    
    # Status for each participant
    user1_archived = db.Column(db.Boolean, default=False)
    user2_archived = db.Column(db.Boolean, default=False)
    user1_deleted = db.Column(db.Boolean, default=False)
    user2_deleted = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])
    
    __table_args__ = (
        db.UniqueConstraint('user1_id', 'user2_id', name='uq_thread_participants'),
    )
    
    def __repr__(self):
        return f'<MessageThread {self.thread_id}: {self.user1_id} <-> {self.user2_id}>'


class MessageGroup(db.Model):
    """
    WhatsApp-style group chats within the messaging system
    """
    __tablename__ = 'message_group'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    avatar = db.Column(db.String(255))
    
    # Creator and admin management
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Group settings
    max_members = db.Column(db.Integer, default=256)  # WhatsApp allows 256
    is_announcement_only = db.Column(db.Boolean, default=False)  # Only admins can post
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    last_message_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[creator_id], backref=db.backref('created_message_groups', lazy='dynamic'))
    
    def __repr__(self):
        return f'<MessageGroup {self.id}: {self.name}>'
    
    def member_count(self):
        """Get total number of members"""
        return MessageGroupMembership.query.filter_by(group_id=self.id).count()
    
    def is_admin(self, user_id):
        """Check if user is admin of this group"""
        membership = MessageGroupMembership.query.filter_by(
            group_id=self.id, 
            user_id=user_id
        ).first()
        return membership and membership.is_admin


class MessageGroupMembership(db.Model):
    """
    Membership in message group chats
    """
    __tablename__ = 'message_group_membership'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('message_group.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Role in group
    is_admin = db.Column(db.Boolean, default=False)
    
    # Notification settings
    is_muted = db.Column(db.Boolean, default=False)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)  # False if user left the group
    
    # Timestamps
    joined_at = db.Column(db.DateTime, default=utc_now)
    left_at = db.Column(db.DateTime)
    
    # Relationships
    group = db.relationship('MessageGroup', backref=db.backref('memberships', lazy='dynamic', cascade='all, delete-orphan'))
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('message_group_memberships', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('group_id', 'user_id', name='uq_message_group_membership'),
    )
    
    def __repr__(self):
        return f'<MessageGroupMembership group={self.group_id} user={self.user_id} admin={self.is_admin}>'


class MessageGroupMessage(db.Model):
    """
    Messages within group chats
    """
    __tablename__ = 'message_group_message'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('message_group.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Message content
    body = db.Column(db.Text, nullable=False)
    
    # Attachments
    has_attachment = db.Column(db.Boolean, default=False)
    attachment_path = db.Column(db.String(500))
    
    # System messages (e.g., "User joined", "User left")
    is_system_message = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    edited_at = db.Column(db.DateTime)
    
    # Relationships
    group = db.relationship('MessageGroup', backref=db.backref('group_messages', lazy='dynamic'))
    sender = db.relationship('User', foreign_keys=[sender_id])
    
    def __repr__(self):
        return f'<MessageGroupMessage {self.id} group={self.group_id} sender={self.sender_id}>'


class MedicalCertificate(db.Model):
    """
    Medical certificate for an athlete (society-managed), used for automated expiry reminders.
    """
    __tablename__ = 'medical_certificate'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    issued_on = db.Column(db.Date)
    expires_on = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), default='valid')  # valid, expired, revoked
    notes = db.Column(db.Text)

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    society = db.relationship('Society', foreign_keys=[society_id])
    user = db.relationship('User', foreign_keys=[user_id])
    creator = db.relationship('User', foreign_keys=[created_by])

    __table_args__ = (
        db.UniqueConstraint('society_id', 'user_id', 'expires_on', name='uq_medical_certificate_society_user_expires'),
    )

    def __repr__(self):
        return f'<MedicalCertificate user={self.user_id} expires={self.expires_on}>'


class SocietyFee(db.Model):
    """
    Society membership fee/payment due for a member (internal billing), used for automated reminders.
    """
    __tablename__ = 'society_fee'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    description = db.Column(db.String(255))
    amount_cents = db.Column(db.Integer, nullable=False, default=0)
    currency = db.Column(db.String(3), default='EUR')
    due_on = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), default='pending')  # pending, paid, cancelled
    paid_at = db.Column(db.DateTime)

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    society = db.relationship('Society', foreign_keys=[society_id])
    user = db.relationship('User', foreign_keys=[user_id])
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<SocietyFee user={self.user_id} due={self.due_on} status={self.status}>'


class MedicalCertificateReminderSent(db.Model):
    """Idempotency for certificate expiry reminders."""
    __tablename__ = 'medical_certificate_reminder_sent'

    id = db.Column(db.Integer, primary_key=True)
    certificate_id = db.Column(db.Integer, db.ForeignKey('medical_certificate.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    kind = db.Column(db.String(50), nullable=False)  # e.g. '14d', '7d', '1d'
    sent_at = db.Column(db.DateTime, default=utc_now, index=True)

    __table_args__ = (
        db.UniqueConstraint('certificate_id', 'user_id', 'kind', name='uq_medical_certificate_reminder_sent'),
    )


class SocietyFeeReminderSent(db.Model):
    """Idempotency for fee due reminders."""
    __tablename__ = 'society_fee_reminder_sent'

    id = db.Column(db.Integer, primary_key=True)
    fee_id = db.Column(db.Integer, db.ForeignKey('society_fee.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    kind = db.Column(db.String(50), nullable=False)  # e.g. '7d', '1d'
    sent_at = db.Column(db.DateTime, default=utc_now, index=True)

    __table_args__ = (
        db.UniqueConstraint('fee_id', 'user_id', 'kind', name='uq_society_fee_reminder_sent'),
    )


class CRMPipeline(db.Model):
    """
    CRM pipeline configuration (per-society).
    Minimal version: one active pipeline per society.
    """
    __tablename__ = 'crm_pipeline'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True, unique=True)
    name = db.Column(db.String(120), nullable=False, default='Pipeline')

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    society = db.relationship('Society', foreign_keys=[society_id], backref=db.backref('crm_pipeline', uselist=False))
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<CRMPipeline society={self.society_id} name={self.name}>'


class CRMPipelineStage(db.Model):
    """
    CRM pipeline stage configuration.
    Stored separately so Opportunity.stage can stay a stable key (string).
    """
    __tablename__ = 'crm_pipeline_stage'

    id = db.Column(db.Integer, primary_key=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('crm_pipeline.id'), nullable=False, index=True)

    key = db.Column(db.String(50), nullable=False)  # stable key stored on Opportunity.stage
    label = db.Column(db.String(120), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0, index=True)
    color = db.Column(db.String(20))  # e.g. '#0d6efd' or bootstrap token

    is_active = db.Column(db.Boolean, default=True)
    is_won = db.Column(db.Boolean, default=False)
    is_lost = db.Column(db.Boolean, default=False)

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    pipeline = db.relationship('CRMPipeline', foreign_keys=[pipeline_id], backref=db.backref('stages', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by])

    __table_args__ = (
        db.UniqueConstraint('pipeline_id', 'key', name='uq_crm_pipeline_stage_key'),
    )

    def __repr__(self):
        return f'<CRMPipelineStage {self.key} ({self.label}) pipeline={self.pipeline_id}>'


class Contact(db.Model):
    """
    CRM Contact model
    Lead, prospect, sponsor, partner contacts with scoring
    """
    __tablename__ = 'contact'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(20))
    company = db.Column(db.String(200))
    position = db.Column(db.String(100))
    
    # Contact details
    contact_type = db.Column(db.String(50))  # prospect, athlete, sponsor, partner, parent, other
    status = db.Column(db.String(50), default='new')  # new, contacted, interested, converted, lost
    source = db.Column(db.String(50))  # website, social, referral, event, advertising, other
    
    # Lead scoring
    score = db.Column(db.Integer, default=0)  # 0-100 lead score
    score_updated_at = db.Column(db.DateTime)
    engagement_level = db.Column(db.String(20), default='cold')  # cold, warm, hot
    
    # Segmentation tags (JSON array)
    tags = db.Column(db.Text)  # JSON: ["vip", "sponsor", "parent"]
    
    # Address
    address = db.Column(db.String(255))
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(10))
    country = db.Column(db.String(100))
    
    # Notes
    notes = db.Column(db.Text)
    
    # Last interaction
    last_contacted_at = db.Column(db.DateTime)
    last_contacted_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Ownership
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))  # Assigned sales rep
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    society = db.relationship('Society', foreign_keys=[society_id], backref='crm_contacts')
    creator = db.relationship('User', foreign_keys=[created_by])
    assigned_user = db.relationship('User', foreign_keys=[assigned_to])
    last_contact_user = db.relationship('User', foreign_keys=[last_contacted_by])
    
    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'
    
    def get_tags_list(self):
        """Get tags as a list"""
        import json
        if self.tags:
            try:
                return json.loads(self.tags)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.warning(f"Failed to parse tags JSON for contact: {e}")
                return []
        return []
    
    def add_tag(self, tag):
        """Add a tag to contact"""
        import json
        tags = self.get_tags_list()
        if tag not in tags:
            tags.append(tag)
            self.tags = json.dumps(tags)
    
    def __repr__(self):
        return f'<Contact {self.id}: {self.get_full_name()}>'


class ContactSegment(db.Model):
    """
    Contact segmentation for targeted communications
    """
    __tablename__ = 'contact_segment'
    
    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Filter criteria (JSON)
    criteria = db.Column(db.Text, nullable=False)  # JSON: filters for segmentation
    
    # Statistics
    contact_count = db.Column(db.Integer, default=0)
    last_calculated_at = db.Column(db.DateTime)
    
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    society = db.relationship('Society', backref='contact_segments')
    creator = db.relationship('User', backref='created_segments')
    
    def __repr__(self):
        return f'<ContactSegment {self.id}: {self.name}>'


class LeadScoringRule(db.Model):
    """
    Rules for automatic lead scoring
    """
    __tablename__ = 'lead_scoring_rule'
    
    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), index=True)
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Rule definition
    rule_type = db.Column(db.String(50), nullable=False)  # demographic, behavioral, engagement, firmographic
    attribute = db.Column(db.String(100), nullable=False)  # e.g., 'contact_type', 'source', 'activity_count'
    operator = db.Column(db.String(20), nullable=False)  # equals, contains, greater_than, less_than
    value = db.Column(db.String(200))
    
    # Scoring
    points = db.Column(db.Integer, nullable=False)  # Points to add/subtract
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    society = db.relationship('Society', backref='lead_scoring_rules')
    creator = db.relationship('User', backref='created_scoring_rules')
    
    def __repr__(self):
        return f'<LeadScoringRule {self.id}: {self.name} ({self.points} pts)>'


class Opportunity(db.Model):
    """
    CRM Opportunity model - ADVANCED (Salesforce-level)
    Sales opportunities, partnerships, sponsorships with forecasting
    """
    __tablename__ = 'opportunity'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Opportunity details
    opportunity_type = db.Column(db.String(50))  # athlete_recruitment, sponsorship, partnership, event, membership, other
    stage = db.Column(db.String(50), default='prospecting')  # prospecting, qualification, proposal, negotiation, closed_won, closed_lost
    value = db.Column(db.String(50))  # Estimated value
    probability = db.Column(db.String(10))  # Win probability percentage
    
    # ADVANCED: Forecasting & Pipeline
    weighted_value = db.Column(db.Float)  # value * probability for forecasting
    forecast_category = db.Column(db.String(20))  # pipeline, best_case, committed, closed
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    stage_history = db.Column(db.Text)  # JSON: track stage progression
    days_in_stage = db.Column(db.Integer, default=0)
    competitors = db.Column(db.Text)  # JSON array of competitor names
    deal_size_category = db.Column(db.String(20))  # small, medium, large, enterprise
    
    # Dates
    expected_close_date = db.Column(db.Date)
    actual_close_date = db.Column(db.Date)
    stage_changed_at = db.Column(db.DateTime)
    
    # Related contact
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'))
    
    # Ownership
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    contact = db.relationship('Contact', backref='opportunities')
    society = db.relationship('Society', foreign_keys=[society_id], backref='crm_opportunities')
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<Opportunity {self.id}: {self.title}>'


class CRMActivity(db.Model):
    """
    CRM Activity log
    Calls, emails, meetings, notes
    """
    __tablename__ = 'crm_activity'
    
    id = db.Column(db.Integer, primary_key=True)
    activity_type = db.Column(db.String(50), nullable=False)  # call, email, meeting, note, task, other
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Date and completion
    activity_date = db.Column(db.Date, default=utc_now)
    completed = db.Column(db.Boolean, default=False)
    
    # Related records
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'))
    opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunity.id'))
    
    # Creator
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    contact = db.relationship('Contact', backref='activities')
    opportunity = db.relationship('Opportunity', backref='activities')
    creator = db.relationship('User', backref='crm_activities')
    
    def __repr__(self):
        return f'<CRMActivity {self.id}: {self.activity_type}>'


# ================================================================================
# SAAS MODELS - Roles, Permissions, Plans, Subscriptions, Payments
# ================================================================================

class Role(db.Model):
    """
    Role model for RBAC (Role-Based Access Control)
    Provides more granular control than simple string roles
    """
    __tablename__ = 'role'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Role hierarchy level (higher = more permissions)
    level = db.Column(db.Integer, default=0)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_system = db.Column(db.Boolean, default=False)  # System roles cannot be deleted
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<Role {self.name}>'


# Association table for roles and permissions
role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=utc_now)
)


class Permission(db.Model):
    """
    Permission model for fine-grained access control
    """
    __tablename__ = 'permission'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    resource = db.Column(db.String(50), nullable=False)  # users, posts, events, crm, etc.
    action = db.Column(db.String(50), nullable=False)  # create, read, update, delete, manage
    description = db.Column(db.Text)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    roles = db.relationship('Role', secondary=role_permissions,
                           backref=db.backref('permissions', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Permission {self.resource}:{self.action}>'


class UserPermissionOverride(db.Model):
    """
    Per-user permission overrides (allow/deny) applied after role permissions.
    """
    __tablename__ = 'user_permission_override'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission.id'), nullable=False)
    effect = db.Column(db.String(10), default='allow')  # allow or deny
    created_at = db.Column(db.DateTime, default=utc_now)

    permission = db.relationship('Permission', backref=db.backref('user_overrides', lazy='dynamic'))

    def __repr__(self):
        return f'<UserPermissionOverride user={self.user_id} perm={self.permission_id} {self.effect}>'


class Plan(db.Model):
    """
    Subscription plan model for SaaS monetization
    """
    __tablename__ = 'plan'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    
    # Pricing
    price_monthly = db.Column(db.Float, default=0)
    price_yearly = db.Column(db.Float, default=0)
    currency = db.Column(db.String(3), default='EUR')

    # Stripe mapping (optional)
    stripe_product_id = db.Column(db.String(120))
    stripe_price_monthly_id = db.Column(db.String(120))
    stripe_price_yearly_id = db.Column(db.String(120))
    
    # Features and limits
    max_users = db.Column(db.Integer)  # null = unlimited
    max_athletes = db.Column(db.Integer)
    max_events = db.Column(db.Integer)
    max_storage_mb = db.Column(db.Integer)
    
    # Feature flags
    has_crm = db.Column(db.Boolean, default=False)
    has_advanced_stats = db.Column(db.Boolean, default=False)
    has_api_access = db.Column(db.Boolean, default=False)
    has_white_label = db.Column(db.Boolean, default=False)
    has_priority_support = db.Column(db.Boolean, default=False)
    
    # Display and ordering
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    display_order = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<Plan {self.name}>'


class Subscription(db.Model):
    """
    Subscription model linking users to plans
    """
    __tablename__ = 'subscription'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    
    # Subscription details
    status = db.Column(db.String(20), default='active')  # active, cancelled, expired, trial, suspended
    billing_cycle = db.Column(db.String(20), default='monthly')  # monthly, yearly
    
    # Dates
    start_date = db.Column(db.DateTime, default=utc_now)
    end_date = db.Column(db.DateTime)
    trial_end_date = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    
    # Billing
    next_billing_date = db.Column(db.DateTime)
    amount = db.Column(db.Float)

    # Stripe billing
    stripe_customer_id = db.Column(db.String(120), index=True)
    stripe_subscription_id = db.Column(db.String(120), index=True)
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    current_period_end = db.Column(db.DateTime)
    
    # Auto-renewal
    auto_renew = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('subscriptions', lazy='dynamic'))
    society = db.relationship('Society', backref=db.backref('subscriptions', lazy='dynamic'))
    plan = db.relationship('Plan', backref='subscriptions')
    
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status == 'active' and (not self.end_date or self.end_date > datetime.now(timezone.utc))
    
    def is_trial(self):
        """Check if subscription is in trial period"""
        return self.status == 'trial' and (not self.trial_end_date or self.trial_end_date > datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Subscription {self.id}: User {self.user_id} - Plan {self.plan_id}>'


class Payment(db.Model):
    """
    Payment transaction model
    """
    __tablename__ = 'payment'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'))
    
    # Payment details
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='EUR')
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, refunded
    payment_method = db.Column(db.String(50))  # card, paypal, bank_transfer, etc.
    
    # Transaction references
    transaction_id = db.Column(db.String(255), unique=True)
    gateway = db.Column(db.String(50))  # stripe, paypal, etc.
    gateway_response = db.Column(db.Text)  # JSON response from payment gateway
    
    # Dates
    payment_date = db.Column(db.DateTime)
    
    # Description and metadata
    description = db.Column(db.String(255))
    payment_metadata = db.Column(db.Text)  # JSON metadata (renamed from 'metadata' to avoid SQLAlchemy reserved word)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = db.relationship('User', backref='payments')
    society = db.relationship('Society', backref='payments')
    subscription = db.relationship('Subscription', backref='payments')
    
    def __repr__(self):
        return f'<Payment {self.id}: {self.amount} {self.currency} - {self.status}>'


class PlatformFeeSetting(db.Model):
    """
    Platform take-rate settings (super admin).
    Used to compute platform fee on society transactions (fees/tickets/etc.).
    """
    __tablename__ = 'platform_fee_setting'

    id = db.Column(db.Integer, primary_key=True)
    take_rate_percent = db.Column(db.Integer, default=5)  # e.g. 5 => 5%
    min_fee_cents = db.Column(db.Integer, default=0)
    currency = db.Column(db.String(3), default='EUR')

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])


class PlatformTransaction(db.Model):
    """
    Ledger for platform revenue share on transactions.
    """
    __tablename__ = 'platform_transaction'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), index=True)

    entity_type = db.Column(db.String(50), nullable=False)  # e.g. "SocietyFee"
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    gross_amount = db.Column(db.Float, default=0)
    platform_fee_amount = db.Column(db.Float, default=0)
    net_amount = db.Column(db.Float, default=0)
    currency = db.Column(db.String(3), default='EUR')
    status = db.Column(db.String(20), default='collected')  # collected, refunded

    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    society = db.relationship('Society', foreign_keys=[society_id])
    user = db.relationship('User', foreign_keys=[user_id])
    payment = db.relationship('Payment', foreign_keys=[payment_id])


class Coupon(db.Model):
    """
    Coupon codes for monetization (super-admin managed).
    Can apply to subscriptions and unlock paid features.
    """
    __tablename__ = 'coupon'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255))

    discount_type = db.Column(db.String(20), default='percent')  # percent, fixed
    discount_value = db.Column(db.Integer, default=0)  # percent points (0-100) or cents for fixed
    currency = db.Column(db.String(3), default='EUR')

    is_active = db.Column(db.Boolean, default=True)
    max_redemptions = db.Column(db.Integer)  # null = unlimited
    redeemed_count = db.Column(db.Integer, default=0)

    valid_from = db.Column(db.DateTime)
    valid_until = db.Column(db.DateTime)

    # Optional restriction to a plan
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'))

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    plan = db.relationship('Plan', foreign_keys=[plan_id])
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<Coupon {self.code} active={self.is_active}>'


class CouponRedemption(db.Model):
    """Coupon redemption audit."""
    __tablename__ = 'coupon_redemption'

    id = db.Column(db.Integer, primary_key=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupon.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'))
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'))

    redeemed_at = db.Column(db.DateTime, default=utc_now, index=True)

    coupon = db.relationship('Coupon', foreign_keys=[coupon_id])
    user = db.relationship('User', foreign_keys=[user_id])
    society = db.relationship('Society', foreign_keys=[society_id])
    subscription = db.relationship('Subscription', foreign_keys=[subscription_id])
    payment = db.relationship('Payment', foreign_keys=[payment_id])



class AddOn(db.Model):
    """
    Optional add-ons that can unlock product features (feature_key).
    Purchased add-ons are materialized as AddOnEntitlement rows.
    """
    __tablename__ = 'addon'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)

    feature_key = db.Column(db.String(80), nullable=False, index=True)  # e.g. "crm", "whatsapp_pro"

    # Pricing (one-time today; can evolve to recurring)
    price_one_time = db.Column(db.Float, default=0)
    currency = db.Column(db.String(3), default='EUR')

    # Optional Stripe mapping for one-time checkout (mode=payment)
    stripe_price_one_time_id = db.Column(db.String(120))

    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    def __repr__(self):
        return f"<AddOn {self.slug} feature={self.feature_key}>"


class AddOnEntitlement(db.Model):
    """
    The effective access grant derived from an add-on purchase.
    Entitlements can be scoped to a society (typical) or to an individual user.
    """
    __tablename__ = 'addon_entitlement'

    id = db.Column(db.Integer, primary_key=True)
    addon_id = db.Column(db.Integer, db.ForeignKey('addon.id'), nullable=False, index=True)
    feature_key = db.Column(db.String(80), nullable=False, index=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), index=True)

    status = db.Column(db.String(20), default='active')  # active, revoked, expired
    start_date = db.Column(db.DateTime, default=utc_now, index=True)
    end_date = db.Column(db.DateTime)

    source = db.Column(db.String(50), default='manual')  # manual, stripe, local
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    addon = db.relationship('AddOn', foreign_keys=[addon_id])
    user = db.relationship('User', foreign_keys=[user_id])
    society = db.relationship('Society', foreign_keys=[society_id])
    payment = db.relationship('Payment', foreign_keys=[payment_id])

    def __repr__(self):
        return f"<AddOnEntitlement addon={self.addon_id} scope_society={self.society_id} scope_user={self.user_id} status={self.status}>"


class Society(db.Model):
    """
    Society (Sports Club) extended model
    Separates society data from User model for better organization
    """
    __tablename__ = 'society'
    
    id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    
    # Legal information
    legal_name = db.Column(db.String(200), nullable=False)
    company_type = db.Column(db.String(50))  # ASD, SSD, SRL, etc.
    vat_number = db.Column(db.String(50), unique=True)
    fiscal_code = db.Column(db.String(50), unique=True)
    registration_number = db.Column(db.String(100))
    
    # Contact information
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    pec = db.Column(db.String(120))  # Certified email for Italian companies
    website = db.Column(db.String(255))
    
    # Address
    address = db.Column(db.String(255))
    city = db.Column(db.String(100))
    province = db.Column(db.String(2))
    postal_code = db.Column(db.String(10))
    country = db.Column(db.String(2), default='IT')
    
    # Sports information
    sport_categories = db.Column(db.Text)  # JSON array of sports
    foundation_year = db.Column(db.Integer)
    
    # Settings
    logo = db.Column(db.String(255))
    brand_color = db.Column(db.String(7))  # Hex color
    members_year_end_policy = db.Column(db.String(20), nullable=False, default='keep')  # 'keep' or 'remove'
    
    # Stats and metadata
    total_athletes = db.Column(db.Integer, default=0)
    total_staff = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[id], backref=db.backref('society_profile', uselist=False))
    
    def __repr__(self):
        return f'<Society {self.legal_name}>'




class Template(db.Model):
    """
    Templates for tasks, events, messages, etc.
    """
    __tablename__ = 'template'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Template details
    template_type = db.Column(db.String(50), nullable=False)  # task, event, email, workflow
    content = db.Column(db.Text, nullable=False)  # JSON template data
    
    # Ownership
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))
    
    # Sharing
    is_public = db.Column(db.Boolean, default=False)
    is_system = db.Column(db.Boolean, default=False)  # System templates
    
    # Usage stats
    usage_count = db.Column(db.Integer, default=0)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<Template {self.name}>'


class MarketplacePackage(db.Model):
    """
    Sellable package of templates/workflows (internal marketplace).
    """
    __tablename__ = 'marketplace_package'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    price_one_time = db.Column(db.Float, default=0)
    currency = db.Column(db.String(3), default='EUR')
    stripe_price_one_time_id = db.Column(db.String(120))

    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f"<MarketplacePackage {self.slug}>"


class MarketplacePackageItem(db.Model):
    __tablename__ = 'marketplace_package_item'

    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.Integer, db.ForeignKey('marketplace_package.id'), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey('template.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    package = db.relationship('MarketplacePackage', foreign_keys=[package_id], backref=db.backref('items', lazy='dynamic', cascade='all, delete-orphan'))
    template = db.relationship('Template', foreign_keys=[template_id])


class MarketplacePurchase(db.Model):
    __tablename__ = 'marketplace_purchase'

    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.Integer, db.ForeignKey('marketplace_package.id'), nullable=False, index=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), index=True)

    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    installed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    package = db.relationship('MarketplacePackage', foreign_keys=[package_id])
    user = db.relationship('User', foreign_keys=[user_id])
    society = db.relationship('Society', foreign_keys=[society_id])
    payment = db.relationship('Payment', foreign_keys=[payment_id])

    __table_args__ = (
        db.UniqueConstraint('package_id', 'society_id', 'user_id', name='uq_marketplace_purchase_scope_package'),
    )


class Task(db.Model):
    """
    Advanced Task Management (Asana/Monday.com/ClickUp level)
    """
    __tablename__ = 'task'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Assignment
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))
    
    # Status and priority
    status = db.Column(db.String(20), default='todo')  # todo, in_progress, review, blocked, done
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    
    # Planning
    due_date = db.Column(db.DateTime)
    start_date = db.Column(db.DateTime)
    estimated_hours = db.Column(db.Float)
    actual_hours = db.Column(db.Float)
    
    # Organization
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    sprint_id = db.Column(db.Integer)
    tags = db.Column(db.Text)  # JSON array
    
    # Kanban
    board_column = db.Column(db.String(50))
    position = db.Column(db.Integer, default=0)
    
    # Collaboration
    watchers = db.Column(db.Text)  # JSON array of user IDs
    attachments = db.Column(db.Text)  # JSON array
    dependencies = db.Column(db.Text)  # JSON: task IDs this depends on
    
    # Subtasks support
    parent_task_id = db.Column(db.Integer, db.ForeignKey('task.id'))
    
    # Progress
    progress_percentage = db.Column(db.Integer, default=0)
    
    # Metadata
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by], backref='tasks_created')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='tasks_assigned')
    subtasks = db.relationship('Task', backref=db.backref('parent', remote_side=[id]))
    
    def __repr__(self):
        return f'<Task {self.title}>'


# =============================================================
# Tournament System (strategic, multi-format, society-owned)
# =============================================================

class Tournament(db.Model):
    __tablename__ = 'tournament'

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    format = db.Column(db.String(50), nullable=False)  # round_robin, knockout, groups_finals
    season = db.Column(db.String(50))
    status = db.Column(db.String(20), default='draft')  # draft, scheduled, running, completed, archived
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)

    auto_select_criteria = db.Column(db.Text)  # JSON criteria for auto team selection
    linked_planner_event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
    linked_calendar_event_id = db.Column(db.Integer, db.ForeignKey('society_calendar_event.id'))

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    society = db.relationship('Society', backref=db.backref('tournaments', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by])
    matches = db.relationship('TournamentMatch', backref='tournament', lazy='dynamic', cascade='all, delete-orphan')
    standings = db.relationship('TournamentStanding', backref='tournament', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Tournament {self.name} ({self.format})>'


class TournamentTeam(db.Model):
    __tablename__ = 'tournament_team'

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100))
    external_ref = db.Column(db.String(100))
    seed = db.Column(db.Integer)

    tournament = db.relationship('Tournament', backref=db.backref('teams', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<TournamentTeam {self.name}>'


class TournamentMatch(db.Model):
    __tablename__ = 'tournament_match'

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey('tournament_team.id'), nullable=True)
    away_team_id = db.Column(db.Integer, db.ForeignKey('tournament_team.id'), nullable=True)
    winner_team_id = db.Column(db.Integer, db.ForeignKey('tournament_team.id'))

    round_label = db.Column(db.String(100))  # group A, quarterfinal, etc.
    round_number = db.Column(db.Integer, default=1, index=True)
    position = db.Column(db.Integer, default=0, index=True)  # bracket position within round (0-based)
    is_bracket = db.Column(db.Boolean, default=False, index=True)
    match_date = db.Column(db.DateTime)
    location = db.Column(db.String(255))

    home_score = db.Column(db.Integer)
    away_score = db.Column(db.Integer)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, played, cancelled

    calendar_event_id = db.Column(db.Integer, db.ForeignKey('society_calendar_event.id'))

    home_team = db.relationship('TournamentTeam', foreign_keys=[home_team_id])
    away_team = db.relationship('TournamentTeam', foreign_keys=[away_team_id])
    winner_team = db.relationship('TournamentTeam', foreign_keys=[winner_team_id])

    def set_score(self, home, away):
        self.home_score = home
        self.away_score = away
        self.status = 'played'
        if home is not None and away is not None and home != away:
            self.winner_team_id = self.home_team_id if home > away else self.away_team_id

    def __repr__(self):
        return f'<TournamentMatch {self.home_team_id} vs {self.away_team_id}>'


class TournamentStanding(db.Model):
    __tablename__ = 'tournament_standing'

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('tournament_team.id'), nullable=False)
    played = db.Column(db.Integer, default=0)
    won = db.Column(db.Integer, default=0)
    drawn = db.Column(db.Integer, default=0)
    lost = db.Column(db.Integer, default=0)
    goals_for = db.Column(db.Integer, default=0)
    goals_against = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)

    team = db.relationship('TournamentTeam')

    def update_from_match(self, match: 'TournamentMatch'):
        self.played += 1
        if match.home_team_id == self.team_id:
            gf, ga = match.home_score, match.away_score
        else:
            gf, ga = match.away_score, match.home_score
        self.goals_for += gf
        self.goals_against += ga
        if gf > ga:
            self.won += 1
            self.points += 3
        elif gf == ga:
            self.drawn += 1
            self.points += 1
        else:
            self.lost += 1

    def __repr__(self):
        return f'<Standing team={self.team_id} pts={self.points}>'


class Project(db.Model):
    """
    Project Management (Monday.com/Asana Boards)
    """
    __tablename__ = 'project'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Ownership
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Project details
    status = db.Column(db.String(20), default='active')  # active, on_hold, completed, archived
    project_type = db.Column(db.String(50))  # training, event, campaign, season
    color = db.Column(db.String(7), default='#3498db')  # Hex color
    icon = db.Column(db.String(50))
    
    # Timeline
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    
    # Progress
    progress_percentage = db.Column(db.Integer, default=0)
    
    # Team
    team_members = db.Column(db.Text)  # JSON array of user IDs
    
    # Views and settings
    default_view = db.Column(db.String(20), default='list')  # list, board, timeline, calendar
    is_public = db.Column(db.Boolean, default=False)
    allow_comments = db.Column(db.Boolean, default=True)
    
    # Budget tracking
    budget = db.Column(db.Float)
    spent = db.Column(db.Float, default=0)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    tasks = db.relationship('Task', backref='project', lazy='dynamic')
    
    def __repr__(self):
        return f'<Project {self.name}>'


class Analytics(db.Model):
    """
    Advanced Analytics & Metrics (Power BI/Tableau style)
    """
    __tablename__ = 'analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(50), nullable=False)  # user, post, event, crm, task
    entity_id = db.Column(db.Integer)
    metric_name = db.Column(db.String(100), nullable=False)
    metric_value = db.Column(db.Float)
    metric_data = db.Column(db.Text)  # JSON for complex metrics
    
    # Context
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Time dimensions
    recorded_at = db.Column(db.DateTime, default=utc_now, index=True)
    period = db.Column(db.String(20))  # hourly, daily, weekly, monthly, yearly
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utc_now)
    
    def __repr__(self):
        return f'<Analytics {self.metric_name}: {self.metric_value}>'


class Automation(db.Model):
    """
    Workflow Automation (Zapier/Make.com/n8n level)
    """
    __tablename__ = 'automation'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Ownership
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Trigger configuration
    trigger_type = db.Column(db.String(50), nullable=False)  # contact_created, opportunity_won, task_completed, etc.
    trigger_conditions = db.Column(db.Text)  # JSON: when to fire
    
    # Actions to perform
    actions = db.Column(db.Text, nullable=False)  # JSON array: email, create_task, update_field, webhook, etc.
    
    # Control
    is_active = db.Column(db.Boolean, default=True)
    
    # Execution stats
    execution_count = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    failure_count = db.Column(db.Integer, default=0)
    last_executed_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    
    # Limits
    max_executions = db.Column(db.Integer)  # Rate limiting
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<Automation {self.name}>'


class AutomationRule(db.Model):
    """Declarative automation rules triggered by platform events."""
    __tablename__ = 'automation_rule'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)  # tournament.created, match.scored, event.upcoming, social.posted
    condition = db.Column(db.Text)  # JSON expression / simple string filter
    actions = db.Column(db.Text, nullable=False)  # JSON array of actions: notify, create_social_post, schedule_reminder
    is_active = db.Column(db.Boolean, default=True)
    max_retries = db.Column(db.Integer, default=3)
    retry_delay = db.Column(db.Integer, default=60)  # seconds
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    creator = db.relationship('User', foreign_keys=[created_by])

    def validate_actions(self):
        """Validate actions JSON schema."""
        import json
        try:
            actions = json.loads(self.actions) if self.actions else []
            if not isinstance(actions, list):
                actions = [actions]
            for action in actions:
                if not isinstance(action, dict) or 'type' not in action:
                    return False, 'Each action must have a type'
                atype = action['type']
                if atype not in ['notify', 'email', 'social_post', 'webhook', 'task_create']:
                    return False, f'Invalid action type: {atype}'
                if atype in ['notify', 'email'] and 'user_id' not in action:
                    return False, f'{atype} action requires user_id'
            return True, None
        except Exception as e:
            return False, f'Invalid JSON: {str(e)}'

    def __repr__(self):
        return f'<AutomationRule {self.event_type}>'


class AutomationRun(db.Model):
    """Audit log of automation executions to keep flows safe and traceable."""
    __tablename__ = 'automation_run'

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('automation_rule.id'), nullable=False)
    status = db.Column(db.String(20), default='success')  # success, skipped, failed, retrying
    payload = db.Column(db.Text)
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    next_retry_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)

    rule = db.relationship('AutomationRule', backref='runs')

    def __repr__(self):
        return f'<AutomationRun rule={self.rule_id} status={self.status}>'


class Team(db.Model):
    """
    Team Collaboration (Slack/Teams style groups)
    """
    __tablename__ = 'team'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Ownership
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Members with roles
    members = db.Column(db.Text)  # JSON: [{user_id, role, joined_at}]
    
    # Settings
    is_public = db.Column(db.Boolean, default=False)
    avatar = db.Column(db.String(255))
    color = db.Column(db.String(7), default='#9b59b6')
    
    # Stats
    member_count = db.Column(db.Integer, default=0)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<Team {self.name}>'


class DashboardTemplate(db.Model):
    """
    Default dashboard template for a role (super admin controlled).
    Used to provision user dashboards and to reset them deterministically.
    """
    __tablename__ = 'dashboard_template'

    id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), index=True)  # nullable = global fallback

    name = db.Column(db.String(200), nullable=False, default='Default')
    layout = db.Column(db.String(20), default='grid')
    widgets = db.Column(db.Text, nullable=False)  # JSON array

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<DashboardTemplate role={self.role_name or "default"}>'


class Dashboard(db.Model):
    """
    Custom Dashboards (Databox/Klipfolio style)
    """
    __tablename__ = 'dashboard'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Ownership
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))
    
    # Layout
    widgets = db.Column(db.Text, nullable=False)  # JSON: widget configs
    layout = db.Column(db.String(20), default='grid')  # grid, flex
    
    # Sharing
    is_public = db.Column(db.Boolean, default=False)
    is_default = db.Column(db.Boolean, default=False)
    
    # Refresh
    auto_refresh = db.Column(db.Boolean, default=False)
    refresh_interval = db.Column(db.Integer, default=300)  # seconds
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def get_widgets(self):
        import json
        try:
            data = json.loads(self.widgets or '[]')
            return data if isinstance(data, list) else [data]
        except Exception:
            return []

    def set_widgets(self, widgets):
        import json
        self.widgets = json.dumps(widgets or [])
    
    def __repr__(self):
        return f'<Dashboard {self.name}>'


class Goal(db.Model):
    """
    OKR and Goals Tracking (Lattice/Betterworks style)
    """
    __tablename__ = 'goal'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Goal type
    goal_type = db.Column(db.String(50))  # okr, smart, kpi, milestone
    
    # Ownership
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    
    # Objective and Key Results
    objective = db.Column(db.Text)
    key_results = db.Column(db.Text)  # JSON array
    
    # Progress
    current_value = db.Column(db.Float)
    target_value = db.Column(db.Float)
    progress_percentage = db.Column(db.Integer, default=0)
    
    # Timeline
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    
    # Status
    status = db.Column(db.String(20), default='in_progress')  # in_progress, achieved, at_risk, missed
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<Goal {self.title}>'


class Career(db.Model):
    """
    LinkedIn-style career/experience entries for user profiles
    """
    __tablename__ = 'career'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    company_logo = db.Column(db.String(255))
    location = db.Column(db.String(200))
    employment_type = db.Column(db.String(50))  # full_time, part_time, contract, internship
    
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    is_current = db.Column(db.Boolean, default=False)
    
    description = db.Column(db.Text)
    skills = db.Column(db.Text)  # comma-separated skills
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    user = db.relationship('User', backref=db.backref('careers', lazy='dynamic', order_by='Career.start_date.desc()'))
    
    def __repr__(self):
        return f'<Career {self.title} at {self.company}>'


class Education(db.Model):
    """
    LinkedIn-style education entries for user profiles
    """
    __tablename__ = 'education'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    school = db.Column(db.String(200), nullable=False)
    school_logo = db.Column(db.String(255))
    degree = db.Column(db.String(200))
    field_of_study = db.Column(db.String(200))
    
    start_year = db.Column(db.Integer)
    end_year = db.Column(db.Integer)
    
    grade = db.Column(db.String(50))
    activities = db.Column(db.Text)
    description = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    user = db.relationship('User', backref=db.backref('educations', lazy='dynamic', order_by='Education.start_year.desc()'))
    
    def __repr__(self):
        return f'<Education {self.degree} at {self.school}>'


class Skill(db.Model):
    """
    LinkedIn-style skills with endorsements
    """
    __tablename__ = 'skill'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))  # sport, coaching, management, technical
    endorsement_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=utc_now)
    
    user = db.relationship('User', backref=db.backref('skills', lazy='dynamic', order_by='Skill.endorsement_count.desc()'))
    
    def __repr__(self):
        return f'<Skill {self.name}>'


class SkillEndorsement(db.Model):
    """
    Endorsements for skills
    """
    __tablename__ = 'skill_endorsement'
    
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'), nullable=False)
    endorsed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    skill = db.relationship('Skill', backref=db.backref('endorsements', lazy='dynamic'))
    endorsed_by = db.relationship('User', backref=db.backref('given_endorsements', lazy='dynamic'))


class Connection(db.Model):
    """
    LinkedIn-style connections (mutual friendships)
    """
    __tablename__ = 'connection'
    
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    addressee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected, blocked
    message = db.Column(db.Text)  # optional connection request message
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    requester = db.relationship('User', foreign_keys=[requester_id], backref=db.backref('sent_connections', lazy='dynamic'))
    addressee = db.relationship('User', foreign_keys=[addressee_id], backref=db.backref('received_connections', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Connection {self.requester_id} -> {self.addressee_id} ({self.status})>'


class ProfileSection(db.Model):
    """
    Admin-configurable profile sections
    """
    __tablename__ = 'profile_section'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_en = db.Column(db.String(100))
    icon = db.Column(db.String(50))
    is_enabled = db.Column(db.Boolean, default=True)
    is_required = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    
    section_type = db.Column(db.String(50))  # career, education, skills, about, contact
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)


class ProfileVerification(db.Model):
    """
    Profile verification requests and status
    """
    __tablename__ = 'profile_verification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True, index=True)
    
    # Verification type
    verification_type = db.Column(db.String(50), nullable=False)  # identity, athlete, society, professional
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, under_review
    
    # Documents
    document_1_path = db.Column(db.String(500))  # ID card, passport
    document_2_path = db.Column(db.String(500))  # Additional proof
    document_3_path = db.Column(db.String(500))  # Supporting document
    
    # Verification details
    submitted_at = db.Column(db.DateTime, default=utc_now)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Notes
    applicant_notes = db.Column(db.Text)  # Why they want verification
    reviewer_notes = db.Column(db.Text)  # Admin notes on verification
    rejection_reason = db.Column(db.Text)
    
    # Badge information (if verified)
    badge_type = db.Column(db.String(50))  # blue_check, gold_star, society_verified, athlete_verified
    badge_expires_at = db.Column(db.DateTime)  # Some verifications may expire
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('verification', uselist=False))
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f'<ProfileVerification user={self.user_id} status={self.status}>'


class ProfileAnalytics(db.Model):
    """
    Profile view and engagement analytics
    """
    __tablename__ = 'profile_analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Daily metrics
    date = db.Column(db.Date, nullable=False, index=True)
    profile_views = db.Column(db.Integer, default=0)
    unique_viewers = db.Column(db.Integer, default=0)
    
    # Engagement
    new_followers = db.Column(db.Integer, default=0)
    lost_followers = db.Column(db.Integer, default=0)
    messages_received = db.Column(db.Integer, default=0)
    
    # Source tracking
    view_sources = db.Column(db.Text)  # JSON: where views came from
    
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('profile_analytics', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', name='uq_profile_analytics_date'),
    )
    
    def __repr__(self):
        return f'<ProfileAnalytics user={self.user_id} date={self.date}>'


class CustomProfileField(db.Model):
    """
    Custom profile fields that users can add
    """
    __tablename__ = 'custom_profile_field'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Field definition
    field_name = db.Column(db.String(100), nullable=False)
    field_type = db.Column(db.String(20), default='text')  # text, url, date, number
    field_value = db.Column(db.Text)
    
    # Display
    is_visible = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    
    # Category
    category = db.Column(db.String(50))  # contact, social, professional, personal
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('custom_fields', lazy='dynamic'))
    
    def __repr__(self):
        return f'<CustomProfileField {self.field_name} for user={self.user_id}>'


class ModerationRule(db.Model):
    """
    Automatic moderation rules for social content
    """
    __tablename__ = 'moderation_rule'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    rule_type = db.Column(db.String(50), nullable=False)  # keyword_filter, spam_detection, etc.
    is_active = db.Column(db.Boolean, default=True)
    
    # Rule configuration
    keywords = db.Column(db.Text)  # comma-separated keywords to filter
    action = db.Column(db.String(50), default='flag')  # flag, hide, delete
    severity = db.Column(db.String(20), default='medium')  # low, medium, high
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<ModerationRule {self.name}>'


class MarketplaceListing(db.Model):
    __tablename__ = 'marketplace_listing'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), index=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False, default=0)
    currency = db.Column(db.String(3), default='EUR')
    category = db.Column(db.String(80), default='altro')
    condition = db.Column(db.String(30), default='usato')
    location = db.Column(db.String(200))

    image_1 = db.Column(db.String(300))
    image_2 = db.Column(db.String(300))
    image_3 = db.Column(db.String(300))
    image_4 = db.Column(db.String(300))

    status = db.Column(db.String(20), default='active', index=True)
    views_count = db.Column(db.Integer, default=0)

    expires_at = db.Column(db.DateTime, index=True)
    is_promoted = db.Column(db.Boolean, default=False, index=True)
    promotion_expires_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    seller = db.relationship('User', foreign_keys=[user_id], backref=db.backref('marketplace_listings', lazy='dynamic'))
    society = db.relationship('Society', foreign_keys=[society_id])

    CATEGORIES = [
        ('sport', 'Attrezzatura Sportiva'),
        ('abbigliamento', 'Abbigliamento'),
        ('elettronica', 'Elettronica'),
        ('veicoli', 'Veicoli'),
        ('casa', 'Casa e Giardino'),
        ('servizi', 'Servizi'),
        ('biglietti', 'Biglietti e Eventi'),
        ('collezionismo', 'Collezionismo'),
        ('altro', 'Altro'),
    ]

    CONDITIONS = [
        ('nuovo', 'Nuovo'),
        ('come_nuovo', 'Come Nuovo'),
        ('buono', 'Buono'),
        ('usato', 'Usato'),
        ('da_riparare', 'Da Riparare'),
    ]

    def __repr__(self):
        return f'<MarketplaceListing {self.title}>'


class PlatformFeature(db.Model):
    __tablename__ = 'platform_feature'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(80), default='general')
    icon = db.Column(db.String(60), default='bi-gear')
    is_premium = db.Column(db.Boolean, default=False)
    is_enabled = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return f'<PlatformFeature {self.key} premium={self.is_premium}>'


class PromotionTier(db.Model):
    __tablename__ = 'promotion_tier'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    duration_days = db.Column(db.Integer, nullable=False, default=7)
    price = db.Column(db.Float, nullable=False, default=0)
    currency = db.Column(db.String(3), default='EUR')
    icon = db.Column(db.String(60), default='bi-star')
    color = db.Column(db.String(7), default='#ff9800')
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    stripe_price_id = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return f'<PromotionTier {self.name} {self.duration_days}d €{self.price}>'


class ListingPromotion(db.Model):
    __tablename__ = 'listing_promotion'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('marketplace_listing.id'), nullable=False, index=True)
    tier_id = db.Column(db.Integer, db.ForeignKey('promotion_tier.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'))

    status = db.Column(db.String(20), default='pending', index=True)
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    amount_paid = db.Column(db.Float, default=0)
    currency = db.Column(db.String(3), default='EUR')

    created_at = db.Column(db.DateTime, default=utc_now)

    listing = db.relationship('MarketplaceListing', backref=db.backref('promotions', lazy='dynamic'))
    tier = db.relationship('PromotionTier')
    user = db.relationship('User', foreign_keys=[user_id])
    payment = db.relationship('Payment', foreign_keys=[payment_id])

    def __repr__(self):
        return f'<ListingPromotion listing={self.listing_id} status={self.status}>'


class PlatformPaymentSetting(db.Model):
    __tablename__ = 'platform_payment_setting'

    id = db.Column(db.Integer, primary_key=True)
    stripe_enabled = db.Column(db.Boolean, default=False)
    stripe_account_id = db.Column(db.String(120))

    bank_account_holder = db.Column(db.String(200))
    bank_name = db.Column(db.String(200))
    bank_iban = db.Column(db.String(60))
    bank_bic_swift = db.Column(db.String(30))
    bank_country = db.Column(db.String(60), default='Italia')

    paypal_email = db.Column(db.String(200))

    payout_method = db.Column(db.String(30), default='stripe')
    payout_frequency = db.Column(db.String(20), default='monthly')
    min_payout_amount = db.Column(db.Float, default=50.0)
    currency = db.Column(db.String(3), default='EUR')

    notes = db.Column(db.Text)

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<PlatformPaymentSetting method={self.payout_method}>'


class BroadcastMessage(db.Model):
    __tablename__ = 'broadcast_message'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    scope_type = db.Column(db.String(20), nullable=False, default='global')
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=True, index=True)

    subject = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=False)

    target_roles = db.Column(db.Text)
    send_email = db.Column(db.Boolean, default=False)

    status = db.Column(db.String(20), nullable=False, default='draft')
    total_recipients = db.Column(db.Integer, default=0)
    total_read = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=utc_now)
    sent_at = db.Column(db.DateTime)

    sender = db.relationship('User', foreign_keys=[sender_id])
    society = db.relationship('Society', foreign_keys=[society_id])
    recipients = db.relationship('BroadcastRecipient', backref='broadcast', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<BroadcastMessage {self.id} "{self.subject}" scope={self.scope_type}>'


class BroadcastRecipient(db.Model):
    __tablename__ = 'broadcast_recipient'

    id = db.Column(db.Integer, primary_key=True)
    broadcast_id = db.Column(db.Integer, db.ForeignKey('broadcast_message.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)

    delivery_status = db.Column(db.String(20), default='pending')
    email_sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime)

    user = db.relationship('User', foreign_keys=[user_id])
    message = db.relationship('Message', foreign_keys=[message_id])

    __table_args__ = (
        db.UniqueConstraint('broadcast_id', 'user_id', name='uq_broadcast_recipient'),
    )

    def __repr__(self):
        return f'<BroadcastRecipient broadcast={self.broadcast_id} user={self.user_id}>'


class EmailConfirmationSetting(db.Model):
    __tablename__ = 'email_confirmation_setting'

    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=False)
    token_expiry_hours = db.Column(db.Integer, default=48)
    max_resends = db.Column(db.Integer, default=5)
    email_subject = db.Column(db.String(255), default='Conferma il tuo indirizzo email - SONACIP')
    email_body_template = db.Column(db.Text, default='')
    auto_confirm_existing = db.Column(db.Boolean, default=True)

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<EmailConfirmationSetting enabled={self.enabled}>'


class PushSubscription(db.Model):
    """Browser push notification subscriptions"""
    __tablename__ = 'push_subscription'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh_key = db.Column(db.String(255))
    auth_key = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=utc_now)
    is_active = db.Column(db.Boolean, default=True)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('push_subscriptions', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'endpoint', name='uq_push_subscription_user_endpoint'),
    )

    def __repr__(self):
        return f'<PushSubscription {self.id} user={self.user_id}>'


class Group(db.Model):
    """Community groups within societies"""
    __tablename__ = 'group'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    society_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    avatar = db.Column(db.String(255))
    cover_image = db.Column(db.String(255))
    is_private = db.Column(db.Boolean, default=False)
    max_members = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    creator = db.relationship('User', foreign_keys=[creator_id], backref=db.backref('created_groups', lazy='dynamic'))
    members = db.relationship('GroupMembership', backref='group', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Group {self.name}>'


class GroupMembership(db.Model):
    """Group membership"""
    __tablename__ = 'group_membership'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    role = db.Column(db.String(20), default='member')
    joined_at = db.Column(db.DateTime, default=utc_now)
    is_muted = db.Column(db.Boolean, default=False)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('group_memberships', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('group_id', 'user_id', name='uq_group_membership'),
    )

    def __repr__(self):
        return f'<GroupMembership group={self.group_id} user={self.user_id} role={self.role}>'


class GroupMessage(db.Model):
    """Messages within groups"""
    __tablename__ = 'group_message'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=utc_now)

    group = db.relationship('Group', foreign_keys=[group_id], backref=db.backref('messages', lazy='dynamic'))
    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<GroupMessage {self.id} group={self.group_id} user={self.user_id}>'


class Story(db.Model):
    """Temporary stories/status"""
    __tablename__ = 'story'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    media_url = db.Column(db.String(500))
    media_type = db.Column(db.String(20), default='image')
    caption = db.Column(db.Text)
    background_color = db.Column(db.String(20), default='#1877f2')
    created_at = db.Column(db.DateTime, default=utc_now)
    expires_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc) + timedelta(hours=24))
    views_count = db.Column(db.Integer, default=0)

    author = db.relationship('User', foreign_keys=[user_id], backref=db.backref('stories', lazy='dynamic'))

    @property
    def is_expired(self):
        return datetime.now(timezone.utc) >= self.expires_at if self.expires_at else False

    @property
    def view_count(self):
        return self.views.count() if hasattr(self, 'views') else self.views_count or 0

    def __repr__(self):
        return f'<Story {self.id} by user={self.user_id}>'


class StoryView(db.Model):
    """Track who viewed stories"""
    __tablename__ = 'story_view'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False, index=True)
    viewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    viewed_at = db.Column(db.DateTime, default=utc_now)

    story = db.relationship('Story', foreign_keys=[story_id], backref=db.backref('views', lazy='dynamic'))
    viewer = db.relationship('User', foreign_keys=[viewer_id])

    __table_args__ = (
        db.UniqueConstraint('story_id', 'viewer_id', name='uq_story_view'),
    )

    def __repr__(self):
        return f'<StoryView story={self.story_id} viewer={self.viewer_id}>'


class LiveStream(db.Model):
    """Live streaming sessions - metadata only, no video storage"""
    __tablename__ = 'live_stream'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, index=True)
    started_at = db.Column(db.DateTime, default=utc_now, index=True)
    ended_at = db.Column(db.DateTime)
    viewer_count = db.Column(db.Integer, default=0)
    peak_viewers = db.Column(db.Integer, default=0)
    
    # WebRTC connection info (for signaling only)
    room_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Visibility: if True, stream is visible on user's profile page and social feed
    is_public = db.Column(db.Boolean, default=False)
    
    streamer = db.relationship('User', foreign_keys=[user_id], backref=db.backref('live_streams', lazy='dynamic'))

    @property
    def duration_seconds(self):
        # Ensure both datetimes are timezone-aware for comparison
        if self.ended_at:
            # If ended_at has no timezone, assume it's UTC
            ended = self.ended_at if self.ended_at.tzinfo else self.ended_at.replace(tzinfo=timezone.utc)
            started = self.started_at if self.started_at.tzinfo else self.started_at.replace(tzinfo=timezone.utc)
            return int((ended - started).total_seconds())
        # For active streams, calculate duration from start until now
        started = self.started_at if self.started_at.tzinfo else self.started_at.replace(tzinfo=timezone.utc)
        return int((datetime.now(timezone.utc) - started).total_seconds())

    def __repr__(self):
        return f'<LiveStream {self.id} by user={self.user_id} active={self.is_active}>'


class LiveStreamViewer(db.Model):
    """Track live stream viewers - for analytics only"""
    __tablename__ = 'live_stream_viewer'

    id = db.Column(db.Integer, primary_key=True)
    stream_id = db.Column(db.Integer, db.ForeignKey('live_stream.id'), nullable=False, index=True)
    viewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    joined_at = db.Column(db.DateTime, default=utc_now)
    left_at = db.Column(db.DateTime)
    
    stream = db.relationship('LiveStream', foreign_keys=[stream_id], backref=db.backref('viewers', lazy='dynamic'))
    viewer = db.relationship('User', foreign_keys=[viewer_id])

    __table_args__ = (
        db.Index('ix_stream_viewer_active', 'stream_id', 'viewer_id'),
    )

    def __repr__(self):
        return f'<LiveStreamViewer stream={self.stream_id} viewer={self.viewer_id}>'


class Poll(db.Model):
    """Polls/surveys"""
    __tablename__ = 'poll'

    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    society_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    is_anonymous = db.Column(db.Boolean, default=False)
    multiple_choice = db.Column(db.Boolean, default=False)
    closes_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    is_active = db.Column(db.Boolean, default=True)

    options = db.relationship('PollOption', backref='poll', lazy='dynamic', cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[creator_id], backref=db.backref('polls_created', lazy='dynamic'))

    def __repr__(self):
        return f'<Poll {self.id} "{self.title}">'


class PollOption(db.Model):
    """Poll answer options"""
    __tablename__ = 'poll_option'

    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False, index=True)
    text = db.Column(db.String(200), nullable=False)
    votes_count = db.Column(db.Integer, default=0)
    display_order = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<PollOption {self.id} poll={self.poll_id}>'


class PollVote(db.Model):
    """User votes on polls"""
    __tablename__ = 'poll_vote'

    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False, index=True)
    option_id = db.Column(db.Integer, db.ForeignKey('poll_option.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    voted_at = db.Column(db.DateTime, default=utc_now)

    poll = db.relationship('Poll', foreign_keys=[poll_id], backref=db.backref('votes', lazy='dynamic'))
    option = db.relationship('PollOption', foreign_keys=[option_id], backref=db.backref('votes', lazy='dynamic'))
    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        db.UniqueConstraint('poll_id', 'user_id', 'option_id', name='uq_poll_vote'),
    )

    def __repr__(self):
        return f'<PollVote poll={self.poll_id} option={self.option_id} user={self.user_id}>'


class AthleteStat(db.Model):
    """Athlete performance tracking"""
    __tablename__ = 'athlete_stat'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    society_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    season = db.Column(db.String(20))
    sport_type = db.Column(db.String(50))
    stat_date = db.Column(db.Date, nullable=False)
    stat_type = db.Column(db.String(50))
    metrics = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('athlete_stats', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<AthleteStat {self.id} user={self.user_id} type={self.stat_type}>'


class StatTemplate(db.Model):
    """Templates for stat types"""
    __tablename__ = 'stat_template'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sport_type = db.Column(db.String(50))
    stat_type = db.Column(db.String(50))
    fields = db.Column(db.Text)
    society_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    is_global = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now)

    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<StatTemplate {self.name} sport={self.sport_type}>'


class DocumentFolder(db.Model):
    """Folders for organizing documents"""
    __tablename__ = 'document_folder'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('document_folder.id'), nullable=True, index=True)
    society_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)

    children = db.relationship('DocumentFolder', backref=db.backref('parent', remote_side='DocumentFolder.id'), lazy='dynamic')
    documents = db.relationship('Document', backref='folder', lazy='dynamic')
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<DocumentFolder {self.name}>'


class Document(db.Model):
    """Document management"""
    __tablename__ = 'document'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(500), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(50))
    folder_id = db.Column(db.Integer, db.ForeignKey('document_folder.id'), nullable=True, index=True)
    society_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    download_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    uploader = db.relationship('User', foreign_keys=[uploaded_by], backref=db.backref('uploaded_documents', lazy='dynamic'))

    def __repr__(self):
        return f'<Document {self.title}>'


class Badge(db.Model):
    """Gamification badges"""
    __tablename__ = 'badge'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    color = db.Column(db.String(7), default='#1877f2')
    category = db.Column(db.String(50))
    requirement_type = db.Column(db.String(50))
    requirement_value = db.Column(db.Integer, default=1)
    points = db.Column(db.Integer, default=10)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    def __repr__(self):
        return f'<Badge {self.name}>'


class UserBadge(db.Model):
    """Badges earned by users"""
    __tablename__ = 'user_badge'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    badge_id = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=False, index=True)
    earned_at = db.Column(db.DateTime, default=utc_now)
    is_notified = db.Column(db.Boolean, default=False)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('badges', lazy='dynamic'))
    badge = db.relationship('Badge', foreign_keys=[badge_id], backref=db.backref('awarded_to', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'badge_id', name='uq_user_badge'),
    )

    def __repr__(self):
        return f'<UserBadge user={self.user_id} badge={self.badge_id}>'


class UserPoints(db.Model):
    """Gamification points"""
    __tablename__ = 'user_points'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True, index=True)
    total_points = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    posts_count = db.Column(db.Integer, default=0)
    events_attended = db.Column(db.Integer, default=0)
    login_streak = db.Column(db.Integer, default=0)
    last_login_date = db.Column(db.Date)
    badges_count = db.Column(db.Integer, default=0)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('points', uselist=False))

    def __repr__(self):
        return f'<UserPoints user={self.user_id} points={self.total_points} level={self.level}>'


class DashboardWidget(db.Model):
    """Available dashboard widgets"""
    __tablename__ = 'dashboard_widget'

    id = db.Column(db.Integer, primary_key=True)
    widget_key = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    category = db.Column(db.String(50))
    default_size = db.Column(db.String(20), default='medium')
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<DashboardWidget {self.widget_key}>'


class UserDashboardLayout(db.Model):
    """User's dashboard configuration"""
    __tablename__ = 'user_dashboard_layout'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    widget_key = db.Column(db.String(50), nullable=False)
    position = db.Column(db.Integer, default=0)
    size = db.Column(db.String(20), default='medium')
    is_visible = db.Column(db.Boolean, default=True)
    config = db.Column(db.Text)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('dashboard_layouts', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'widget_key', name='uq_user_dashboard_layout'),
    )

    def __repr__(self):
        return f'<UserDashboardLayout user={self.user_id} widget={self.widget_key}>'


class FeePayment(db.Model):
    """Payment records for society fees"""
    __tablename__ = 'fee_payment'

    id = db.Column(db.Integer, primary_key=True)
    fee_id = db.Column(db.Integer, db.ForeignKey('society_fee.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))
    stripe_payment_id = db.Column(db.String(255), nullable=True)
    stripe_receipt_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default='pending')
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    notes = db.Column(db.Text)

    fee = db.relationship('SocietyFee', foreign_keys=[fee_id], backref=db.backref('payments', lazy='dynamic'))
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('fee_payments', lazy='dynamic'))

    def __repr__(self):
        return f'<FeePayment {self.id} fee={self.fee_id} user={self.user_id} status={self.status}>'


class Invoice(db.Model):
    """
    Invoice model for payments and fees
    Links to payments and provides formal invoicing
    """
    __tablename__ = 'invoice'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Links to payment or fee payment
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=True)
    fee_payment_id = db.Column(db.Integer, db.ForeignKey('fee_payment.id'), nullable=True)
    
    # Billing information
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=True)
    
    # Invoice details
    amount = db.Column(db.Float, nullable=False)
    tax_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='EUR')
    
    # Billing address
    billing_name = db.Column(db.String(200))
    billing_address = db.Column(db.Text)
    billing_city = db.Column(db.String(100))
    billing_postal_code = db.Column(db.String(20))
    billing_country = db.Column(db.String(100))
    tax_id = db.Column(db.String(50))  # VAT/Tax ID
    
    # Invoice dates
    invoice_date = db.Column(db.DateTime, default=utc_now, nullable=False)
    due_date = db.Column(db.DateTime, nullable=True)
    paid_date = db.Column(db.DateTime, nullable=True)
    
    # Status and notes
    status = db.Column(db.String(20), default='draft')  # draft, sent, paid, cancelled, overdue
    description = db.Column(db.Text)
    notes = db.Column(db.Text)
    
    # PDF generation
    pdf_path = db.Column(db.String(500))  # Path to generated PDF
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = db.relationship('User', backref='invoices')
    society = db.relationship('Society', backref='invoices')
    payment = db.relationship('Payment', backref='invoice', uselist=False)
    fee_payment = db.relationship('FeePayment', backref='invoice', uselist=False)
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number}: {self.total_amount} {self.currency} - {self.status}>'
    
    def generate_invoice_number(self):
        """Generate unique invoice number"""
        from datetime import datetime
        year = datetime.now().year
        # Format: INV-YYYY-XXXXX (e.g., INV-2026-00001)
        return f'INV-{year}-{str(self.id).zfill(5)}'


class InvoiceLineItem(db.Model):
    """
    Line items for invoices (for detailed invoices with multiple items)
    """
    __tablename__ = 'invoice_line_item'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False, index=True)
    
    description = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    tax_rate = db.Column(db.Float, default=0.0)  # Tax rate percentage
    amount = db.Column(db.Float, nullable=False)  # quantity * unit_price
    
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationship
    invoice = db.relationship('Invoice', backref=db.backref('line_items', lazy='dynamic'))
    
    def __repr__(self):
        return f'<InvoiceLineItem {self.id}: {self.description} - {self.amount}>'


class InvoiceSettings(db.Model):
    """
    Super admin configurable invoice settings
    Company details, branding, electronic invoice configuration
    """
    __tablename__ = 'invoice_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Company information
    company_name = db.Column(db.String(200), nullable=True)
    company_address = db.Column(db.Text, nullable=True)
    company_city = db.Column(db.String(100), nullable=True)
    company_postal_code = db.Column(db.String(20), nullable=True)
    company_country = db.Column(db.String(100), default='Italia')
    company_vat = db.Column(db.String(50), nullable=True)  # Partita IVA
    company_tax_code = db.Column(db.String(50), nullable=True)  # Codice Fiscale
    company_phone = db.Column(db.String(50), nullable=True)
    company_email = db.Column(db.String(120), nullable=True)
    company_website = db.Column(db.String(200), nullable=True)
    
    # Invoice settings
    invoice_prefix = db.Column(db.String(20), default='INV')
    invoice_footer = db.Column(db.Text, nullable=True)
    invoice_notes = db.Column(db.Text, nullable=True)
    default_tax_rate = db.Column(db.Float, default=22.0)  # IVA 22% default in Italy
    
    # Logo and branding
    logo_path = db.Column(db.String(500), nullable=True)
    
    # Electronic invoice settings (Fatturazione Elettronica)
    enable_electronic_invoice = db.Column(db.Boolean, default=False)
    e_invoice_provider = db.Column(db.String(50), nullable=True)  # 'fatture_in_cloud', 'aruba', etc.
    e_invoice_api_key = db.Column(db.String(500), nullable=True)
    e_invoice_api_secret = db.Column(db.String(500), nullable=True)
    e_invoice_company_id = db.Column(db.String(100), nullable=True)
    sdi_code = db.Column(db.String(7), nullable=True)  # Codice Destinatario SDI
    pec_email = db.Column(db.String(120), nullable=True)  # PEC for electronic invoices
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationship
    updater = db.relationship('User', foreign_keys=[updated_by])
    
    def __repr__(self):
        return f'<InvoiceSettings {self.company_name}>'


class Expense(db.Model):
    """
    Expense tracking for societies and platform
    """
    __tablename__ = 'expense'
    
    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Expense details
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='EUR')
    category = db.Column(db.String(50), nullable=False)  # travel, equipment, facility, marketing, etc.
    description = db.Column(db.Text, nullable=False)
    
    # Vendor and receipt
    vendor_name = db.Column(db.String(200))
    receipt_path = db.Column(db.String(500))  # Path to uploaded receipt
    
    # Dates
    expense_date = db.Column(db.DateTime, nullable=False, index=True)
    
    # Approval and reimbursement
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, reimbursed
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    approved_at = db.Column(db.DateTime)
    reimbursed_at = db.Column(db.DateTime)
    
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    society = db.relationship('Society', backref='expenses')
    user = db.relationship('User', foreign_keys=[user_id], backref='submitted_expenses')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_expenses')
    
    def __repr__(self):
        return f'<Expense {self.id}: {self.amount} {self.currency} - {self.category}>'


class Budget(db.Model):
    """
    Budget planning and tracking for societies
    """
    __tablename__ = 'budget'
    
    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False, index=True)
    
    # Budget details
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False)  # operating, capital, project, event, etc.
    
    # Budget amounts
    allocated_amount = db.Column(db.Float, nullable=False)
    spent_amount = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='EUR')
    
    # Period
    period_start = db.Column(db.DateTime, nullable=False, index=True)
    period_end = db.Column(db.DateTime, nullable=False, index=True)
    
    # Status
    status = db.Column(db.String(20), default='active')  # active, closed, exceeded
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    society = db.relationship('Society', backref='budgets')
    
    @property
    def remaining_amount(self):
        """Calculate remaining budget"""
        return self.allocated_amount - self.spent_amount
    
    @property
    def percentage_spent(self):
        """Calculate percentage of budget spent"""
        if self.allocated_amount == 0:
            return 0
        return (self.spent_amount / self.allocated_amount) * 100
    
    def __repr__(self):
        return f'<Budget {self.id}: {self.name} - {self.allocated_amount} {self.currency}>'


class ContactMessage(db.Model):
    __tablename__ = 'contact_message'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)

    def __repr__(self):
        return f'<ContactMessage {self.id} from={self.email}>'


class SystemModule(db.Model):
    """
    System module for managing updates and extensions uploaded by admin.
    Allows for modular system updates with enable/disable functionality.
    """
    __tablename__ = 'system_module'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    version = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(255), nullable=False)  # Original zip filename
    description = db.Column(db.Text)
    enabled = db.Column(db.Boolean, default=False, index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=utc_now, index=True)
    enabled_at = db.Column(db.DateTime)
    disabled_at = db.Column(db.DateTime)
    
    # Relationships
    uploader = db.relationship('User', backref='uploaded_modules')

    def __repr__(self):
        return f'<SystemModule {self.name} v{self.version} enabled={self.enabled}>'
