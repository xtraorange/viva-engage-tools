import os
from typing import List

from .config import load_group_config
from .sql_builder import generate_safe_hierarchy_sql


class Group:
    def __init__(self, folder: str):
        self.folder = folder
        self.config = load_group_config(folder)
        self.handle = self.config["handle"]
        self.display_name = self.config.get("display_name")
        self.tags = set(self.config.get("tags", []))
        self.query_file = os.path.join(folder, "query.sql")

    def has_override_query(self) -> bool:
        if not os.path.exists(self.query_file):
            return False
        try:
            return bool(self.read_override_query().strip())
        except Exception:
            return False

    def read_override_query(self) -> str:
        if not os.path.exists(self.query_file):
            return ""
        with open(self.query_file, "r", encoding="utf-8") as f:
            return f.read()

    def _builder_payload_for_sql(self) -> dict:
        payload = self.config.get("query_builder") or {}
        allowed = {
            "mode",
            "persons",
            "person_id",
            "person_first_name",
            "person_last_name",
            "person_username",
            "selected_person_details",
            "attributes_job_title",
            "attributes_job_title_display",
            "attributes_job_code",
            "attributes_job_title_text",
            "attributes_bu_code",
            "attributes_company",
            "attributes_tree_branch",
            "attributes_department_id",
            "filter_job_titles",
            "filter_job_codes",
            "filter_job_titles_display",
            "filter_bu_codes",
            "filter_companies",
            "filter_tree_branches",
            "filter_department_ids",
            "filter_full_part_time",
            "exclude_root",
        }
        return {k: v for k, v in payload.items() if k in allowed}

    def read_query(self) -> str:
        # Manual override takes precedence if present.
        override = self.read_override_query().strip()
        if override:
            return override

        payload = self._builder_payload_for_sql()
        if payload:
            return generate_safe_hierarchy_sql(**payload)

        raise ValueError(
            f"Group '{self.handle}' has no query override and no query_builder parameters"
        )

    def output_path(self, base_output: str) -> str:
        # groups can override their own output_dir in config
        override = self.config.get("output_dir")
        if override:
            return override
        return os.path.join(base_output, self.handle)

    def matches(self, names: List[str] = None, tags: List[str] = None) -> bool:
        if names:
            if self.handle in names:
                return True
        if tags:
            if self.tags.intersection(tags):
                return True
        return False
