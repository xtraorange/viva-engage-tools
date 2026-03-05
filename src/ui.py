"""Web UI for managing configuration and running reports."""
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import yaml
import shutil
import zipfile
from io import BytesIO
from datetime import datetime, timedelta
import json
import urllib.request
import subprocess
import sys
import webbrowser
import time
import logging

from .generate_reports import discover_groups, process_group, _send_override_email
from .config import load_general_config
from .db import DatabaseExecutor, ProgressTracker
from .group import Group
from .email_template import load_email_template, load_override_email_template
from .sql_builder import generate_safe_hierarchy_sql


def load_version_config():
    """Load version and repository info from config/version.yaml."""
    base = os.getcwd()
    version_path = os.path.join(base, "config", "version.yaml")
    if os.path.exists(version_path):
        with open(version_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
            return config.get("version", "0.2.0"), config.get("repository", "xtraorange/jampy-engage")
    return "0.2.0", "xtraorange/jampy-engage"


# Load version and repository from config
__version__, GITHUB_REPO = load_version_config()
CHECK_INTERVAL_SECONDS = 24 * 60 * 60  # check GitHub no more than once per day


def create_app():
    base = os.getcwd()
    # ensure templates folder is located at workspace root
    app = Flask(__name__, template_folder=os.path.join(base, "templates"))
    general_path = os.path.join(base, "config", "general.yaml")

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

    def load_general():
        return load_general_config(general_path)

    def save_general(cfg: dict):
        with open(general_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f)

    def load_groups():
        return discover_groups(base)

    def save_group(group: Group, data: dict):
        cfg_path = os.path.join(group.folder, "group.yaml")
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

    def _parse_version(v: str):
        return tuple(int(x) for x in v.lstrip('v').split('.') if x.isdigit())

    def _is_newer(latest: str, current: str) -> bool:
        try:
            return _parse_version(latest) > _parse_version(current)
        except Exception:
            return latest != current

    def check_for_updates(cfg: dict) -> dict:
        """Always fetch latest version from GitHub and return update info.
        
        Stores: {version: X.Y.Z, body: release notes, last_check: timestamp}
        """
        now = datetime.now()
        info = cfg.get("update_info") or {}

        # migrate legacy top-level timestamp if present
        if "last_update_check" in cfg:
            info.setdefault("last_check", cfg.pop("last_update_check"))
            cfg["update_info"] = info
            save_general(cfg)

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
        save_general(cfg)
        
        return info

    @app.route("/settings", methods=["GET", "POST"])
    def index():
        cfg = load_general()
        # settings page no longer checks updates directly
        if request.method == "POST":
            # update general config based on form fields
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
            save_general(cfg)
            return redirect(url_for("index"))
        groups = load_groups()
        return render_template("index.html", config=cfg, groups=groups,
                               updating=app.config.get("updating"),
                               update_error=app.config.get("update_error"))

    @app.route("/updates", methods=["GET", "POST"])
    def updates():
        cfg = load_general()
        # if user clicked "check again", clear the old info first
        if request.args.get("check") == "true":
            cfg["update_info"] = {}
            save_general(cfg)
        update_info = check_for_updates(cfg)
        update_available = False
        if update_info and update_info.get("version"):
            update_available = _is_newer(update_info.get("version"), __version__)
        if request.method == "POST":
            # trigger manual update via perform_update
            return redirect(url_for("perform_update"))
        return render_template("updates.html",
                               current_version=__version__,
                               update_info=update_info,
                               update_available=update_available,
                               updating=app.config.get("updating"),
                               update_status=app.config.get("update_status"),
                               update_error=app.config.get("update_error"))

    @app.route("/update", methods=["GET", "POST"])
    def perform_update():
        if app.config.get("updating"):
            return redirect(url_for("index"))
        app.config["updating"] = True
        app.config["update_status"] = "Starting update..."
        app.config["update_output"] = []
        def updater():
            try:
                # stash any local changes (including config) so pull can succeed
                app.config["update_status"] = "Stashing local modifications..."
                app.config["update_output"].append("$ git stash push -u -m jampy-update")
                st = subprocess.run(["git", "stash", "push", "-u", "-m", "jampy-update"], cwd=base, capture_output=True, text=True, timeout=30)
                if st.stdout:
                    app.config["update_output"].append(st.stdout.strip())
                if st.stderr:
                    app.config["update_output"].append(st.stderr.strip())
                
                app.config["update_status"] = "Fetching latest code..."
                app.config["update_output"].append("$ git pull --ff-only")
                result = subprocess.run(["git", "pull", "--ff-only"], cwd=base, capture_output=True, text=True, timeout=60, check=True)
                if result.stdout:
                    app.config["update_output"].append(result.stdout.strip())
                if result.stderr:
                    app.config["update_output"].append(result.stderr.strip())
                
                # restore stash
                app.config["update_status"] = "Restoring local changes..."
                app.config["update_output"].append("$ git stash pop")
                pop = subprocess.run(["git", "stash", "pop"], cwd=base, capture_output=True, text=True, timeout=30)
                if pop.stdout:
                    app.config["update_output"].append(pop.stdout.strip())
                if pop.stderr:
                    app.config["update_output"].append(pop.stderr.strip())
                
                app.config["update_status"] = "Installing dependencies..."
                app.config["update_output"].append(f"$ {sys.executable} -m pip install -r requirements.txt")
                result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=base, capture_output=True, text=True, timeout=120, check=True)
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
        return redirect(url_for("index"))
    
    @app.route("/force-update", methods=["POST"])
    def force_update():
        """Force update regardless of version check."""
        if app.config.get("updating"):
            return redirect(url_for("index"))
        app.config["updating"] = True
        app.config["update_status"] = "Starting force update..."
        app.config["update_output"] = []
        def updater():
            try:
                # stash any local changes (including config) so pull can succeed
                app.config["update_status"] = "Stashing local modifications..."
                app.config["update_output"].append("$ git stash push -u -m jampy-update")
                st = subprocess.run(["git", "stash", "push", "-u", "-m", "jampy-update"], cwd=base, capture_output=True, text=True, timeout=30)
                if st.stdout:
                    app.config["update_output"].append(st.stdout.strip())
                if st.stderr:
                    app.config["update_output"].append(st.stderr.strip())
                
                app.config["update_status"] = "Fetching latest code..."
                app.config["update_output"].append("$ git pull --ff-only")
                result = subprocess.run(["git", "pull", "--ff-only"], cwd=base, capture_output=True, text=True, timeout=60, check=True)
                if result.stdout:
                    app.config["update_output"].append(result.stdout.strip())
                if result.stderr:
                    app.config["update_output"].append(result.stderr.strip())
                
                # restore stash
                app.config["update_status"] = "Restoring local changes..."
                app.config["update_output"].append("$ git stash pop")
                pop = subprocess.run(["git", "stash", "pop"], cwd=base, capture_output=True, text=True, timeout=30)
                if pop.stdout:
                    app.config["update_output"].append(pop.stdout.strip())
                if pop.stderr:
                    app.config["update_output"].append(pop.stderr.strip())
                
                app.config["update_status"] = "Installing dependencies..."
                app.config["update_output"].append(f"$ {sys.executable} -m pip install -r requirements.txt")
                result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=base, capture_output=True, text=True, timeout=120, check=True)
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
        return redirect(url_for("index"))
    
    @app.route("/api/update-status")
    def update_status_api():
        """Return current update status and output for live polling"""
        return jsonify({
            "updating": app.config.get("updating", False),
            "status": app.config.get("update_status", ""),
            "output": app.config.get("update_output", []),
            "error": app.config.get("update_error", "")
        })

    @app.route("/restart", methods=["POST"])
    def restart():
        """Signal the launcher to restart the server and then shut down this process.

        We create a small flag file so the `start.bat` loop knows to relaunch.
        """
        # set flag
        try:
            with open(os.path.join(base, "restart.flag"), "w") as f:
                f.write("restart")
        except Exception:
            pass

        func = request.environ.get('werkzeug.server.shutdown')
        if func:
            threading.Thread(target=func).start()
        else:
            threading.Timer(0.5, lambda: os._exit(0)).start()
        return "Shutting down", 200

    @app.route("/groups")
    def groups():
        if app.config.get("updating"):
            return "Update in progress, please wait and refresh after restart", 503
        groups = load_groups()
        return render_template("groups.html", groups=groups)

    @app.route("/tags")
    def tags():
        if app.config.get("updating"):
            return "Update in progress, please wait and refresh after restart", 503
        groups = load_groups()
        all_tags = set()
        tag_groups = {}
        for g in groups:
            for t in g.tags:
                all_tags.add(t)
                if t not in tag_groups:
                    tag_groups[t] = []
                tag_groups[t].append(g.handle)
        return render_template("tags.html", tags=sorted(all_tags), tag_groups=tag_groups)

    @app.route("/group/<handle>", methods=["GET", "POST"])
    def edit_group(handle):
        if app.config.get("updating"):
            return "Update in progress, please wait and refresh after restart", 503
        groups = load_groups()
        group = next((g for g in groups if g.handle == handle), None)
        if group is None:
            return "Group not found", 404
        cfg = group.config.copy()
        if request.method == "POST":
            # update properties
            cfg["display_name"] = request.form.get("display_name", cfg.get("display_name"))
            tags = request.form.get("tags", "")
            cfg["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
            cfg["email_recipient"] = request.form.get("email_recipient", cfg.get("email_recipient"))
            outdir = request.form.get("output_dir", "")
            if outdir:
                cfg["output_dir"] = outdir
            # update query if provided
            query = request.form.get("query", "").strip()
            if query:
                with open(group.query_file, "w", encoding="utf-8") as f:
                    f.write(query)
            save_group(group, cfg)
            return redirect(url_for("groups"))
        # prepare tag string and load query
        cfg["tags_str"] = ",".join(cfg.get("tags", []))
        cfg["query"] = group.read_query()
        return render_template("group.html", group=group, config=cfg)

    @app.route("/group/new", methods=["GET", "POST"])
    def new_group():
        if request.method == "POST":
            handle = request.form.get("handle", "").strip()
            if not handle or not handle.replace("_", "").replace("-", "").isalnum():
                return "Invalid group handle", 400
            
            # create group directory
            group_dir = os.path.join(base, "groups", handle)
            if os.path.exists(group_dir):
                return "Group already exists", 400
            
            os.makedirs(group_dir, exist_ok=True)
            
            # create group.yaml
            cfg = {
                "handle": handle,
                "display_name": request.form.get("display_name", handle),
                "tags": [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()],
            }
            email_recipient = request.form.get("email_recipient", "").strip()
            if email_recipient:
                cfg["email_recipient"] = email_recipient
            
            group_cfg_path = os.path.join(group_dir, "group.yaml")
            with open(group_cfg_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f)
            
            # create query.sql
            query = request.form.get("query", "SELECT * FROM dual;").strip()
            query_path = os.path.join(group_dir, "query.sql")
            with open(query_path, "w", encoding="utf-8") as f:
                f.write(query)
            
            return redirect(url_for("groups"))
        
        return render_template("group_new.html")

    @app.route("/", methods=["GET", "POST"])
    def generate():
        if app.config.get("updating"):
            return "Update in progress, please wait and refresh after restart", 503
        groups = load_groups()
        cfg = load_general()
        if request.method == "POST":
            selected_handles = request.form.getlist("groups")
            selected = [g for g in groups if g.handle in selected_handles]
            tag_sel = request.form.getlist("tags")
            for t in tag_sel:
                for g in groups:
                    if t in g.tags and g not in selected:
                        selected.append(g)
            should_email = request.form.get("email") == "on"
            override = request.form.get("override_email") or None
            tracker = start_jobs(selected, should_email, override)
            app.config["tracker"] = tracker
            return redirect(url_for("status"))
        tags = set()
        for g in groups:
            tags.update(g.tags)
        tags = sorted(tags)
        return render_template("generate.html", groups=groups, tags=tags)

    @app.route("/status")
    def status():
        if app.config.get("updating"):
            return "Update in progress, please wait and refresh after restart", 503
        tracker = app.config.get("tracker")
        if not tracker:
            return redirect(url_for("generate"))
        return render_template("status.html", tracker=tracker)

    @app.route("/api/status")
    def api_status():
        tracker = app.config.get("tracker")
        if not tracker:
            return jsonify(error="No job running")
        return jsonify(status=tracker.status, done=tracker.done, total=tracker.total)

    @app.route("/email-templates", methods=["GET", "POST"])
    def email_templates():
        templates_path = os.path.join(base, "config")
        std_template = load_email_template(templates_path)
        override_template = load_override_email_template(templates_path)
        
        if request.method == "POST":
            template_type = request.form.get("template_type")
            subject = request.form.get("subject")
            body = request.form.get("body")
            
            if template_type == "standard":
                filepath = os.path.join(templates_path, "email_template.yaml")
            else:
                filepath = os.path.join(templates_path, "email_template_override.yaml")
            
            with open(filepath, "w", encoding="utf-8") as f:
                yaml.safe_dump({"subject": subject, "body": body}, f)
            
            return redirect(url_for("email_templates"))
        
        return render_template("email_templates.html", 
                             std_template=std_template, 
                             override_template=override_template)

    @app.route("/group/<handle>/delete", methods=["POST"])
    def delete_group(handle):
        groups = load_groups()
        group = next((g for g in groups if g.handle == handle), None)
        if group is None:
            return "Group not found", 404
        
        try:
            # For Windows, remove read-only attributes first and handle file locks
            import stat, time
            def _onrmerror(func, path, exc_info):
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass
            # walk and chmod
            for root, dirs, files in os.walk(group.folder):
                for name in files + dirs:
                    path = os.path.join(root, name)
                    try:
                        os.chmod(path, stat.S_IWRITE)
                    except Exception:
                        pass

            # try removing up to a few times
            for attempt in range(4):
                try:
                    shutil.rmtree(group.folder, onerror=_onrmerror)
                    break
                except PermissionError:
                    time.sleep(0.5)
            # final check
            if os.path.exists(group.folder):
                return f"Error deleting group: folder still exists", 500
            return redirect(url_for("groups"))
        except Exception as e:
            return f"Error deleting group: {str(e)}", 500

    @app.route("/tag/<tag>/delete", methods=["POST"])
    def delete_tag(tag):
        groups = load_groups()
        for group in groups:
            if tag in group.tags:
                group.config["tags"] = [t for t in group.config.get("tags", []) if t != tag]
                save_group(group, group.config)
        return redirect(url_for("tags"))

    @app.route("/tag/new", methods=["GET", "POST"])
    def new_tag():
        groups = load_groups()
        if request.method == "POST":
            tag_name = request.form.get("tag_name", "").strip()
            if not tag_name:
                return render_template("tag_new.html", groups=groups, error="Tag name is required")
            
            selected_groups = request.form.getlist("groups")
            for group in groups:
                if group.handle in selected_groups:
                    if tag_name not in group.tags:
                        group.config["tags"] = group.config.get("tags", []) + [tag_name]
                        save_group(group, group.config)
            
            return redirect(url_for("tags"))
        
        return render_template("tag_new.html", groups=groups, error=None)

    @app.route("/query-builder", methods=["GET"])
    def query_builder():
        """UI for building hierarchy queries."""
        return render_template("query_builder.html")

    @app.route("/api/search-employees", methods=["GET"])
    def search_employees():
        """Typeahead search for employees."""
        cfg = load_general()
        query = request.args.get("q", "").strip()
        
        if not query or len(query) < 2:
            return jsonify([])
        
        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            
            # Search across ID, name, and username
            sql = f"""
            SELECT ID, FIRST_NAME, LAST_NAME, USERNAME FROM omsadm.employee_mv 
            WHERE (ID LIKE '%{query}%' OR FIRST_NAME LIKE '%{query}%' OR LAST_NAME LIKE '%{query}%' OR USERNAME LIKE '%{query}%')
            AND Terminated IS NULL 
            ORDER BY FIRST_NAME, LAST_NAME
            """
            
            results = executor.execute_query(sql)
            items = [
                {"id": row[0], "first_name": row[1], "last_name": row[2], "username": row[3]}
                for row in results[:20]  # Limit results on Python side
            ]
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/search-job-titles", methods=["GET"])
    def search_job_titles():
        """Typeahead search for job titles."""
        cfg = load_general()
        query = request.args.get("q", "").strip()
        
        if not query or len(query) < 1:
            return jsonify([])
        
        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT JOB_TITLE FROM omsadm.employee_mv WHERE JOB_TITLE LIKE '%{query}%' AND Terminated IS NULL ORDER BY JOB_TITLE"
            results = executor.execute_query(sql)
            items = [{"value": row[0]} for row in results[:20]]
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/search-bu-codes", methods=["GET"])
    def search_bu_codes():
        """Typeahead search for business unit codes."""
        cfg = load_general()
        query = request.args.get("q", "").strip()
        
        if not query or len(query) < 1:
            return jsonify([])
        
        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT BU_CODE FROM omsadm.employee_mv WHERE BU_CODE LIKE '%{query}%' AND Terminated IS NULL ORDER BY BU_CODE"
            results = executor.execute_query(sql)
            items = [{"value": row[0]} for row in results[:20]]
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/search-companies", methods=["GET"])
    def search_companies():
        """Typeahead search for companies/countries."""
        cfg = load_general()
        query = request.args.get("q", "").strip()
        
        if not query or len(query) < 1:
            return jsonify([])
        
        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT COMPANY FROM omsadm.employee_mv WHERE COMPANY LIKE '%{query}%' AND Terminated IS NULL ORDER BY COMPANY"
            results = executor.execute_query(sql)
            items = [{"value": row[0]} for row in results[:20]]
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/search-tree-branches", methods=["GET"])
    def search_tree_branches():
        """Typeahead search for tree branches."""
        cfg = load_general()
        query = request.args.get("q", "").strip()
        
        if not query or len(query) < 1:
            return jsonify([])
        
        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT TREE_BRANCH FROM omsadm.employee_mv WHERE TREE_BRANCH LIKE '%{query}%' AND Terminated IS NULL ORDER BY TREE_BRANCH"
            results = executor.execute_query(sql)
            items = [{"value": row[0]} for row in results[:20]]
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/generate-builder-sql", methods=["POST"])
    def generate_builder_sql():
        """Generate SQL from builder parameters."""
        try:
            data = request.get_json()
            
            mode = data.get("mode")
            person_id = data.get("person_id")
            person_first_name = data.get("person_first_name")
            person_last_name = data.get("person_last_name")
            person_username = data.get("person_username")
            attributes_job_title = data.get("attributes_job_title")
            attributes_bu_code = data.get("attributes_bu_code")
            attributes_company = data.get("attributes_company")
            attributes_tree_branch = data.get("attributes_tree_branch")
            filter_job_titles = data.get("filter_job_titles", [])
            filter_bu_codes = data.get("filter_bu_codes", [])
            filter_companies = data.get("filter_companies", [])
            filter_tree_branches = data.get("filter_tree_branches", [])
            filter_full_part_time = data.get("filter_full_part_time")
            exclude_root = data.get("exclude_root", False)
            
            sql = generate_safe_hierarchy_sql(
                mode=mode,
                person_id=person_id,
                person_first_name=person_first_name,
                person_last_name=person_last_name,
                person_username=person_username,
                attributes_job_title=attributes_job_title,
                attributes_bu_code=attributes_bu_code,
                attributes_company=attributes_company,
                attributes_tree_branch=attributes_tree_branch,
                filter_job_titles=filter_job_titles,
                filter_bu_codes=filter_bu_codes,
                filter_companies=filter_companies,
                filter_tree_branches=filter_tree_branches,
                filter_full_part_time=filter_full_part_time,
                exclude_root=exclude_root,
            )
            
            return jsonify({"sql": sql})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/test-query", methods=["POST"])
    def test_query():
        """Test a query and return record count."""
        try:
            cfg = load_general()
            data = request.get_json()
            sql = data.get("sql", "").strip()
            
            if not sql:
                return jsonify({"error": "No SQL provided"}), 400
            
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            # Count records
            count_sql = f"SELECT COUNT(*) FROM ({sql})"
            result = executor.execute_query(count_sql)
            count = result[0][0] if result else 0
            executor.close()
            
            return jsonify({"count": count})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/backup")
    def backup():
        """Create a zip backup of all configuration and groups."""
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add config files
            config_path = os.path.join(base, "config")
            for filename in os.listdir(config_path):
                if filename.endswith((".yaml", ".yml")):
                    file_path = os.path.join(config_path, filename)
                    zf.write(file_path, os.path.join("config", filename))
            
            # Add groups
            groups_path = os.path.join(base, "groups")
            if os.path.exists(groups_path):
                for root, dirs, files in os.walk(groups_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, base)
                        zf.write(file_path, arcname)
        
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'jampy-backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'
        )

    @app.route("/restore", methods=["GET", "POST"])
    def restore():
        if request.method == "POST":
            if 'file' not in request.files:
                return render_template("restore.html", error="No file provided")
            
            file = request.files['file']
            if not file.filename.endswith('.zip'):
                return render_template("restore.html", error="File must be a zip archive")
            
            try:
                with zipfile.ZipFile(file, 'r') as zf:
                    zf.extractall(base)
                return redirect(url_for("index"))
            except Exception as e:
                return render_template("restore.html", error=f"Error restoring backup: {str(e)}")
        
        return render_template("restore.html", error=None)


    def start_jobs(selected, should_email, override_email):
        general_cfg = load_general()
        executor = DatabaseExecutor(general_cfg.get("oracle_tns"))
        max_workers = general_cfg.get("max_workers") or os.cpu_count() or 4
        tracker = ProgressTracker(len(selected))
        csv_files = []

        def task():
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = []
                for idx, g in enumerate(selected, start=1):
                    futures.append(
                        pool.submit(
                            process_group,
                            g,
                            general_cfg,
                            executor,
                            tracker,
                            should_email=should_email,
                            override_email=override_email,
                            job_num=idx,
                            job_total=len(selected),
                        )
                    )
                for fut in futures:
                    res = fut.result()
                    if override_email and res:
                        csv_files.append(res)
            try:
                executor.close()
            except Exception:
                pass
            if override_email and csv_files:
                date_str = datetime.now().strftime("%y-%m-%d")
                groups_list = "\n".join([os.path.basename(f) for f in csv_files])
                _send_override_email(override_email, general_cfg, csv_files, groups_list, date_str, len(selected))

        threading.Thread(target=task, daemon=True).start()
        return tracker

    @app.route("/api/pick-folder")
    def pick_folder():
        """Open a native folder picker dialog and return the selected path."""
        try:
            import tkinter as tk
            from tkinter.filedialog import askdirectory
            
            # Create a hidden root window
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            # Open folder picker
            folder = askdirectory(title="Select a folder")
            root.destroy()
            
            if folder:
                return jsonify(path=folder)
            else:
                # user cancelled; not an error
                return jsonify(cancelled=True)
        except ImportError:
            return jsonify(error="tkinter not installed"), 200
        except Exception as e:
            # catch tkinter/display errors and return gracefully
            return jsonify(error=str(e)), 200

    return app

if __name__ == "__main__":
    """Run the Flask application."""
    app = create_app()
    
    # Open browser after a brief delay to let the server start
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:5000")
    
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    app.run(host="0.0.0.0", port=5000, debug=False)