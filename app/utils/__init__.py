"""
Utilities package for the SONACIP application.

This acts as a shim to maintain backward compatibility.
The main utilities are in ../utils.py (the file), while this directory
contains specialized utility modules (caching, search, exports, etc.).

To avoid circular imports, submodules are not eagerly imported here.
Use explicit imports like: from app.utils.caching import cache_key
"""

# Don't eagerly import submodules to avoid circular imports
# They can be imported directly when needed

__all__ = [
    'caching',
    'search',
    'exports',
    'error_handling',
]
