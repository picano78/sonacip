"""
Database Models
All SQLAlchemy models for SONACIP platform
"""
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.utils import check_permission


# Association tables for many-to-many relationships
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

post_likes = db.Table('post_likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

event_athletes = db.Table('event_athletes',
    db.Column('event_id', db.Integer, db.ForeignKey('event.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('status', db.String(20), default='pending'),  # pending, accepted, rejected
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    db.Column('responded_at', db.DateTime)
)

# Society Calendar association tables (director-level calendar, not field planner)
society_calendar_event_staff = db.Table('society_calendar_event_staff',
    db.Column('event_id', db.Integer, db.ForeignKey('society_calendar_event.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

society_calendar_event_athletes = db.Table('society_calendar_event_athletes',
    db.Column('event_id', db.Integer, db.ForeignKey('society_calendar_event.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
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
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))  # Link to società
    
    # For Atleta
    birth_date = db.Column(db.Date)
    sport = db.Column(db.String(100))
    athlete_society_id = db.Column(db.Integer, db.ForeignKey('society.id'))  # Link to società
    
    # Account status
    is_active = db.Column(db.Boolean, default=True)
    is_banned = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
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
        society = self.get_primary_society()
        if not society:
            return False
        return society.id == society_id

    def get_primary_society(self):
        """Return Society entity for this user, if any."""
        if self.is_society() and self.society_profile:
            return self.society_profile
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
        Check if user has access to a specific feature based on their plan
        """
        if self.is_admin():
            return True
        
        subscription = self.get_active_subscription()
        if not subscription or not subscription.plan:
            # No active subscription - check free plan limits
            return False
        
        plan = subscription.plan
        feature_map = {
            'crm': plan.has_crm,
            'advanced_stats': plan.has_advanced_stats,
            'api_access': plan.has_api_access,
            'white_label': plan.has_white_label,
            'priority_support': plan.has_priority_support
        }
        
        return feature_map.get(feature_name, False)
    
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
    Social post model - LinkedIn-style posts
    """
    __tablename__ = 'post'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255))  # optional image
    
    # Visibility
    is_public = db.Column(db.Boolean, default=True)
    post_type = db.Column(db.String(50), default='personal')  # personal, official, tournament, match, automation

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
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    comments = db.relationship('Comment', backref='post', lazy='dynamic',
                              cascade='all, delete-orphan')
    liked_by = db.relationship('User', secondary=post_likes,
                              backref=db.backref('liked_posts', lazy='dynamic'),
                              lazy='dynamic')
    
    def is_liked_by(self, user):
        """Check if user liked this post"""
        return self.liked_by.filter(post_likes.c.user_id == user.id).count() > 0
    
    def __repr__(self):
        return f'<Post {self.id} by {self.user_id}>'


class Comment(db.Model):
    """
    Comment model for posts
    """
    __tablename__ = 'comment'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - convocated athletes
    convocated_athletes = db.relationship('User', secondary=event_athletes,
                                         backref=db.backref('events', lazy='dynamic'),
                                         lazy='dynamic')
    
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
            ).values(status=status, responded_at=datetime.utcnow())
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

    title = db.Column(db.String(200), nullable=False)
    team = db.Column(db.String(100))  # textual team/category label
    category = db.Column(db.String(100))
    event_type = db.Column(db.String(50), nullable=False)  # match, tournament, meeting, travel, other
    competition_name = db.Column(db.String(200))

    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime)

    location_text = db.Column(db.String(255))
    notes = db.Column(db.Text)

    share_to_social = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    society = db.relationship('Society', backref=db.backref('calendar_events', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by])
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime)
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = datetime.utcnow()
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
    action = db.Column(db.String(100), nullable=False)  # Action type
    entity_type = db.Column(db.String(50))  # User, Post, Event, etc.
    entity_id = db.Column(db.Integer)  # ID of affected entity
    details = db.Column(db.Text)  # JSON or text details
    ip_address = db.Column(db.String(45))  # IPv4 or IPv6
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    user = db.relationship('User', backref='audit_logs')
    
    def __repr__(self):
        return f'<AuditLog {self.action} by User {self.user_id}>'


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<AdsSetting CPM={self.price_per_thousand_views}>'


class SocialSetting(db.Model):
    """Global social governance controlled by super admin."""
    __tablename__ = 'social_setting'

    id = db.Column(db.Integer, primary_key=True)
    feed_enabled = db.Column(db.Boolean, default=True)
    allow_likes = db.Column(db.Boolean, default=True)
    allow_comments = db.Column(db.Boolean, default=True)
    allow_shares = db.Column(db.Boolean, default=True)
    boost_official = db.Column(db.Boolean, default=True)
    mute_user_posts = db.Column(db.Boolean, default=False)
    max_posts_per_day = db.Column(db.Integer, default=20)
    boosted_types = db.Column(db.Text)  # JSON list of types to prioritize (tournaments, matches)
    muted_types = db.Column(db.Text)    # JSON list of types to suppress

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    layout_style = db.Column(db.String(50), default='standard')

    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<SmtpSetting enabled={self.enabled}>'


class Message(db.Model):
    """
    Direct messaging between users
    """
    __tablename__ = 'message'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    
    # Status
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime)
    
    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='messages_sent')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='messages_received')
    
    def __repr__(self):
        return f'<Message {self.id} from {self.sender_id} to {self.recipient_id}>'


class Contact(db.Model):
    """
    CRM Contact model
    Lead, prospect, sponsor, partner contacts
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
    
    # Address
    address = db.Column(db.String(255))
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(10))
    
    # Notes
    notes = db.Column(db.Text)
    
    # Ownership
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    society = db.relationship('Society', foreign_keys=[society_id], backref='crm_contacts')
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'
    
    def __repr__(self):
        return f'<Contact {self.id}: {self.get_full_name()}>'


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    activity_date = db.Column(db.Date, default=datetime.utcnow)
    completed = db.Column(db.Boolean, default=False)
    
    # Related records
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'))
    opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunity.id'))
    
    # Creator
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Role {self.name}>'


# Association table for roles and permissions
role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    trial_end_date = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    
    # Billing
    next_billing_date = db.Column(db.DateTime)
    amount = db.Column(db.Float)
    
    # Auto-renewal
    auto_renew = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('subscriptions', lazy='dynamic'))
    society = db.relationship('Society', backref=db.backref('subscriptions', lazy='dynamic'))
    plan = db.relationship('Plan', backref='subscriptions')
    
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status == 'active' and (not self.end_date or self.end_date > datetime.utcnow())
    
    def is_trial(self):
        """Check if subscription is in trial period"""
        return self.status == 'trial' and (not self.trial_end_date or self.trial_end_date > datetime.utcnow())
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='payments')
    society = db.relationship('Society', backref='payments')
    subscription = db.relationship('Subscription', backref='payments')
    
    def __repr__(self):
        return f'<Payment {self.id}: {self.amount} {self.currency} - {self.status}>'


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
    
    # Stats and metadata
    total_athletes = db.Column(db.Integer, default=0)
    total_staff = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Template {self.name}>'


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    society_id = db.Column(db.Integer, db.ForeignKey('society.id'), nullable=False)
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

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

    tournament = db.relationship('Tournament', backref=db.backref('teams', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<TournamentTeam {self.name}>'


class TournamentMatch(db.Model):
    __tablename__ = 'tournament_match'

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey('tournament_team.id'), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey('tournament_team.id'), nullable=False)

    round_label = db.Column(db.String(100))  # group A, quarterfinal, etc.
    match_date = db.Column(db.DateTime)
    location = db.Column(db.String(255))

    home_score = db.Column(db.Integer)
    away_score = db.Column(db.Integer)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, played, cancelled

    calendar_event_id = db.Column(db.Integer, db.ForeignKey('society_calendar_event.id'))

    home_team = db.relationship('TournamentTeam', foreign_keys=[home_team_id])
    away_team = db.relationship('TournamentTeam', foreign_keys=[away_team_id])

    def set_score(self, home, away):
        self.home_score = home
        self.away_score = away
        self.status = 'played'

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    period = db.Column(db.String(20))  # hourly, daily, weekly, monthly, yearly
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Goal {self.title}>'


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ModerationRule {self.name}>'
