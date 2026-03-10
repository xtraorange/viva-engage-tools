"""UI utilities and helpers."""
import os
import logging


def setup_flask_app(base_path: str):
    """Set up Flask app with common configuration."""
    from flask import Flask

    # Resolve templates from the ui package location, not current working directory.
    app = Flask(__name__, template_folder="templates")

    # Suppress Flask/Werkzeug webserver output
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.logger.setLevel(logging.ERROR)

    # Make updating and update_status available to all templates
    @app.context_processor
    def inject_update_status():
        return {
            "updating": app.config.get("updating"),
            "update_status": app.config.get("update_status")
        }

    return app


def load_version_info(base_path: str):
    """Load version and repository info."""
    from ..services.config_service import ConfigService
    config_service = ConfigService(base_path)
    return config_service.load_version_config()