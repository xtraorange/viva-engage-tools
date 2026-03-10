"""Core report generation service."""
import os
from datetime import datetime
from typing import List, Optional

from ..config import load_general_config
from ..db import DatabaseExecutor, ProgressTracker
from ..group import Group
from .email_service import EmailService


class ReportService:
    """Service for generating reports and managing the processing workflow."""

    def __init__(self, config: dict):
        self.config = config
        self.email_service = EmailService(config)

    def process_groups(
        self,
        groups: List[Group],
        should_email: bool = False,
        override_email: Optional[str] = None,
        progress_callback: Optional[callable] = None,
        tracker: Optional[ProgressTracker] = None
    ) -> List[str]:
        """Process multiple groups and generate reports.

        Args:
            groups: List of groups to process
            should_email: Whether to send individual emails
            override_email: Email address for bulk sending (overrides individual emails)
            progress_callback: Optional callback for progress updates
            tracker: Optional ProgressTracker instance for UI integration

        Returns:
            List of generated CSV file paths
        """
        executor = DatabaseExecutor(self.config.get("oracle_tns"))
        max_workers = self.config.get("max_workers") or os.cpu_count() or 4
        if tracker is None:
            tracker = ProgressTracker(len(groups))
        csv_files = []

        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = []
                for idx, group in enumerate(groups, start=1):
                    tracker.update(group.handle, "queued")
                    future = pool.submit(
                        self._process_single_group,
                        group,
                        executor,
                        tracker,
                        should_email,
                        override_email,
                        idx,
                        len(groups)
                    )
                    futures.append(future)

                for future in as_completed(futures):
                    try:
                        csv_path = future.result()
                        if csv_path:
                            csv_files.append(csv_path)
                            if progress_callback:
                                progress_callback(csv_path)
                    except Exception as e:
                        print(f"Error in group processing task: {e}")

            # Send bulk email if override email is specified
            if override_email and csv_files:
                self._send_bulk_email(override_email, csv_files, groups)

        finally:
            try:
                executor.close()
            except Exception:
                pass

        return csv_files

    def _process_single_group(
        self,
        group: Group,
        executor: DatabaseExecutor,
        tracker: ProgressTracker,
        should_email: bool,
        override_email: Optional[str],
        job_num: int,
        job_total: int
    ) -> Optional[str]:
        """Process a single group.

        Returns:
            Path to generated CSV file, or None if failed
        """
        handle = group.handle
        tracker.update(handle, f"generating member list ({job_num}/{job_total})")

        try:
            # Read and execute query
            tracker.update(handle, "querying database")
            query = group.read_query()
            rows = executor.run_query(query)
            tracker.update(handle, f"fetched {len(rows)} rows")

            # Process email addresses
            emails = self._extract_emails(rows)
            rows = emails

            # Prepare output
            out_base = self.config.get("output_dir")
            folder = group.output_path(out_base)
            os.makedirs(folder, exist_ok=True)

            date_str = datetime.now().strftime("%y-%m-%d")
            fname = f"{handle} ({group.display_name}) - {date_str}.csv"
            fullpath = os.path.join(folder, fname)

            # Write CSV
            tracker.update(handle, "writing CSV")
            executor.write_csv(rows, None, fullpath)
            tracker.update(handle, f"written {os.path.basename(fullpath)}")

            # Send individual email if requested and not using bulk override
            if should_email and not override_email:
                tracker.update(handle, "sending email")
                self._send_group_email(group, fullpath, len(rows), date_str)

            return fullpath

        except Exception as e:
            tracker.update(handle, f"failed: {e}")
            return None
        finally:
            tracker.increment(handle)

    def _extract_emails(self, rows: List) -> List[tuple]:
        """Extract and normalize email addresses from query results."""
        emails = []
        for row in rows:
            email = None
            if isinstance(row, dict):
                # Try to find username column
                for key, value in row.items():
                    if key.lower() == "username" and isinstance(value, str):
                        email = value
                        break
            else:
                # Assume first column is username
                if row and isinstance(row[0], str):
                    email = row[0]

            if email is None:
                continue

            # Add domain if not present
            if not email.lower().endswith("@fastenal.com"):
                email = f"{email}@fastenal.com"

            emails.append((email,))

        return emails

    def _send_group_email(
        self,
        group: Group,
        csv_file: str,
        row_count: int,
        date_str: str
    ) -> None:
        """Send email for a single group."""
        recipient = group.config.get("email_recipient") or self.config.get("email_recipient")
        if not recipient:
            return

        auto_send = self.config.get("outlook_auto_send", False)
        self.email_service.send_group_email(
            recipient=recipient,
            csv_file=csv_file,
            group_name=group.display_name,
            group_handle=group.handle,
            date_str=date_str,
            row_count=row_count,
            auto_send=auto_send
        )

    def _send_bulk_email(
        self,
        recipient: str,
        csv_files: List[str],
        groups: List[Group]
    ) -> None:
        """Send bulk email with all generated CSVs."""
        date_str = datetime.now().strftime("%y-%m-%d")
        groups_list = "\n".join([f"  - {os.path.basename(f)}" for f in csv_files])

        self.email_service.send_bulk_email(
            recipient=recipient,
            csv_files=csv_files,
            groups_list=groups_list,
            date_str=date_str,
            count=len(groups)
        )