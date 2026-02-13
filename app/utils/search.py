"""
Advanced Search Utilities
Provides flexible search across multiple models with filters
"""
from sqlalchemy import or_, and_, func
from app.models import User, Post, Event, Contact, Opportunity, Tournament, Match
from datetime import datetime, timedelta, timezone


class SearchEngine:
    """Advanced search engine for SONACIP platform"""
    
    @staticmethod
    def search_users(query, filters=None, limit=50, offset=0):
        """
        Search users with advanced filters
        
        Args:
            query: Search query string
            filters: Dictionary of filters (role, society_id, is_active, etc.)
            limit: Maximum results to return
            offset: Pagination offset
            
        Returns:
            List of User objects
        """
        filters = filters or {}
        
        # Base query
        search_query = User.query
        
        # Text search
        if query:
            search_query = search_query.filter(
                or_(
                    User.username.ilike(f'%{query}%'),
                    User.email.ilike(f'%{query}%'),
                    User.first_name.ilike(f'%{query}%'),
                    User.last_name.ilike(f'%{query}%'),
                    func.concat(User.first_name, ' ', User.last_name).ilike(f'%{query}%')
                )
            )
        
        # Apply filters
        if 'role' in filters:
            search_query = search_query.filter(User.role_id == filters['role'])
        
        if 'is_active' in filters:
            search_query = search_query.filter(User.is_active == filters['is_active'])
        
        if 'society_id' in filters:
            from app.models import SocietyMembership
            member_ids = SocietyMembership.query.filter_by(
                society_id=filters['society_id'],
                status='active'
            ).with_entities(SocietyMembership.user_id).all()
            member_ids = [m[0] for m in member_ids]
            search_query = search_query.filter(User.id.in_(member_ids))
        
        # Pagination
        results = search_query.limit(limit).offset(offset).all()
        
        return results
    
    @staticmethod
    def search_posts(query, filters=None, limit=50, offset=0):
        """
        Search social posts
        
        Args:
            query: Search query string
            filters: Dictionary of filters (author_id, visibility, date_from, date_to)
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of Post objects
        """
        filters = filters or {}
        
        search_query = Post.query
        
        # Text search
        if query:
            search_query = search_query.filter(
                Post.content.ilike(f'%{query}%')
            )
        
        # Apply filters
        if 'author_id' in filters:
            search_query = search_query.filter(Post.author_id == filters['author_id'])
        
        if 'visibility' in filters:
            search_query = search_query.filter(Post.visibility == filters['visibility'])
        
        if 'date_from' in filters:
            search_query = search_query.filter(Post.created_at >= filters['date_from'])
        
        if 'date_to' in filters:
            search_query = search_query.filter(Post.created_at <= filters['date_to'])
        
        # Order by relevance and date
        results = search_query.order_by(
            Post.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return results
    
    @staticmethod
    def search_events(query, filters=None, limit=50, offset=0):
        """
        Search events
        
        Args:
            query: Search query string
            filters: Dictionary of filters (society_id, status, date_from, date_to, event_type)
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of Event objects
        """
        filters = filters or {}
        
        search_query = Event.query
        
        # Text search
        if query:
            search_query = search_query.filter(
                or_(
                    Event.title.ilike(f'%{query}%'),
                    Event.description.ilike(f'%{query}%'),
                    Event.location.ilike(f'%{query}%')
                )
            )
        
        # Apply filters
        if 'society_id' in filters:
            search_query = search_query.filter(Event.society_id == filters['society_id'])
        
        if 'status' in filters:
            search_query = search_query.filter(Event.status == filters['status'])
        
        if 'event_type' in filters:
            search_query = search_query.filter(Event.event_type == filters['event_type'])
        
        if 'date_from' in filters:
            search_query = search_query.filter(Event.event_date >= filters['date_from'])
        
        if 'date_to' in filters:
            search_query = search_query.filter(Event.event_date <= filters['date_to'])
        
        results = search_query.order_by(
            Event.event_date.desc()
        ).limit(limit).offset(offset).all()
        
        return results
    
    @staticmethod
    def search_contacts(query, filters=None, limit=50, offset=0):
        """
        Search CRM contacts
        
        Args:
            query: Search query string
            filters: Dictionary of filters (society_id, contact_type, status)
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of Contact objects
        """
        filters = filters or {}
        
        search_query = Contact.query
        
        # Text search
        if query:
            search_query = search_query.filter(
                or_(
                    Contact.name.ilike(f'%{query}%'),
                    Contact.email.ilike(f'%{query}%'),
                    Contact.phone.ilike(f'%{query}%'),
                    Contact.company.ilike(f'%{query}%')
                )
            )
        
        # Apply filters
        if 'society_id' in filters:
            search_query = search_query.filter(Contact.society_id == filters['society_id'])
        
        if 'contact_type' in filters:
            search_query = search_query.filter(Contact.contact_type == filters['contact_type'])
        
        if 'status' in filters:
            search_query = search_query.filter(Contact.status == filters['status'])
        
        results = search_query.order_by(
            Contact.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return results
    
    @staticmethod
    def search_opportunities(query, filters=None, limit=50, offset=0):
        """
        Search CRM opportunities
        
        Args:
            query: Search query string
            filters: Dictionary of filters (society_id, status, min_value, max_value)
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of Opportunity objects
        """
        filters = filters or {}
        
        search_query = Opportunity.query
        
        # Text search
        if query:
            search_query = search_query.filter(
                or_(
                    Opportunity.title.ilike(f'%{query}%'),
                    Opportunity.description.ilike(f'%{query}%')
                )
            )
        
        # Apply filters
        if 'society_id' in filters:
            search_query = search_query.filter(Opportunity.society_id == filters['society_id'])
        
        if 'status' in filters:
            search_query = search_query.filter(Opportunity.status == filters['status'])
        
        if 'min_value' in filters:
            search_query = search_query.filter(Opportunity.value >= filters['min_value'])
        
        if 'max_value' in filters:
            search_query = search_query.filter(Opportunity.value <= filters['max_value'])
        
        results = search_query.order_by(
            Opportunity.value.desc()
        ).limit(limit).offset(offset).all()
        
        return results
    
    @staticmethod
    def search_tournaments(query, filters=None, limit=50, offset=0):
        """
        Search tournaments
        
        Args:
            query: Search query string
            filters: Dictionary of filters (society_id, status, sport_type)
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of Tournament objects
        """
        filters = filters or {}
        
        search_query = Tournament.query
        
        # Text search
        if query:
            search_query = search_query.filter(
                or_(
                    Tournament.name.ilike(f'%{query}%'),
                    Tournament.description.ilike(f'%{query}%')
                )
            )
        
        # Apply filters
        if 'society_id' in filters:
            search_query = search_query.filter(Tournament.society_id == filters['society_id'])
        
        if 'status' in filters:
            search_query = search_query.filter(Tournament.status == filters['status'])
        
        if 'sport_type' in filters:
            search_query = search_query.filter(Tournament.sport_type == filters['sport_type'])
        
        results = search_query.order_by(
            Tournament.start_date.desc()
        ).limit(limit).offset(offset).all()
        
        return results
    
    @staticmethod
    def global_search(query, limit=10):
        """
        Search across all entities
        
        Args:
            query: Search query string
            limit: Results per entity type
            
        Returns:
            Dictionary with results by type
        """
        results = {
            'users': SearchEngine.search_users(query, limit=limit),
            'posts': SearchEngine.search_posts(query, limit=limit),
            'events': SearchEngine.search_events(query, limit=limit),
            'contacts': SearchEngine.search_contacts(query, limit=limit),
            'opportunities': SearchEngine.search_opportunities(query, limit=limit),
            'tournaments': SearchEngine.search_tournaments(query, limit=limit)
        }
        
        return results
