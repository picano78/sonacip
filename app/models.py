"""
Database Models
All SQLAlchemy models for SONACIP platform
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


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


class User(UserMixin, db.Model):
    """
    User model - handles all user types
    Roles: super_admin, societa, staff, atleta, appassionato
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
    
    # Role and type
    role = db.Column(db.String(20), nullable=False, default='appassionato')
    # Roles: super_admin, societa, staff, atleta, appassionato
    
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
    society_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Link to società
    
    # For Atleta
    birth_date = db.Column(db.Date)
    sport = db.Column(db.String(100))
    athlete_society_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Link to società
    
    # Account status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
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
    
    def is_admin(self):
        """Check if user is super admin"""
        return self.role == 'super_admin'
    
    def is_society(self):
        """Check if user is a società"""
        return self.role == 'societa'
    
    def is_staff(self):
        """Check if user is staff"""
        return self.role == 'staff'
    
    def is_athlete(self):
        """Check if user is an athlete"""
        return self.role == 'atleta'
    
    def get_full_name(self):
        """Get full name or company name"""
        if self.role == 'societa' and self.company_name:
            return self.company_name
        elif self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
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
    society_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    society = db.relationship('User', foreign_keys=[society_id], backref='crm_contacts')
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'
    
    def __repr__(self):
        return f'<Contact {self.id}: {self.get_full_name()}>'


class Opportunity(db.Model):
    """
    CRM Opportunity model
    Sales opportunities, partnerships, sponsorships
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
    
    # Dates
    expected_close_date = db.Column(db.Date)
    actual_close_date = db.Column(db.Date)
    
    # Related contact
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'))
    
    # Ownership
    society_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contact = db.relationship('Contact', backref='opportunities')
    society = db.relationship('User', foreign_keys=[society_id], backref='crm_opportunities')
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
