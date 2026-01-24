"""
Admin utilities and decorators
"""
# Import common decorators from app.utils for consistency
from app.utils import admin_required, can_manage_user, can_view_user

# Re-export for backward compatibility
__all__ = ['admin_required', 'can_manage_user', 'can_view_user']
