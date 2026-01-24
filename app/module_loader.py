"""
Dynamic module discovery and registration for external feature packs.
"""
import importlib
import os
import pkgutil
import sys
from typing import Optional


def discover_and_register_modules(app) -> None:
    """Load optional modules without breaking core app if missing/invalid."""
    modules_path = app.config.get('MODULES_FOLDER')
    if not modules_path or not os.path.isdir(modules_path):
        return

    # Make sure Python can import from the folder
    if modules_path not in sys.path:
        sys.path.append(modules_path)

    package_import = 'app.modules'
    for _, name, _ in pkgutil.iter_modules([modules_path]):
        module_name = f"{package_import}.{name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            app.logger.warning(f"Modulo opzionale '{module_name}' non caricato: {exc}")
            continue

        _maybe_register_blueprint(app, module, name)
        _maybe_call_register(app, module)


def _maybe_register_blueprint(app, module, name: str) -> None:
    bp = getattr(module, 'bp', None)
    if not bp:
        return
    url_prefix: Optional[str] = getattr(module, 'url_prefix', f'/{name}')
    try:
        app.register_blueprint(bp, url_prefix=url_prefix)
    except Exception as exc:
        app.logger.warning(f"Blueprint '{name}' non registrato: {exc}")


def _maybe_call_register(app, module) -> None:
    register_fn = getattr(module, 'register', None)
    if callable(register_fn):
        try:
            register_fn(app)
        except Exception as exc:
            app.logger.warning(f"Funzione di bootstrap modulo fallita: {exc}")
