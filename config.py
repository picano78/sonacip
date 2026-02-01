"""
Compatibility shim.

The canonical config lives in `app.core.config`.
Keep this module for legacy imports such as `from config import config`.
"""

from app.core.config import Config, DevelopmentConfig, ProductionConfig, config

__all__ = [
    "Config",
    "DevelopmentConfig",
    "ProductionConfig",
    "config",
]
