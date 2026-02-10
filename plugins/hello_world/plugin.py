from flask import render_template


def register(app):
    """
    Example SONACIP plugin.

    - Registers a blueprint serving its own templates/static.
    - Adds a simple route under /plugins/hello_world
    """
    # Import helper from core (available because SONACIP imports this plugin).
    from app.core.plugins import create_plugin_blueprint

    import os
    plugin_dir = os.path.dirname(__file__)
    bp = create_plugin_blueprint("hello_world", plugin_dir, url_prefix="/plugins/hello_world")

    @bp.get("/")
    def index():
        return render_template("hello_world/index.html")

    app.register_blueprint(bp)

