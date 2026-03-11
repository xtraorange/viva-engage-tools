"""Service for tracking and reporting lightweight app usage statistics."""
import os
from datetime import datetime
from typing import Dict, Any, List

import yaml


class StatsService:
    """Persist simple usage analytics to config/stats.yaml."""

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.stats_path = os.path.join(base_path, "config", "stats.yaml")

    def _default_stats(self) -> Dict[str, Any]:
        return {
            "total_run_requests": 0,
            "total_reports_generated": 0,
            "total_groups_selected": 0,
            "runs_with_email": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "total_runtime_seconds": 0.0,
            "longest_run_seconds": 0.0,
            "avg_runtime_seconds": 0.0,
            "available_reports_last_seen": 0,
            "last_run_at": None,
            "last_run_duration_seconds": 0.0,
            "per_group_generation_counts": {},
            "reports_file_only_total": 0,
            "reports_email_group_total": 0,
            "reports_email_default_total": 0,
            "reports_email_override_total": 0,
            "runs_with_override_email": 0,
            "per_group_runtime_seconds_total": {},
            "per_group_completed_runs": {},
        }

    def load_stats(self) -> Dict[str, Any]:
        if not os.path.exists(self.stats_path):
            return self._default_stats()

        with open(self.stats_path, "r", encoding="utf-8") as f:
            stats = yaml.safe_load(f) or {}

        defaults = self._default_stats()
        for key, value in defaults.items():
            stats.setdefault(key, value)

        return stats

    def save_stats(self, stats: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.stats_path), exist_ok=True)
        with open(self.stats_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(stats, f, sort_keys=False)

    def reset_stats(self) -> None:
        self.save_stats(self._default_stats())

    def record_available_reports(self, count: int) -> None:
        stats = self.load_stats()
        stats["available_reports_last_seen"] = int(count)
        self.save_stats(stats)

    def record_run_started(
        self,
        selected_groups: List[Any],
        should_email: bool,
        override_email: str | None,
        default_recipient: str | None,
    ) -> None:
        stats = self.load_stats()
        selected_count = len(selected_groups)
        stats["total_run_requests"] += 1
        stats["total_groups_selected"] += int(selected_count)

        group_recipient_count = 0
        default_recipient_count = 0
        file_only_count = selected_count

        if should_email:
            stats["runs_with_email"] += 1

            if override_email:
                stats["runs_with_override_email"] += 1
                stats["reports_email_override_total"] += int(selected_count)
                file_only_count = 0
            else:
                for group in selected_groups:
                    if getattr(group, "email_recipient", None):
                        group_recipient_count += 1
                    elif default_recipient:
                        default_recipient_count += 1

                emailed_total = group_recipient_count + default_recipient_count
                file_only_count = max(selected_count - emailed_total, 0)
                stats["reports_email_group_total"] += int(group_recipient_count)
                stats["reports_email_default_total"] += int(default_recipient_count)

        stats["reports_file_only_total"] += int(max(file_only_count, 0))
        self.save_stats(stats)

    def record_run_completed(
        self,
        selected_handles: List[str],
        generated_files: List[str],
        duration_seconds: float,
        group_run_details: Dict[str, Dict[str, Any]] | None = None,
    ) -> None:
        stats = self.load_stats()

        generated_count = len(generated_files)
        stats["total_reports_generated"] += generated_count
        stats["last_run_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        runtime = float(max(duration_seconds, 0.0))
        stats["last_run_duration_seconds"] = round(runtime, 3)
        stats["total_runtime_seconds"] = round(float(stats["total_runtime_seconds"]) + runtime, 3)
        stats["longest_run_seconds"] = round(max(float(stats["longest_run_seconds"]), runtime), 3)

        if generated_count == len(selected_handles):
            stats["successful_runs"] += 1
        else:
            stats["failed_runs"] += 1

        total_completed_runs = int(stats["successful_runs"]) + int(stats["failed_runs"])
        if total_completed_runs > 0:
            stats["avg_runtime_seconds"] = round(
                float(stats["total_runtime_seconds"]) / total_completed_runs,
                3,
            )

        per_group = stats.get("per_group_generation_counts") or {}
        per_group_runtime_totals = stats.get("per_group_runtime_seconds_total") or {}
        per_group_completed_runs = stats.get("per_group_completed_runs") or {}
        for path in generated_files:
            name = os.path.basename(path)
            if " (" in name:
                handle = name.split(" (", 1)[0]
            else:
                handle = name
            per_group[handle] = int(per_group.get(handle, 0)) + 1

        for handle, detail in (group_run_details or {}).items():
            if not detail.get("success"):
                continue
            duration = float(detail.get("duration_seconds") or 0.0)
            per_group_runtime_totals[handle] = round(float(per_group_runtime_totals.get(handle, 0.0)) + duration, 3)
            per_group_completed_runs[handle] = int(per_group_completed_runs.get(handle, 0)) + 1

        stats["per_group_generation_counts"] = per_group
        stats["per_group_runtime_seconds_total"] = per_group_runtime_totals
        stats["per_group_completed_runs"] = per_group_completed_runs
        self.save_stats(stats)

    def dashboard_metrics(self) -> Dict[str, Any]:
        stats = self.load_stats()
        per_group = stats.get("per_group_generation_counts") or {}
        most_generated_handle = None
        most_generated_count = 0
        if per_group:
            most_generated_handle, most_generated_count = max(per_group.items(), key=lambda x: x[1])

        runtime_totals = stats.get("per_group_runtime_seconds_total") or {}
        runtime_counts = stats.get("per_group_completed_runs") or {}
        per_group_avg_runtime_seconds = {}
        for handle, total in runtime_totals.items():
            count = int(runtime_counts.get(handle, 0))
            if count > 0:
                per_group_avg_runtime_seconds[handle] = round(float(total) / count, 3)

        return {
            "total_run_requests": int(stats.get("total_run_requests", 0)),
            "total_reports_generated": int(stats.get("total_reports_generated", 0)),
            "available_reports_last_seen": int(stats.get("available_reports_last_seen", 0)),
            "runs_with_email": int(stats.get("runs_with_email", 0)),
            "successful_runs": int(stats.get("successful_runs", 0)),
            "failed_runs": int(stats.get("failed_runs", 0)),
            "avg_runtime_seconds": float(stats.get("avg_runtime_seconds", 0.0)),
            "longest_run_seconds": float(stats.get("longest_run_seconds", 0.0)),
            "last_run_duration_seconds": float(stats.get("last_run_duration_seconds", 0.0)),
            "last_run_at": stats.get("last_run_at"),
            "most_generated_handle": most_generated_handle,
            "most_generated_count": int(most_generated_count or 0),
            "per_group_generation_counts": per_group,
            "reports_file_only_total": int(stats.get("reports_file_only_total", 0)),
            "reports_email_group_total": int(stats.get("reports_email_group_total", 0)),
            "reports_email_default_total": int(stats.get("reports_email_default_total", 0)),
            "reports_email_override_total": int(stats.get("reports_email_override_total", 0)),
            "runs_with_override_email": int(stats.get("runs_with_override_email", 0)),
            "per_group_avg_runtime_seconds": per_group_avg_runtime_seconds,
        }
