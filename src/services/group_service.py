"""Service for managing groups and their configurations."""
import glob
import os
import shutil
import stat
import time
from typing import List, Optional

from ..config import load_group_config
from ..group import Group


class GroupService:
    """Service for group management operations."""

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.groups_path = os.path.join(base_path, "groups")

    def discover_groups(self) -> List[Group]:
        """Discover all groups in the groups directory."""
        pattern = os.path.join(self.groups_path, "*")
        folders = [p for p in glob.glob(pattern) if os.path.isdir(p)]
        groups = []

        for folder in folders:
            try:
                groups.append(Group(folder))
            except Exception:
                # Skip folders that don't have valid group.yaml
                pass

        return groups

    def get_group(self, handle: str) -> Optional[Group]:
        """Get a group by handle."""
        groups = self.discover_groups()
        return next((g for g in groups if g.handle == handle), None)

    def create_group(
        self,
        handle: str,
        display_name: str,
        tags: List[str],
        query: Optional[str] = None,
        query_builder: Optional[dict] = None,
        email_recipient: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> Group:
        """Create a new group."""
        if not handle or not handle.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Invalid group handle")

        os.makedirs(self.groups_path, exist_ok=True)
        group_dir = os.path.join(self.groups_path, handle)
        if os.path.exists(group_dir):
            raise ValueError("Group already exists")

        os.makedirs(group_dir, exist_ok=True)

        # Create group.yaml
        config = {
            "handle": handle,
            "display_name": display_name,
            "tags": tags,
        }
        if email_recipient:
            config["email_recipient"] = email_recipient
        if output_dir:
            config["output_dir"] = output_dir
        if query_builder:
            config["query_builder"] = query_builder

        import yaml
        group_cfg_path = os.path.join(group_dir, "group.yaml")
        with open(group_cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)

        # Create override query.sql only if provided.
        if query is not None and query.strip():
            query_path = os.path.join(group_dir, "query.sql")
            with open(query_path, "w", encoding="utf-8") as f:
                f.write(query)

        return Group(group_dir)

    def update_group(
        self,
        group: Group,
        display_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        query: Optional[str] = None,
        query_builder: Optional[dict] = None,
        email_recipient: Optional[str] = None,
        output_dir: Optional[str] = None,
        query_mode: Optional[str] = None,
    ) -> None:
        """Update an existing group."""
        config = group.config.copy()

        if display_name is not None:
            config["display_name"] = display_name
        if tags is not None:
            config["tags"] = tags
        if email_recipient is not None:
            if email_recipient == "":
                config.pop("email_recipient", None)
            else:
                config["email_recipient"] = email_recipient
        if output_dir is not None:
            if output_dir == "":
                config.pop("output_dir", None)
            else:
                config["output_dir"] = output_dir
        if query_builder is not None:
            if query_builder:
                config["query_builder"] = query_builder
            else:
                config.pop("query_builder", None)
        if query_mode is not None:
            if query_mode in {"builder", "manual"}:
                config["query_mode"] = query_mode
            else:
                config.pop("query_mode", None)

        # Save config
        import yaml
        cfg_path = os.path.join(group.folder, "group.yaml")
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)

        # Update override query (empty string removes override file).
        if query is not None:
            if query.strip():
                with open(group.query_file, "w", encoding="utf-8") as f:
                    f.write(query)
            elif os.path.exists(group.query_file):
                os.remove(group.query_file)

    def delete_group(self, group: Group) -> None:
        """Delete a group and all its files."""
        # Handle Windows file permissions
        def _onrmerror(func, path, exc_info):
            try:
                os.chmod(path, stat.S_I_WRITE)
                func(path)
            except Exception:
                pass

        # Walk and chmod for Windows
        for root, dirs, files in os.walk(group.folder):
            for name in files + dirs:
                path = os.path.join(root, name)
                try:
                    os.chmod(path, stat.S_I_WRITE)
                except Exception:
                    pass

        # Try removing up to a few times
        for attempt in range(4):
            try:
                shutil.rmtree(group.folder, onerror=_onrmerror)
                break
            except PermissionError:
                time.sleep(0.5)

        # Final check
        if os.path.exists(group.folder):
            # Fallback cleanup for stubborn file handles on Windows.
            try:
                for root, dirs, files in os.walk(group.folder, topdown=False):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        try:
                            os.chmod(file_path, stat.S_IWRITE)
                        except Exception:
                            pass
                        try:
                            os.remove(file_path)
                        except FileNotFoundError:
                            pass
                    for dirname in dirs:
                        dir_path = os.path.join(root, dirname)
                        try:
                            os.chmod(dir_path, stat.S_IWRITE)
                        except Exception:
                            pass
                        try:
                            os.rmdir(dir_path)
                        except FileNotFoundError:
                            pass
                os.rmdir(group.folder)
            except Exception as exc:
                raise Exception("Failed to delete group folder") from exc

    def get_all_tags(self) -> List[str]:
        """Get all unique tags across all groups."""
        groups = self.discover_groups()
        tags = set()
        for group in groups:
            tags.update(group.tags)
        return sorted(tags)

    def add_tag_to_groups(self, tag_name: str, group_handles: List[str]) -> None:
        """Add a tag to multiple groups."""
        groups = self.discover_groups()
        import yaml

        for group in groups:
            if group.handle in group_handles and tag_name not in group.tags:
                group.config["tags"] = group.config.get("tags", []) + [tag_name]
                cfg_path = os.path.join(group.folder, "group.yaml")
                with open(cfg_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(group.config, f)

    def remove_tag_from_all_groups(self, tag_name: str) -> None:
        """Remove a tag from all groups that have it."""
        groups = self.discover_groups()
        import yaml

        for group in groups:
            if tag_name in group.tags:
                group.config["tags"] = [t for t in group.config.get("tags", []) if t != tag_name]
                cfg_path = os.path.join(group.folder, "group.yaml")
                with open(cfg_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(group.config, f)