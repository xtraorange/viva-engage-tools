"""Service for managing application configuration."""
import os
import yaml
from typing import Dict, Any


class ConfigService:
    """Service for configuration management."""

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.config_path = os.path.join(base_path, "config", "general.yaml")

    def load_general_config(self) -> Dict[str, Any]:
        """Load general configuration with defaults."""
        return self._load_config_with_defaults(self.config_path, {
            "output_dir": os.path.join(self.base_path, "output"),
            "max_workers": None,
            "email_method": "smtp",
            "outlook_auto_send": False,
            "ui_port": 5000,
        })

    def save_general_config(self, config: Dict[str, Any]) -> None:
        """Save general configuration."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)

    def update_general_config(self, updates: Dict[str, Any]) -> None:
        """Update specific configuration values."""
        config = self.load_general_config()
        config.update(updates)
        self.save_general_config(config)

    def load_email_template_config(self, template_type: str = "standard") -> Dict[str, Any]:
        """Load email template configuration."""
        if template_type == "override":
            path = os.path.join(self.base_path, "config", "email_template_override.yaml")
            defaults = {
                "subject": "Viva Engage Member Lists - {date}",
                "body": "Please find attached the member lists for the following communities:\n\n{groups_list}\n\nTotal Reports: {count}\n\nGenerated on {date}",
            }
        else:
            path = os.path.join(self.base_path, "config", "email_template.yaml")
            defaults = {
                "subject": "Viva Engage Member List: {group_name}",
                "body": "Please find attached the member list for {group_name}.",
            }

        return self._load_config_with_defaults(path, defaults)

    def save_email_template_config(self, template_type: str, config: Dict[str, Any]) -> None:
        """Save email template configuration."""
        filename = "email_template_override.yaml" if template_type == "override" else "email_template.yaml"
        path = os.path.join(self.base_path, "config", filename)

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)

    def load_version_config(self) -> tuple:
        """Load version and repository info."""
        version_path = os.path.join(self.base_path, "config", "version.yaml")
        if os.path.exists(version_path):
            with open(version_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                return config.get("version", "0.2.0"), config.get("repository", "xtraorange/jampy-engage")
        return "0.2.0", "xtraorange/jampy-engage"

    def _load_config_with_defaults(self, path: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Load YAML config file with default values."""
        if not os.path.exists(path):
            return defaults.copy()

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        # Apply defaults for missing keys
        for key, default_value in defaults.items():
            config.setdefault(key, default_value)

        return config