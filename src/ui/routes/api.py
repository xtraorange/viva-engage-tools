"""API routes for AJAX calls."""
from flask import Blueprint, request, jsonify
import os
import sys
from datetime import datetime

from ...services.config_service import ConfigService
from ...services.employee_lookup_service import EmployeeLookupService
from ...sql_builder import generate_safe_hierarchy_sql
from ...db import DatabaseExecutor


def _single_or_in_condition(column: str, values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return f"{column} = '{values[0]}'"
    csv = ",".join([f"'{value}'" for value in values])
    return f"{column} IN ({csv})"

def init_api_routes(app, base_path: str):
    """Initialize API routes with dependencies."""
    api_bp = Blueprint('api', __name__)
    config_service = ConfigService(base_path)

    @api_bp.route("/api/search-employees", methods=["GET"])
    def search_employees():
        """Typeahead search for employees."""
        cfg = config_service.load_general_config()
        query = request.args.get("q", "").strip()

        if not query or len(query) < 2:
            return jsonify([])

        try:
            lookup_service = EmployeeLookupService(cfg.get("oracle_tns"))
            parts = query.split()
            first_name = parts[0] if len(parts) >= 2 else None
            last_name = parts[-1] if len(parts) >= 2 else None
            items = lookup_service.search_candidates(query=query, first_name=first_name, last_name=last_name, limit=20)
            return jsonify(items)
        except Exception as e:
            import traceback, logging, os
            err_msg = str(e)
            # Write detailed error to log file in base path
            log_path = os.path.join(os.getcwd(), 'error.log')
            with open(log_path, 'a', encoding='utf-8') as logf:
                logf.write(f"[{datetime.now()}] Search error for '{query}': {err_msg}\n")
                logf.write(traceback.format_exc())
                logf.write("\n---\n")
            print(f"DEBUG: Search error logged to {log_path}")
            # return full message if short number or generic
            return jsonify({"error": err_msg}), 500


    @api_bp.route("/api/get-all-values", methods=["GET"])
    def get_all_values():
        """Generic endpoint to get all unique values for a field."""
        cfg = config_service.load_general_config()
        field = request.args.get("field", "").strip()
        
        # Map field names to column names
        field_map = {
            "job_title": "JOB_TITLE",
            "bu_code": "BU_CODE", 
            "company": "COMPANY",
            "tree_branch": "TREE_BRANCH",
            "department_id": "DEPARTMENT_ID",
        }
        
        if field not in field_map:
            return jsonify({"error": "Invalid field"}), 400
            
        column = field_map[field]
        
        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT {column} FROM omsadm.employee_mv WHERE {column} IS NOT NULL AND status_code != 'T' ORDER BY {column}"
            results = executor.run_query(sql)
            items = [row[0] if isinstance(row, (list, tuple)) else next(iter(row.values())) for row in results]
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/search-values", methods=["GET"])
    def search_values():
        """Generic endpoint for live search of field values."""
        cfg = config_service.load_general_config()
        field = request.args.get("field", "").strip()
        query = request.args.get("q", "").strip()
        
        if not query or len(query) < 1:
            return jsonify([])
            
        # Map field names to column names
        field_map = {
            "job_title": "JOB_TITLE",
            "bu_code": "BU_CODE",
            "company": "COMPANY", 
            "tree_branch": "TREE_BRANCH",
            "department_id": "DEPARTMENT_ID",
        }
        
        if field not in field_map:
            return jsonify({"error": "Invalid field"}), 400
            
        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            if field == "job_title":
                # Special case: search both JOB_CODE and JOB_TITLE
                sql = f"SELECT DISTINCT JOB_CODE || ' - ' || JOB_TITLE as value FROM omsadm.employee_mv WHERE (UPPER(JOB_CODE) LIKE UPPER('%{query}%') OR UPPER(JOB_TITLE) LIKE UPPER('%{query}%')) AND status_code != 'T' ORDER BY value"
            else:
                column = field_map[field]
                sql = f"SELECT DISTINCT {column} FROM omsadm.employee_mv WHERE UPPER({column}) LIKE UPPER('%{query}%') AND status_code != 'T' ORDER BY {column}"
            
            results = executor.run_query(sql)
            items = []
            for row in results[:20]:
                if isinstance(row, dict):
                    value = next(iter(row.values()), None)
                else:
                    value = row[0]
                items.append({"value": value})
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/preview-role-roots", methods=["GET"])
    def preview_role_roots():
        """Preview employees selected as hierarchy roots in By Role mode."""
        cfg = config_service.load_general_config()
        job_titles = [value.strip().replace("'", "''") for value in request.args.getlist("job_title") if value.strip()]
        bu_codes = [value.strip().replace("'", "''") for value in request.args.getlist("bu_code") if value.strip()]
        companies = [value.strip().replace("'", "''") for value in request.args.getlist("company") if value.strip()]
        tree_branches = [value.strip().replace("'", "''") for value in request.args.getlist("tree_branch") if value.strip()]
        department_ids = [value.strip().replace("'", "''") for value in request.args.getlist("department_id") if value.strip()]

        # Require at least one attribute to avoid huge unfiltered queries.
        if not (job_titles or bu_codes or companies or tree_branches or department_ids):
            return jsonify([])

        where_parts = ["status_code != 'T'"]
        if job_titles:
            job_codes = [value.split(" - ", 1)[0].strip() for value in job_titles]
            where_parts.append(_single_or_in_condition("JOB_CODE", job_codes))
        if bu_codes:
            where_parts.append(_single_or_in_condition("BU_CODE", bu_codes))
        if companies:
            where_parts.append(_single_or_in_condition("COMPANY", companies))
        if tree_branches:
            where_parts.append(_single_or_in_condition("TREE_BRANCH", tree_branches))
        if department_ids:
            where_parts.append(_single_or_in_condition("DEPARTMENT_ID", department_ids))

        sql = f"""
        SELECT EMPLOYEE_ID, FIRST_NAME, LAST_NAME, USERNAME, JOB_TITLE
        FROM omsadm.employee_mv
        WHERE {' AND '.join(where_parts)}
        ORDER BY FIRST_NAME, LAST_NAME
        FETCH FIRST 25 ROWS ONLY
        """

        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            results = executor.run_query(sql)
            items = []
            for row in results:
                if isinstance(row, dict):
                    items.append({
                        "id": row.get("EMPLOYEE_ID") or row.get("employee_id"),
                        "first_name": row.get("FIRST_NAME") or row.get("first_name"),
                        "last_name": row.get("LAST_NAME") or row.get("last_name"),
                        "username": row.get("USERNAME") or row.get("username"),
                        "job_title": row.get("JOB_TITLE") or row.get("job_title"),
                    })
                else:
                    items.append({
                        "id": row[0],
                        "first_name": row[1],
                        "last_name": row[2],
                        "username": row[3],
                        "job_title": row[4],
                    })
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/search-tree-branches", methods=["GET"])
    def search_tree_branches():
        """Typeahead search for tree branches."""
        cfg = config_service.load_general_config()
        query = request.args.get("q", "").strip()

        if not query or len(query) < 1:
            return jsonify([])

        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT TREE_BRANCH FROM omsadm.employee_mv WHERE UPPER(TREE_BRANCH) LIKE UPPER('%{query}%') AND status_code != 'T' ORDER BY TREE_BRANCH"
            results = executor.run_query(sql)
            items = []
            for row in results[:20]:
                if isinstance(row, dict):
                    value = next(iter(row.values()), None)
                else:
                    value = row[0]
                items.append({"value": value})
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/generate-builder-sql", methods=["POST"])
    def generate_builder_sql():
        """Generate SQL from builder parameters."""
        try:
            data = request.get_json()

            sql = generate_safe_hierarchy_sql(**data)
            return jsonify({"sql": sql})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @api_bp.route("/api/test-query", methods=["POST"])
    def test_query():
        """Test a query and return record count."""
        try:
            cfg = config_service.load_general_config()
            data = request.get_json()
            sql = data.get("sql", "").strip()

            if not sql:
                return jsonify({"error": "No SQL provided"}), 400

            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            # Count records
            count_sql = f"SELECT COUNT(*) FROM ({sql})"
            result = executor.run_query(count_sql)
            count = result[0]["COUNT(*)"] if result else 0
            executor.close()

            return jsonify({"count": count})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/pick-folder")
    def pick_folder():
        """Open a native folder picker dialog."""
        try:
            # Try Windows Shell API first (fastest, no window)
            import ctypes
            import ctypes.wintypes as wintypes
            from ctypes import c_char_p, pointer, POINTER, Structure

            class BROWSEINFO(Structure):
                _fields_ = [
                    ("hwndOwner", wintypes.HWND),
                    ("pidlRoot", wintypes.c_void_p),
                    ("pszDisplayName", ctypes.c_char_p),
                    ("lpszTitle", wintypes.LPCSTR),
                    ("ulFlags", wintypes.UINT),
                    ("lpfn", wintypes.c_void_p),
                    ("lParam", wintypes.LPARAM),
                    ("iImage", wintypes.c_int),
                ]

            shell32 = ctypes.windll.shell32
            ole32 = ctypes.windll.ole32

            # Initialize COM
            ole32.CoInitialize(None)

            # Set up browse info
            bi = BROWSEINFO()
            bi.hwndOwner = None
            bi.pidlRoot = None
            bi.pszDisplayName = ctypes.create_string_buffer(4096)
            bi.lpszTitle = b"Select a folder"
            bi.ulFlags = 0x0001  # BIF_RETURNONLYFSDIRS

            # Show picker
            pidl = shell32.SHBrowseForFolder(pointer(bi))
            if pidl:
                path_buffer = ctypes.create_unicode_buffer(4096)
                shell32.SHGetPathFromIDListW(pidl, path_buffer)
                folder = path_buffer.value
                # Free PIDL
                ole32.CoTaskMemFree(pidl)
                ole32.CoUninitialize()
                if folder:
                    return jsonify(path=folder)
            ole32.CoUninitialize()
            return jsonify(cancelled=True)

        except Exception:
            # Fall back to tkinter
            try:
                import tkinter as tk
                from tkinter.filedialog import askdirectory

                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                folder = askdirectory(title="Select a folder")
                root.destroy()

                if folder:
                    return jsonify(path=folder)
                else:
                    return jsonify(cancelled=True)
            except ImportError:
                return jsonify(error="tkinter not installed"), 200
            except Exception as e:
                return jsonify(error=str(e)), 200

    @api_bp.route("/api/view-report", methods=["GET"])
    def view_report():
        """Retrieve report content as JSON for display in modal."""
        from flask import current_app
        handle = request.args.get("handle", "").strip()
        
        if not handle:
            return jsonify({"error": "No handle provided"}), 400
        
        tracker = current_app.config.get("tracker")
        if not tracker:
            return jsonify({"error": "No job running"}), 400
        
        result = tracker.results.get(handle)
        if not result:
            return jsonify({"error": "Group not found or not completed yet"}), 404
        
        csv_path = result.get("csv_path")
        if not csv_path:
            return jsonify({"error": "Report file not available"}), 404
        
        try:
            # Read CSV file
            import csv
            parsed_rows = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    # Generated report files typically have no header row; keep all rows as data.
                    if not row or not any(str(cell).strip() for cell in row):
                        continue
                    parsed_rows.append(row)

            if parsed_rows:
                max_cols = max(len(row) for row in parsed_rows)
            else:
                max_cols = 1

            # Provide synthetic headers so the UI can render a table.
            if max_cols == 1:
                headers = ["email"]
            else:
                headers = [f"column_{index + 1}" for index in range(max_cols)]

            rows = [row + [""] * (max_cols - len(row)) for row in parsed_rows]
            
            return jsonify({
                "headers": headers,
                "rows": rows,
                "total_rows": len(rows),
                "file_path": csv_path
            })
        except FileNotFoundError:
            return jsonify({"error": "Report file not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return api_bp