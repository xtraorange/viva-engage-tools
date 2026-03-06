import csv
import os
import threading
from datetime import datetime
from typing import Any, Dict, List

import jampy_db


class DatabaseExecutor:
    def __init__(self, tns: str, profile: str = "oracle_thick_external", **props):
        # build a shared jampy_db client; extra props may include client_folder,
        # lib_dir, config_dir, or any other profile-specific keyword arguments.
        self.client = jampy_db.create(profile, tnsname=tns, **props)

    def run_query(self, query: str) -> List[Any]:
        # execute synchronously; default return_type 'rows' returns list of dicts
        job = self.client.query(query, return_type="rows", run_async=False)
        return job.result()

    def write_csv(self, rows: Any, headers: Any, out_file: str) -> None:
        """Write provided rows to CSV without any header.

        Each row should be an iterable of values; the caller is responsible for
        collapsing to a single email column if desired.
        """
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(out_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            for row in rows:
                writer.writerow(row)

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass


# simple progress tracker shared among threads
class ProgressTracker:
    def __init__(self, total: int):
        self.lock = threading.Lock()
        self.total = total
        self.done = 0
        self.status: Dict[str, str] = {}

    def update(self, handle: str, msg: str):
        with self.lock:
            self.status[handle] = msg
            self._print_status()

    def increment(self, handle: str):
        with self.lock:
            self.done += 1
            self._print_status()

    def _print_status(self):
        lines = [f"{h}: {s}" for h, s in self.status.items()]
        pct = (self.done / self.total * 100) if self.total else 0
        lines.append(f"Completed {self.done}/{self.total} ({pct:.0f}% )")
        # print progress without clearing screen so terminal output remains readable
        print("\n".join(lines))
