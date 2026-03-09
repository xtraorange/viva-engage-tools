"""API routes for AJAX calls."""
from flask import Blueprint, request, jsonify
import os
import sys
from datetime import datetime

from ...services.config_service import ConfigService
from ...sql_builder import generate_safe_hierarchy_sql
from ...db import DatabaseExecutor

api_bp = Blueprint('api', __name__)


def init_api_routes(app, base_path: str):
    """Initialize API routes with dependencies."""
    config_service = ConfigService(base_path)

    @api_bp.route("/api/search-employees", methods=["GET"])
    def search_employees():
        """Typeahead search for employees."""
        cfg = config_service.load_general_config()
        query = request.args.get("q", "").strip()

        if not query or len(query) < 2:
            return jsonify([])

        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))

            # Build search conditions with support for full-name and partial name matching
            conds = []
            conds.append(f"UPPER(EMPLOYEE_ID) LIKE UPPER('%{query}%')")
            conds.append(f"UPPER(FIRST_NAME) LIKE UPPER('%{query}%')")
            conds.append(f"UPPER(LAST_NAME) LIKE UPPER('%{query}%')")
            conds.append(f"UPPER(USERNAME) LIKE UPPER('%{query}%')")
            # concatenated full name
            conds.append(f"UPPER(FIRST_NAME || ' ' || LAST_NAME) LIKE UPPER('%{query}%')")
            # if query contains two words, also try first/last separately
            if ' ' in query:
                parts = query.split()
                if len(parts) >= 2:
                    first_part = parts[0]
                    last_part = parts[-1]
                    conds.append(f"(UPPER(FIRST_NAME) LIKE UPPER('%{first_part}%') AND UPPER(LAST_NAME) LIKE UPPER('%{last_part}%'))")

            where_clause = " OR ".join(conds)
            sql = f"""
            SELECT EMPLOYEE_ID, FIRST_NAME, LAST_NAME, USERNAME FROM omsadm.employee_mv
            WHERE ({where_clause})
            AND status_code != 'T'
            ORDER BY FIRST_NAME, LAST_NAME
            """

            results = executor.run_query(sql)
            print(f"DEBUG: Query results: {results}, type: {type(results)}")
            items = []
            for row in results[:20]:  # Limit results
                if isinstance(row, dict):
                    items.append({
                        "id": row.get("EMPLOYEE_ID") or row.get("employee_id"),
                        "first_name": row.get("FIRST_NAME") or row.get("first_name"),
                        "last_name": row.get("LAST_NAME") or row.get("last_name"),
                        "username": row.get("USERNAME") or row.get("username"),
                    })
                else:
                    items.append({
                        "id": row[0],
                        "first_name": row[1],
                        "last_name": row[2],
                        "username": row[3],
                    })
            executor.close()
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
            "tree_branch": "TREE_BRANCH"
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
            "tree_branch": "TREE_BRANCH"
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

    return api_bp