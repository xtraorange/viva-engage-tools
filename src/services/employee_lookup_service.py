"""Helpers for searching employee records for UI workflows."""

from typing import Any, Dict, List, Optional

from ..db import DatabaseExecutor


EXPORTABLE_FIELDS: Dict[str, str] = {
    "employee_id": "Employee ID",
    "username": "Username",
    "email": "Email",
    "job_title": "Job Title",
    "department_id": "Department ID",
    "bu_code": "Business Unit",
    "company": "Company",
    "tree_branch": "Tree Branch",
    "full_part_time": "Full/Part Time",
}


def _sanitize(value: Optional[str]) -> str:
    return (value or "").replace("'", "''").strip()


def _serialize_row(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        getter = lambda *keys: next((row.get(key) for key in keys if row.get(key) is not None), None)
    else:
        getter = lambda index, *_keys: row[index] if len(row) > index else None

    return {
        "id": getter("EMPLOYEE_ID", "employee_id") if isinstance(row, dict) else getter(0),
        "first_name": getter("FIRST_NAME", "first_name") if isinstance(row, dict) else getter(1),
        "last_name": getter("LAST_NAME", "last_name") if isinstance(row, dict) else getter(2),
        "username": getter("USERNAME", "username") if isinstance(row, dict) else getter(3),
        "email": getter("EMAIL", "email") if isinstance(row, dict) else getter(4),
        "job_title": getter("JOB_TITLE", "job_title") if isinstance(row, dict) else getter(5),
        "department_id": getter("DEPARTMENT_ID", "department_id") if isinstance(row, dict) else getter(6),
        "bu_code": getter("BU_CODE", "bu_code") if isinstance(row, dict) else getter(7),
        "company": getter("COMPANY", "company") if isinstance(row, dict) else getter(8),
        "tree_branch": getter("TREE_BRANCH", "tree_branch") if isinstance(row, dict) else getter(9),
        "full_part_time": getter("FULL_PART_TIME", "full_part_time") if isinstance(row, dict) else getter(10),
    }


class EmployeeLookupService:
    """Search employee records using the configured database."""

    def __init__(self, oracle_tns: str):
        self.oracle_tns = oracle_tns

    def search_candidates(
        self,
        query: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        search = _sanitize(query)
        first = _sanitize(first_name)
        last = _sanitize(last_name)

        if not search and not first and not last:
            return []

        conditions = []
        if search:
            conditions.extend([
                f"UPPER(EMPLOYEE_ID) LIKE UPPER('%{search}%')",
                f"UPPER(FIRST_NAME) LIKE UPPER('%{search}%')",
                f"UPPER(LAST_NAME) LIKE UPPER('%{search}%')",
                f"UPPER(USERNAME) LIKE UPPER('%{search}%')",
                f"UPPER(EMAIL) LIKE UPPER('%{search}%')",
                f"UPPER(FIRST_NAME || ' ' || LAST_NAME) LIKE UPPER('%{search}%')",
            ])

        if first and last:
            conditions.append(
                f"(UPPER(FIRST_NAME) LIKE UPPER('%{first}%') AND UPPER(LAST_NAME) LIKE UPPER('%{last}%'))"
            )
        elif first:
            conditions.append(f"UPPER(FIRST_NAME) LIKE UPPER('%{first}%')")
        elif last:
            conditions.append(f"UPPER(LAST_NAME) LIKE UPPER('%{last}%')")

        sql = f"""
        SELECT EMPLOYEE_ID,
               FIRST_NAME,
               LAST_NAME,
               USERNAME,
               EMAIL,
               JOB_TITLE,
               DEPARTMENT_ID,
               BU_CODE,
               COMPANY,
               TREE_BRANCH,
               FULL_PART_TIME
        FROM omsadm.employee_mv
        WHERE status_code != 'T'
          AND ({' OR '.join(conditions)})
        ORDER BY FIRST_NAME, LAST_NAME, USERNAME
        FETCH FIRST {max(1, int(limit))} ROWS ONLY
        """

        executor = DatabaseExecutor(self.oracle_tns)
        try:
            return [_serialize_row(row) for row in executor.run_query(sql)]
        finally:
            executor.close()
