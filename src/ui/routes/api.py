"""API routes for AJAX calls."""
from flask import Blueprint, request, jsonify
import os

from ...services.config_service import ConfigService
from ...sql_builder import generate_safe_hierarchy_sql

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
            from ...db import DatabaseExecutor
            executor = DatabaseExecutor(cfg.get("oracle_tns"))

            # First test basic connection
            test_sql = "SELECT 1 FROM dual"
            test_result = executor.run_query(test_sql)
            print(f"DEBUG: Database connection test: {test_result}")  # Debug log

            # Search across ID, name, and username (case-insensitive)
            sql = f"""
            SELECT ID, FIRST_NAME, LAST_NAME, USERNAME FROM omsadm.employee_mv
            WHERE (UPPER(ID) LIKE UPPER('%{query}%') OR UPPER(FIRST_NAME) LIKE UPPER('%{query}%') OR UPPER(LAST_NAME) LIKE UPPER('%{query}%') OR UPPER(USERNAME) LIKE UPPER('%{query}%'))
            AND Terminated IS NULL
            ORDER BY FIRST_NAME, LAST_NAME
            """

            results = executor.run_query(sql)
            print(f"DEBUG: Search query '{query}' returned {len(results)} results")  # Debug log
            items = [
                {"id": row[0], "first_name": row[1], "last_name": row[2], "username": row[3]}
                for row in results[:20]  # Limit results
            ]
            executor.close()
            return jsonify(items)
        except Exception as e:
            print(f"DEBUG: Search error for '{query}': {str(e)}")  # Debug log
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/search-job-titles", methods=["GET"])
    def search_job_titles():
        """Typeahead search for job titles."""
        cfg = config_service.load_general_config()
        query = request.args.get("q", "").strip()

        if not query or len(query) < 1:
            return jsonify([])

        try:
            from ...db import DatabaseExecutor
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT JOB_TITLE FROM omsadm.employee_mv WHERE JOB_TITLE LIKE '%{query}%' AND Terminated IS NULL ORDER BY JOB_TITLE"
            results = executor.run_query(sql)
            items = [{"value": row[0]} for row in results[:20]]
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/search-bu-codes", methods=["GET"])
    def search_bu_codes():
        """Typeahead search for business unit codes."""
        cfg = config_service.load_general_config()
        query = request.args.get("q", "").strip()

        if not query or len(query) < 1:
            return jsonify([])

        try:
            from ...db import DatabaseExecutor
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT BU_CODE FROM omsadm.employee_mv WHERE BU_CODE LIKE '%{query}%' AND Terminated IS NULL ORDER BY BU_CODE"
            results = executor.run_query(sql)
            items = [{"value": row[0]} for row in results[:20]]
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/search-companies", methods=["GET"])
    def search_companies():
        """Typeahead search for companies/countries."""
        cfg = config_service.load_general_config()
        query = request.args.get("q", "").strip()

        if not query or len(query) < 1:
            return jsonify([])

        try:
            from ...db import DatabaseExecutor
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT COMPANY FROM omsadm.employee_mv WHERE COMPANY LIKE '%{query}%' AND Terminated IS NULL ORDER BY COMPANY"
            results = executor.run_query(sql)
            items = [{"value": row[0]} for row in results[:20]]
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
            from ...db import DatabaseExecutor
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT TREE_BRANCH FROM omsadm.employee_mv WHERE TREE_BRANCH LIKE '%{query}%' AND Terminated IS NULL ORDER BY TREE_BRANCH"
            results = executor.run_query(sql)
            items = [{"value": row[0]} for row in results[:20]]
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

            from ..db import DatabaseExecutor
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            # Count records
            count_sql = f"SELECT COUNT(*) FROM ({sql})"
            result = executor.run_query(count_sql)
            count = result[0][0] if result else 0
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