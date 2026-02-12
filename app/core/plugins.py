"""
External plugin loader for SONACIP.

Plugins are discovered from a filesystem folder (default: `<BASE_DIR>/plugins`).
Each plugin must live in its own folder:

  plugins/<plugin_id>/
    plugin.py          # required, must export `register(app)` callable
    plugin.json        # optional metadata
    templates/         # optional templates
    static/            # optional static assets

The loader is intentionally conservative:
- No DB migrations or schema changes.
- Failures are isolated (one broken plugin won't stop the app).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional

from flask import Blueprint


_ID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_\\-]{1,60}$")


@dataclass(frozen=True)
class PluginMeta:
    plugin_id: str
    name: str
    version: str
    description: str
    url_prefix: Optional[str] = None
    enabled_by_default: bool = True


def _parse_list(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip()}


def _load_meta(plugin_dir: str, plugin_id: str) -> PluginMeta:
    meta_path = os.path.join(plugin_dir, "plugin.json")
    default = PluginMeta(
        plugin_id=plugin_id,
        name=plugin_id,
        version="0.0.0",
        description="",
        url_prefix=f"/plugins/{plugin_id}",
        enabled_by_default=True,
    )
    if not os.path.isfile(meta_path):
        return default
    try:
        data = json.loads(open(meta_path, "r", encoding="utf-8").read())
        return PluginMeta(
            plugin_id=plugin_id,
            name=str(data.get("name") or plugin_id),
            version=str(data.get("version") or "0.0.0"),
            description=str(data.get("description") or ""),
            url_prefix=str(data.get("url_prefix") or default.url_prefix) if data.get("url_prefix", None) is not None else default.url_prefix,
            enabled_by_default=bool(data.get("enabled_by_default", True)),
        )
    except Exception:
        return default


def create_plugin_blueprint(plugin_id: str, plugin_dir: str, url_prefix: str | None = None) -> Blueprint:
    """
    Convenience helper for plugins: returns a Blueprint that can serve templates/static
    from `templates/` and `static/` inside the plugin folder.
    """
    templates_dir = os.path.join(plugin_dir, "templates")
    static_dir = os.path.join(plugin_dir, "static")
    bp = Blueprint(
        f"plugin_{plugin_id}",
        __name__,
        url_prefix=url_prefix,
        template_folder=templates_dir if os.path.isdir(templates_dir) else None,
        static_folder=static_dir if os.path.isdir(static_dir) else None,
        static_url_path=f"/static/plugins/{plugin_id}" if os.path.isdir(static_dir) else None,
    )
    return bp


def _import_plugin_module(plugin_id: str, plugin_dir: str):
    """
    Import plugin.py module with security checks.
    
    Security considerations:
    - Validates plugin directory is within PLUGINS_FOLDER
    - Prevents path traversal attacks through multiple checks:
      1. Preliminary check for '..' in path (fast early rejection)
      2. Realpath validation ensures resolved path is within plugin_dir
    - Isolates plugin modules to prevent conflicts
    """
    # Security: Preliminary path traversal check (fast early rejection)
    # Note: This is followed by a more thorough realpath validation below
    if '..' in plugin_dir or not os.path.isabs(plugin_dir):
        raise ValueError(f"Invalid plugin directory path: {plugin_dir}")
    
    plugin_py = os.path.join(plugin_dir, "plugin.py")
    
    # Security: Verify the resolved path is still within plugin_dir
    real_plugin_py = os.path.realpath(plugin_py)
    real_plugin_dir = os.path.realpath(plugin_dir)
    if not real_plugin_py.startswith(real_plugin_dir):
        raise ValueError(f"Security: plugin.py path traversal detected for '{plugin_id}'")
    
    if not os.path.isfile(plugin_py):
        raise FileNotFoundError(f"Missing plugin.py for plugin '{plugin_id}'")

    # Load as an isolated module name to avoid collisions.
    module_name = f"sonacip_ext_plugin__{plugin_id}"
    spec = importlib.util.spec_from_file_location(module_name, plugin_py)
    if not spec or not spec.loader:
        raise ImportError(f"Cannot import plugin '{plugin_id}'")

    module = importlib.util.module_from_spec(spec)
    # Allow relative imports inside the plugin folder.
    module.__package__ = module_name
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def load_external_plugins(app) -> list[PluginMeta]:
    """
    Discover and load plugins from PLUGINS_FOLDER.

    Enabled rules:
    - If PLUGINS_ALLOWLIST is set, only those IDs are loaded.
    - If PLUGINS_BLOCKLIST is set, those IDs are skipped.
    - Otherwise, plugins with enabled_by_default=true are loaded.
    
    Security:
    - Validates plugin folder exists and is a directory
    - Prevents loading plugins from outside the designated folder
    - Validates plugin IDs against strict regex
    """
    plugins_dir = app.config.get("PLUGINS_FOLDER")
    if not plugins_dir or not os.path.isdir(plugins_dir):
        app.extensions["sonacip_plugins"] = []
        return []
    
    # Security: Get absolute path and validate it's a real directory
    plugins_dir = os.path.abspath(os.path.realpath(plugins_dir))
    if not os.path.isdir(plugins_dir):
        app.logger.error("PLUGINS_FOLDER is not a valid directory: %s", plugins_dir)
        app.extensions["sonacip_plugins"] = []
        return []

    allow = _parse_list(app.config.get("PLUGINS_ALLOWLIST"))
    block = _parse_list(app.config.get("PLUGINS_BLOCKLIST"))

    loaded: list[PluginMeta] = []
    for entry in sorted(os.listdir(plugins_dir)):
        plugin_id = entry.strip()
        if not plugin_id or plugin_id.startswith("."):
            continue
        if not _ID_RE.match(plugin_id):
            app.logger.warning("Skipping invalid plugin id folder: %s", plugin_id)
            continue

        plugin_path = os.path.join(plugins_dir, plugin_id)
        
        # Security: Prevent path traversal
        real_plugin_path = os.path.realpath(plugin_path)
        if not real_plugin_path.startswith(plugins_dir):
            app.logger.error("Security: Path traversal attempt detected for plugin: %s", plugin_id)
            continue
            
        if not os.path.isdir(plugin_path):
            continue

        meta = _load_meta(plugin_path, plugin_id)
        if allow and plugin_id not in allow:
            continue
        if plugin_id in block:
            continue
        if not allow and not meta.enabled_by_default:
            continue

        try:
            module = _import_plugin_module(plugin_id, plugin_path)
            register_fn: Optional[Callable[[Any], Any]] = getattr(module, "register", None)
            if not callable(register_fn):
                raise TypeError(f"Plugin '{plugin_id}' has no callable register(app)")

            # Provide helpers to plugin code.
            setattr(module, "create_plugin_blueprint", create_plugin_blueprint)

            register_fn(app)
            loaded.append(meta)
            app.logger.info("Loaded plugin %s (%s)", meta.plugin_id, meta.version)
        except Exception as exc:
            app.logger.exception("Failed to load plugin '%s': %s", plugin_id, exc)
            continue

    app.extensions["sonacip_plugins"] = loaded
    return loaded

