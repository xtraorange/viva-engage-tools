"""Main routes for the web interface."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
import os
import threading

from ...services.config_service import ConfigService
from ...services.group_service import GroupService
from ...services.report_service import ReportService
from ...generate_reports import discover_groups

main_bp = Blueprint('main', __name__)


def init_main_routes(app, base_path: str):
    """Initialize main routes with dependencies."""
    config_service = ConfigService(base_path)
    group_service = GroupService(base_path)

    @main_bp.route("/")
    def index():
        """Main dashboard - generate reports."""
        groups = group_service.discover_groups()
        cfg = config_service.load_general_config()

        # Get all tags for the UI
        tags = set()
        for g in groups:
            tags.update(g.tags)
        tags = sorted(tags)

        return render_template("generate.html", config=cfg, groups=groups, tags=tags,
                               updating=app.config.get("updating"),
                               update_error=app.config.get("update_error"))

    @main_bp.route("/", methods=["POST"])
    def generate():
        """Start report generation."""
        if app.config.get("updating"):
            return "Update in progress, please wait and refresh after restart", 503

        groups = group_service.discover_groups()
        cfg = config_service.load_general_config()

        selected_handles = request.form.getlist("groups")
        selected = [g for g in groups if g.handle in selected_handles]

        tag_sel = request.form.getlist("tags")
        for t in tag_sel:
            for g in groups:
                if t in g.tags and g not in selected:
                    selected.append(g)

        should_email = request.form.get("email") == "on"
        override = request.form.get("override_email") or None

        # Start processing in background
        tracker = start_jobs(app, selected, should_email, override)
        app.config["tracker"] = tracker

        return redirect(url_for("main.status"))

    @main_bp.route("/status")
    def status():
        """Show processing status."""
        tracker = app.config.get("tracker")
        if not tracker:
            return redirect(url_for("main.index"))

        return render_template("status.html", tracker=tracker)

    @main_bp.route("/api/status")
    def api_status():
        """API endpoint for status polling."""
        tracker = app.config.get("tracker")
        if not tracker:
            return jsonify(error="No job running")

        return jsonify(status=tracker.status, done=tracker.done, total=tracker.total)

    @main_bp.route("/settings", methods=["GET", "POST"])
    def settings():
        """Settings page."""
        cfg = config_service.load_general_config()

        if request.method == "POST":
            # Update general config based on form fields
            for key in [
                "oracle_tns",
                "output_dir",
                "max_workers",
                "email_method",
                "outlook_auto_send",
                "smtp_server",
                "smtp_port",
                "smtp_use_tls",
                "smtp_from",
                "email_recipient",
            ]:
                if key in request.form:
                    val = request.form.get(key)
                    if val == "":
                        cfg.pop(key, None)
                    else:
                        if key in ["max_workers", "smtp_port"]:
                            try:
                                cfg[key] = int(val)
                            except ValueError:
                                cfg[key] = val
                        elif key in ["smtp_use_tls", "outlook_auto_send"]:
                            cfg[key] = request.form.get(key) == "on"
                        else:
                            cfg[key] = val

            config_service.save_general_config(cfg)
            return redirect(url_for("main.settings"))

        groups = group_service.discover_groups()
        return render_template("settings.html", config=cfg, groups=groups,
                               updating=app.config.get("updating"),
                               update_error=app.config.get("update_error"))

    return main_bp


def start_jobs(app, selected, should_email, override_email):
    """Start background job processing."""
    from ...services.config_service import ConfigService
    from ...services.report_service import ReportService

    base = os.getcwd()
    config_service = ConfigService(base)
    cfg = config_service.load_general_config()
    report_service = ReportService(cfg)

    # create tracker that will be visible to the UI
    from ...db import ProgressTracker
    tracker = ProgressTracker(len(selected))

    def task():
        # pass the tracker so it gets updated during processing
        report_service.process_groups(
            selected,
            should_email,
            override_email,
            tracker=tracker,
        )
        # Processing complete - tracker will be cleaned up by the UI

    threading.Thread(target=task, daemon=True).start()

    # Return the tracker for status monitoring
    return tracker