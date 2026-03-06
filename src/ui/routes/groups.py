"""Group management routes."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
import os

from ...services.group_service import GroupService
from ...utils.validation import validate_group_handle
from ...utils.file_utils import safe_delete_directory

groups_bp = Blueprint('groups', __name__)


def init_groups_routes(app, base_path: str):
    """Initialize group routes with dependencies."""
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
        if group is None:
            return "Group not found", 404

        if request.method == "POST":
            # Update group configuration
            display_name = request.form.get("display_name", "").strip()
            tags_str = request.form.get("tags", "").strip()
            email_recipient = request.form.get("email_recipient", "").strip()
            output_dir = request.form.get("output_dir", "").strip()
            query = request.form.get("query", "").strip()

            tags = [t.strip() for t in tags_str.split(",") if t.strip()]

            group_service.update_group(
                group=group,
                display_name=display_name,
                tags=tags,
                query=query,
                email_recipient=email_recipient or None,
                output_dir=output_dir or None
            )

            return redirect(url_for("groups.groups"))

        # Prepare data for template
        cfg = group.config.copy()
        cfg["tags_str"] = ",".join(cfg.get("tags", []))
        cfg["query"] = group.read_query()

        return render_template("group.html", group=group, config=cfg)

    @groups_bp.route("/group/new", methods=["GET", "POST"])
    def new_group():
        """Create a new group."""
        if request.method == "POST":
            handle = request.form.get("handle", "").strip()
            if not validate_group_handle(handle):
                return render_template("group_new.html", error="Invalid group handle")

            display_name = request.form.get("display_name", handle).strip()
            tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
            email_recipient = request.form.get("email_recipient", "").strip() or None
            query = request.form.get("query", "SELECT * FROM dual;").strip()

            try:
                group_service.create_group(
                    handle=handle,
                    display_name=display_name,
                    tags=tags,
                    query=query,
                    email_recipient=email_recipient
                )
                return redirect(url_for("groups.groups"))
            except ValueError as e:
                return render_template("group_new.html", error=str(e))

        return render_template("group_new.html", error=None)

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

    return groups_bp