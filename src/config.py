import os
import yaml


def load_general_config(path: str) -> dict:
    cfg = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    # provide defaults
    cfg.setdefault("output_dir", os.path.join(os.getcwd(), "output"))
    cfg.setdefault("max_workers", None)
    cfg.setdefault("email_method", "smtp")
    cfg.setdefault("outlook_auto_send", False)
    cfg.setdefault("ui_port", 5000)
    return cfg


def load_group_config(folder: str) -> dict:
    cfg_path = os.path.join(folder, "group.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # ensure handle matches folder name or not?
    cfg.setdefault("handle", os.path.basename(folder))
    cfg.setdefault("display_name", cfg.get("handle"))
    cfg.setdefault("tags", [])
    return cfg
