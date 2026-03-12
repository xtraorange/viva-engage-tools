"""Group management routes."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
import json
import os

from ...services.group_service import GroupService
from ...utils.validation import validate_group_handle
from ...utils.file_utils import safe_delete_directory

def init_groups_routes(app, base_path: str):
    """Initialize group routes with dependencies."""
    groups_bp = Blueprint('groups', __name__)
    group_service = GroupService(base_path)

    @groups_bp.route("/groups")
    def groups():
        """List all groups."""
        groups = group_service.discover_groups()
        return render_template("groups.html", groups=groups)

    @groups_bp.route("/group/<handle>", methods=["GET", "POST"])
    def edit_group(handle):
        """Edit a group."""
        group = group_service.get_group(handle)
        all_tags = group_service.get_all_tags()
        if group is None:
            return "Group not found", 404

        def _build_cfg():
            cfg = group.config.copy()
            cfg["tags_str"] = ",".join(cfg.get("tags", []))
            cfg["has_override_query"] = group.has_override_query()
            cfg["override_query"] = group.read_override_query() if cfg["has_override_query"] else ""
            cfg["query_builder"] = cfg.get("query_builder")
            cfg["query_builder_json"] = json.dumps(cfg.get("query_builder") or {})
            cfg["query_mode"] = cfg.get("query_mode") or ("manual" if cfg["has_override_query"] else "builder")
            return cfg

        if request.method == "POST":
            is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
            save_scope = request.form.get("save_scope", "all").strip().lower()

            # Update group configuration
            display_name = request.form.get("display_name", "").strip()
            tags_str = request.form.get("tags", "").strip()
            email_recipient = request.form.get("email_recipient", "").strip()
            output_dir = request.form.get("output_dir", "").strip()
            query = request.form.get("query", "").strip()
            query_builder_raw = request.form.get("query_builder_json", "").strip()
            query_mode = request.form.get("query_mode", "").strip()

            query_builder = None
            if query_builder_raw:
                try:
                    query_builder = json.loads(query_builder_raw)
                except json.JSONDecodeError:
                    query_builder = None

            if save_scope == "query_mode":
                group_service.update_group(group=group, query_mode=query_mode)
                group = group_service.get_group(handle)
                cfg = _build_cfg()
                return jsonify(ok=True, config=cfg)

            if save_scope == "settings":
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                group_service.update_group(
                    group=group,
                    display_name=display_name,
                    tags=tags,
                    email_recipient=email_recipient or None,
                    output_dir=output_dir or None,
                    query_mode=query_mode,
                )
            elif save_scope == "query":
                if not query and not query_builder:
                    if is_ajax:
                        return jsonify(ok=False, error="Save either Query Builder parameters or an override SQL script."), 400
                    cfg = _build_cfg()
                    return render_template("group.html", group=group, config=cfg, error="Save either Query Builder parameters or an override SQL script.", all_tags=all_tags, edit_mode=True)
                group_service.update_group(
                    group=group,
                    query=query,
                    query_builder=query_builder,
                    query_mode=query_mode,
                )
            else:
                if not query and not query_builder:
                    if is_ajax:
                        return jsonify(ok=False, error="Save either Query Builder parameters or an override SQL script."), 400
                    cfg = _build_cfg()
                    return render_template("group.html", group=group, config=cfg, error="Save either Query Builder parameters or an override SQL script.", all_tags=all_tags, edit_mode=True)
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                group_service.update_group(
                    group=group,
                    display_name=display_name,
                    tags=tags,
                    query=query,
                    query_builder=query_builder,
                    email_recipient=email_recipient or None,
                    output_dir=output_dir or None,
                    query_mode=query_mode,
                )

            group = group_service.get_group(handle)
            cfg = _build_cfg()
            if is_ajax:
                return jsonify(ok=True, config=cfg)
            return render_template("group.html", group=group, config=cfg, all_tags=all_tags, edit_mode=False)

        # Prepare data for template
        cfg = _build_cfg()

        return render_template("group.html", group=group, config=cfg, all_tags=all_tags, edit_mode=False)

    @groups_bp.route("/group/new", methods=["GET", "POST"])
    def new_group():
        """Create a new group (settings first), then redirect to edit page."""
        all_tags = group_service.get_all_tags()
        form_data = {
            "handle": "",
            "display_name": "",
            "tags": "",
            "email_recipient": "",
            "output_dir": "",
        }
        if request.method == "POST":
            handle = request.form.get("handle", "").strip()
            display_name = request.form.get("display_name", handle).strip()
            tags_raw = request.form.get("tags", "").strip()
            email_recipient = request.form.get("email_recipient", "").strip()
            output_dir = request.form.get("output_dir", "").strip()

            form_data = {
                "handle": handle,
                "display_name": display_name,
                "tags": tags_raw,
                "email_recipient": email_recipient,
                "output_dir": output_dir,
            }

            if not validate_group_handle(handle):
                return render_template("group_create.html", error="Invalid group handle", all_tags=all_tags, form_data=form_data)

            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

            try:
                group_service.create_group(
                    handle=handle,
                    display_name=display_name,
                    tags=tags,
                    email_recipient=email_recipient or None,
                    output_dir=output_dir or None,
                )
                return redirect(url_for("groups.edit_group", handle=handle))
            except ValueError as e:
                return render_template("group_create.html", error=str(e), all_tags=all_tags, form_data=form_data)

        return render_template("group_create.html", error=None, all_tags=all_tags, form_data=form_data)

    @groups_bp.route("/group/<handle>/delete", methods=["POST"])
    def delete_group(handle):
        """Delete a group."""
        group = group_service.get_group(handle)
        if group is None:
            return "Group not found", 404

        try:
            group_service.delete_group(group)
            return redirect(url_for("groups.groups"))
        except Exception as e:
            return f"Error deleting group: {str(e)}", 500

    @groups_bp.route("/group/<handle>/remove-override", methods=["POST"])
    def remove_override(handle):
        """Remove override query.sql so group uses saved query builder params."""
        group = group_service.get_group(handle)
        if group is None:
            return "Group not found", 404

        group_service.update_group(group=group, query="")
        return redirect(url_for("groups.edit_group", handle=handle))

    return groups_bp