"""Update management routes."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file
import os
import yaml
import urllib.request
import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta

from ...services.config_service import ConfigService

updates_bp = Blueprint('updates', __name__)


def init_updates_routes(app, base_path: str):
    """Initialize update routes with dependencies."""
    config_service = ConfigService(base_path)
    __version__, GITHUB_REPO = config_service.load_version_config()
    CHECK_INTERVAL_SECONDS = 24 * 60 * 60  # check GitHub no more than once per day

    def _parse_version(v: str):
        return tuple(int(x) for x in v.lstrip('v').split('.') if x.isdigit())

    def _is_newer(latest: str, current: str) -> bool:
        try:
            return _parse_version(latest) > _parse_version(current)
        except Exception:
            return latest != current

    def check_for_updates(cfg: dict) -> dict:
        """Always fetch latest version from GitHub and return update info."""
        now = datetime.now()
        info = cfg.get("update_info") or {}

        # Always fetch fresh from GitHub
        try:
            raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/config/version.yaml"
            with urllib.request.urlopen(raw_url) as resp:
                data = resp.read()
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            remote_config = yaml.safe_load(data)

            if remote_config and remote_config.get("version"):
                remote_version = remote_config.get("version")
                info = {"version": remote_version, "body": ""}

                # fetch release notes (optional)
                try:
                    releases_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tag/v{remote_version}"
                    with urllib.request.urlopen(releases_url) as resp:
                        release_data = json.load(resp)
                        if release_data.get("body"):
                            info["body"] = release_data.get("body")
                except Exception:
                    pass

                cfg["update_info"] = info
        except Exception as e:
            # on fetch failure, keep existing info but log the issue
            pass

        # Always update timestamp of last check attempt
        info["last_check"] = now.isoformat()
        cfg["update_info"] = info
        config_service.save_general_config(cfg)

        return info

    @updates_bp.route("/updates", methods=["GET", "POST"])
    def updates():
        """Updates page."""
        cfg = config_service.load_general_config()
        # if user clicked "check again", clear the old info first
        if request.args.get("check") == "true":
            cfg["update_info"] = {}
            config_service.save_general_config(cfg)
        update_info = check_for_updates(cfg)
        update_available = False
        if update_info and update_info.get("version"):
            update_available = _is_newer(update_info.get("version"), __version__)
        if request.method == "POST":
            # trigger manual update via perform_update
            return redirect(url_for("updates.perform_update"))
        return render_template("updates.html",
                               current_version=__version__,
                               update_info=update_info,
                               update_available=update_available,
                               updating=app.config.get("updating"),
                               update_status=app.config.get("update_status"),
                               update_error=app.config.get("update_error"))

    @updates_bp.route("/update", methods=["GET", "POST"])
    def perform_update():
        """Perform application update."""
        if app.config.get("updating"):
            return redirect(url_for("main.index"))
        app.config["updating"] = True
        app.config["update_status"] = "Starting update..."
        app.config["update_output"] = []

        def updater():
            try:
                # stash any local changes (including config) so pull can succeed
                app.config["update_status"] = "Stashing local modifications..."
                app.config["update_output"].append("$ git stash push -u -m jampy-update")
                st = subprocess.run(["git", "stash", "push", "-u", "-m", "jampy-update"], cwd=base_path, capture_output=True, text=True, timeout=30)
                if st.stdout:
                    app.config["update_output"].append(st.stdout.strip())
                if st.stderr:
                    app.config["update_output"].append(st.stderr.strip())

                app.config["update_status"] = "Fetching latest code..."
                app.config["update_output"].append("$ git pull --ff-only")
                result = subprocess.run(["git", "pull", "--ff-only"], cwd=base_path, capture_output=True, text=True, timeout=60, check=True)
                if result.stdout:
                    app.config["update_output"].append(result.stdout.strip())
                if result.stderr:
                    app.config["update_output"].append(result.stderr.strip())

                # restore stash
                app.config["update_status"] = "Restoring local changes..."
                app.config["update_output"].append("$ git stash pop")
                pop = subprocess.run(["git", "stash", "pop"], cwd=base_path, capture_output=True, text=True, timeout=30)
                if pop.stdout:
                    app.config["update_output"].append(pop.stdout.strip())
                if pop.stderr:
                    app.config["update_output"].append(pop.stderr.strip())

                app.config["update_status"] = "Installing dependencies..."
                app.config["update_output"].append(f"$ {sys.executable} -m pip install -r requirements.txt")
                result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=base_path, capture_output=True, text=True, timeout=120, check=True)
                if result.stdout:
                    app.config["update_output"].append(result.stdout.strip())
                if result.stderr:
                    app.config["update_output"].append(result.stderr.strip())

                app.config["update_status"] = "Update complete! Please restart the app."
                app.config["update_output"].append("✓ Update successful. Please restart the application.")
            except subprocess.TimeoutExpired:
                app.config["update_error"] = "Update timed out. Check your network and try again."
                app.config["update_status"] = "Update timed out."
                app.config["update_output"].append("✗ Operation timed out")
            except subprocess.CalledProcessError as e:
                msg = f"Command failed (exit {e.returncode})"
                app.config["update_output"].append(f"✗ {msg}")
                if e.stdout:
                    app.config["update_output"].append("STDOUT: " + e.stdout.strip())
                if e.stderr:
                    app.config["update_output"].append("STDERR: " + e.stderr.strip())
                app.config["update_error"] = msg
                app.config["update_status"] = "Update failed."
            except Exception as e:
                app.config["update_error"] = str(e)
                app.config["update_status"] = "Update failed."
                app.config["update_output"].append(f"✗ Error: {str(e)}")
            finally:
                app.config["updating"] = False

        threading.Thread(target=updater, daemon=True).start()
        return redirect(url_for("main.index"))

    @updates_bp.route("/force-update", methods=["POST"])
    def force_update():
        """Force update regardless of version check."""
        if app.config.get("updating"):
            return redirect(url_for("main.index"))
        app.config["updating"] = True
        app.config["update_status"] = "Starting force update..."
        app.config["update_output"] = []

        def updater():
            try:
                # stash any local changes (including config) so pull can succeed
                app.config["update_status"] = "Stashing local modifications..."
                app.config["update_output"].append("$ git stash push -u -m jampy-update")
                st = subprocess.run(["git", "stash", "push", "-u", "-m", "jampy-update"], cwd=base_path, capture_output=True, text=True, timeout=30)
                if st.stdout:
                    app.config["update_output"].append(st.stdout.strip())
                if st.stderr:
                    app.config["update_output"].append(st.stderr.strip())

                app.config["update_status"] = "Fetching latest code..."
                app.config["update_output"].append("$ git pull --ff-only")
                result = subprocess.run(["git", "pull", "--ff-only"], cwd=base_path, capture_output=True, text=True, timeout=60, check=True)
                if result.stdout:
                    app.config["update_output"].append(result.stdout.strip())
                if result.stderr:
                    app.config["update_output"].append(result.stderr.strip())

                # restore stash
                app.config["update_status"] = "Restoring local changes..."
                app.config["update_output"].append("$ git stash pop")
                pop = subprocess.run(["git", "stash", "pop"], cwd=base_path, capture_output=True, text=True, timeout=30)
                if pop.stdout:
                    app.config["update_output"].append(pop.stdout.strip())
                if pop.stderr:
                    app.config["update_output"].append(pop.stderr.strip())

                app.config["update_status"] = "Installing dependencies..."
                app.config["update_output"].append(f"$ {sys.executable} -m pip install -r requirements.txt")
                result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=base_path, capture_output=True, text=True, timeout=120, check=True)
                if result.stdout:
                    app.config["update_output"].append(result.stdout.strip())
                if result.stderr:
                    app.config["update_output"].append(result.stderr.strip())

                app.config["update_status"] = "Force update complete! Please restart the app."
                app.config["update_output"].append("✓ Force update successful. Please restart the application.")
            except subprocess.TimeoutExpired:
                app.config["update_error"] = "Update timed out. Check your network and try again."
                app.config["update_status"] = "Update timed out."
                app.config["update_output"].append("✗ Operation timed out")
            except subprocess.CalledProcessError as e:
                msg = f"Command failed (exit {e.returncode})"
                app.config["update_output"].append(f"✗ {msg}")
                if e.stdout:
                    app.config["update_output"].append("STDOUT: " + e.stdout.strip())
                if e.stderr:
                    app.config["update_output"].append("STDERR: " + e.stderr.strip())
                app.config["update_error"] = msg
                app.config["update_status"] = "Update failed."
            except Exception as e:
                app.config["update_error"] = str(e)
                app.config["update_status"] = "Update failed."
                app.config["update_output"].append(f"✗ Error: {str(e)}")
            finally:
                app.config["updating"] = False

        threading.Thread(target=updater, daemon=True).start()
        return redirect(url_for("main.index"))

    @updates_bp.route("/api/update-status")
    def update_status_api():
        """Return current update status and output for live polling."""
        return jsonify({
            "updating": app.config.get("updating", False),
            "status": app.config.get("update_status", ""),
            "output": app.config.get("update_output", []),
            "error": app.config.get("update_error", "")
        })

    @updates_bp.route("/restart", methods=["POST"])
    def restart():
        """Signal the launcher to restart the server."""
        # set flag
        try:
            with open(os.path.join(base_path, "restart.flag"), "w") as f:
                f.write("restart")
        except Exception:
            pass
        return redirect(url_for("main.index"))

    @updates_bp.route("/email-templates", methods=["GET", "POST"])
    def email_templates():
        """Email templates management."""
        std_template = config_service.load_email_template_config("standard")
        override_template = config_service.load_email_template_config("override")

        if request.method == "POST":
            template_type = request.form.get("template_type")
            subject = request.form.get("subject")
            body = request.form.get("body")

            config_service.save_email_template_config(template_type, {"subject": subject, "body": body})
            return redirect(url_for("updates.email_templates"))

        return render_template("email_templates.html",
                             std_template=std_template,
                             override_template=override_template)

    @updates_bp.route("/query-builder", methods=["GET"])
    def query_builder():
        """UI for building hierarchy queries."""
        return render_template("query_builder.html")

    @updates_bp.route("/backup")
    def backup():
        """Create a zip backup of all configuration and groups."""
        from ...utils.file_utils import create_backup_zip, get_backup_filename
        zip_buffer = create_backup_zip(base_path)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=get_backup_filename()
        )

    @updates_bp.route("/restore", methods=["GET", "POST"])
    def restore():
        """Restore from backup."""
        if request.method == "POST":
            if 'file' not in request.files:
                return render_template("restore.html", error="No file provided")

            file = request.files['file']
            if not file.filename.endswith('.zip'):
                return render_template("restore.html", error="File must be a zip archive")

            try:
                import zipfile
                with zipfile.ZipFile(file, 'r') as zf:
                    zf.extractall(base_path)
                return redirect(url_for("main.index"))
            except Exception as e:
                return render_template("restore.html", error=f"Error restoring backup: {str(e)}")

        return render_template("restore.html", error=None)

    return updates_bp