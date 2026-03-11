import os
import socket
import time
import io
from pathlib import Path

import pytest
import yaml

from src.ui import create_app, _find_available_port


@pytest.fixture
def app_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "groups").mkdir(parents=True, exist_ok=True)

    (tmp_path / "config" / "general.yaml").write_text(
        yaml.safe_dump(
            {
                "oracle_tns": "dummy",
                "ui_port": 5000,
                "output_dir": str(tmp_path / "output"),
                "email_method": "smtp",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "config" / "version.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "0.2.0",
                "repository": "xtraorange/jampy-engage",
            }
        ),
        encoding="utf-8",
    )

    app = create_app()
    app.testing = True
    return app, tmp_path


@pytest.fixture
def client(app_workspace):
    app, _ = app_workspace
    return app.test_client()


def _write_group(base_path: Path, handle: str, query_builder=None, override_query=None):
    folder = base_path / "groups" / handle
    folder.mkdir(parents=True, exist_ok=True)
    cfg = {
        "handle": handle,
        "display_name": handle,
        "tags": ["demo"],
    }
    if query_builder is not None:
        cfg["query_builder"] = query_builder

    (folder / "group.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    if override_query is not None:
        (folder / "query.sql").write_text(override_query, encoding="utf-8")


def wait_for_update_to_finish(client, timeout_seconds=5):
    start = time.time()
    while True:
        status = client.get("/api/update-status").get_json()
        if not status["updating"]:
            return status
        if time.time() - start > timeout_seconds:
            pytest.fail("Timed out waiting for update status to clear")
        time.sleep(0.05)


def test_ui_app_creation(app_workspace):
    app, _ = app_workspace
    routes = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "main.index" in routes
    assert "groups.edit_group" in routes
    assert "main.generate" in routes
    assert "main.status" in routes
    assert "updates.perform_update" in routes
    assert "updates.force_update" in routes


def test_index_page(client):
    rv = client.get("/settings")
    assert rv.status_code == 200
    assert b"General Settings" in rv.data


def test_settings_can_save_ui_port(client, app_workspace):
    _, base = app_workspace
    general_path = base / "config" / "general.yaml"
    original = general_path.read_text(encoding="utf-8")

    try:
        rv = client.post(
            "/settings",
            data={
                "ui_port": "5055",
                "output_dir": "./output",
                "email_method": "smtp",
            },
            follow_redirects=True,
        )
        assert rv.status_code == 200
        assert b"General Settings" in rv.data

        cfg = yaml.safe_load(general_path.read_text(encoding="utf-8")) or {}
        assert cfg.get("ui_port") == 5055
    finally:
        general_path.write_text(original, encoding="utf-8")


def test_settings_can_reset_stats(client, app_workspace):
    _, base = app_workspace
    stats_path = base / "config" / "stats.yaml"
    stats_path.write_text(
        yaml.safe_dump(
            {
                "total_run_requests": 10,
                "total_reports_generated": 22,
                "per_group_generation_counts": {"demo": 5},
            }
        ),
        encoding="utf-8",
    )

    rv = client.post(
        "/settings",
        data={"reset_stats": "1"},
        follow_redirects=True,
    )
    assert rv.status_code == 200

    cfg = yaml.safe_load(stats_path.read_text(encoding="utf-8")) or {}
    assert cfg.get("total_run_requests") == 0
    assert cfg.get("total_reports_generated") == 0
    assert cfg.get("per_group_generation_counts") == {}


def test_generate_page(client):
    # Test dashboard page
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"Dashboard" in rv.data
    assert b"Generate Reports" in rv.data
    
    # Test generate form page
    rv = client.get("/generate")
    assert rv.status_code == 200
    assert b"Generate Reports" in rv.data
    assert b"By Group" in rv.data
    assert b"By Tag" in rv.data
    assert b"Selection Summary" in rv.data
    assert b"Generation Options" in rv.data


def test_dashboard_stats_api(client):
    rv = client.get("/api/dashboard-stats")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "total_run_requests" in data
    assert "per_group_generation_counts" in data


def test_adhoc_match_ignores_blank_rows(client, monkeypatch):
    import src.ui.routes.main as main_routes

    class DummyLookupService:
        def __init__(self, oracle_tns):
            self.oracle_tns = oracle_tns

        def search_candidates(self, query=None, first_name=None, last_name=None, limit=20):
            return [{"id": "1", "first_name": first_name or query, "last_name": last_name or "User", "username": "demo", "email": "demo@fastenal.com", "job_title": "Tester"}]

    monkeypatch.setattr(main_routes, "EmployeeLookupService", DummyLookupService)

    csv_bytes = io.BytesIO(b"name\nAlice Example\n\nBob Example\n")
    rv = client.post(
        "/adhoc-match",
        data={"csv_file": (csv_bytes, "names.csv")},
        content_type="multipart/form-data",
    )
    assert rv.status_code == 200
    assert b'"row_index": 0' in rv.data
    assert b'"row_index": 1' in rv.data
    assert b'"row_index": 2' not in rv.data
    assert b"Rows Loaded" in rv.data


def test_adhoc_match_caches_duplicate_name_lookups(client, monkeypatch):
    import src.ui.routes.main as main_routes

    call_count = {"count": 0}

    class DummyLookupService:
        def __init__(self, oracle_tns):
            self.oracle_tns = oracle_tns

        def search_candidates(self, query=None, first_name=None, last_name=None, limit=20):
            call_count["count"] += 1
            return [{"id": "1", "first_name": first_name or query, "last_name": last_name or "User", "username": "demo", "email": "demo@fastenal.com", "job_title": "Tester"}]

    monkeypatch.setattr(main_routes, "EmployeeLookupService", DummyLookupService)

    csv_bytes = io.BytesIO(b"name\nAlice Example\nAlice Example\n")
    rv = client.post(
        "/adhoc-match",
        data={"csv_file": (csv_bytes, "names.csv")},
        content_type="multipart/form-data",
    )

    assert rv.status_code == 200
    assert call_count["count"] == 1


def test_updates_page(client):
    rv = client.get("/updates")
    assert rv.status_code == 200
    assert b"Application Updates" in rv.data


def test_force_bypasses_cache(monkeypatch, client, app_workspace):
    _, base = app_workspace
    general_path = base / "config" / "general.yaml"

    cfg = yaml.safe_load(general_path.read_text(encoding="utf-8")) or {}
    cfg["update_info"] = {
        "version": "1.0.0",
        "body": "",
        "last_check": "2026-01-01T00:00:00",
    }
    general_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    called = {"count": 0}

    def fake_urlopen(url):
        called["count"] += 1

        class Dummy:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                if "raw.githubusercontent" in url:
                    return b"version: '9.9.9'\nrepository: foo/bar\n"
                return b'{"body": "notes"}'

        return Dummy()

    import src.ui.routes.updates as updates

    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)

    rv = client.get("/updates?check=true")
    assert rv.status_code == 200
    assert called["count"] > 0

    cfg2 = yaml.safe_load(general_path.read_text(encoding="utf-8")) or {}
    assert cfg2["update_info"]["last_check"] is not None
    assert cfg2["update_info"]["version"] == "9.9.9"
    assert b"v9.9.9" in rv.data


def test_restart_endpoint(client):
    rv = client.post("/restart")
    assert rv.status_code == 200
    assert b"Shutting" in rv.data

    flag_path = Path.cwd() / "restart.flag"
    assert flag_path.exists()
    flag_path.unlink()


def test_update_stashes_changes(monkeypatch, client):
    from types import SimpleNamespace

    calls = []

    def fake_run(cmd, cwd=None, capture_output=False, text=False, timeout=None, check=False):
        calls.append(cmd)
        return SimpleNamespace(stdout="ok", stderr="")

    monkeypatch.setattr("src.ui.routes.updates.subprocess.run", fake_run)

    rv = client.post("/update")
    assert rv.status_code == 302

    wait_for_update_to_finish(client)
    assert ["git", "stash", "push", "-u", "-m", "jampy-update"] in calls
    assert ["git", "pull", "--ff-only"] in calls
    assert ["git", "stash", "pop"] in calls


def test_force_update_endpoint(monkeypatch, client):
    from types import SimpleNamespace

    calls = []

    def fake_run(cmd, cwd=None, capture_output=False, text=False, timeout=None, check=False):
        calls.append(cmd)
        return SimpleNamespace(stdout="ok", stderr="")

    monkeypatch.setattr("src.ui.routes.updates.subprocess.run", fake_run)

    rv = client.post("/force-update")
    assert rv.status_code == 302

    status = wait_for_update_to_finish(client)
    assert ["git", "stash", "push", "-u", "-m", "jampy-update"] in calls
    assert ["git", "pull", "--ff-only"] in calls
    assert ["git", "stash", "pop"] in calls
    assert "force update" in status["status"].lower()


def test_query_builder_routes(client, monkeypatch):
    called = {"sql": []}

    class DummyExec:
        def __init__(self, tns):
            pass

        def run_query(self, sql):
            called["sql"].append(sql)
            if "COUNT(*)" in sql:
                return [{"COUNT(*)": 0}]
            return []

        def close(self):
            pass

    import src.ui.routes.api as api

    monkeypatch.setattr(api, "DatabaseExecutor", DummyExec)

    response = client.get("/query-builder")
    assert response.status_code == 200
    assert b"SQL Query Builder" in response.data

    response = client.get("/tag/new")
    assert response.status_code == 200
    assert b"Create New Tag" in response.data

    response = client.get("/api/search-employees?q=test")
    assert response.status_code in [200, 500]

    for field in ["job_title", "bu_code", "company", "tree_branch", "department_id"]:
        response = client.get(f"/api/search-values?field={field}&q=test")
        assert response.status_code == 200
        assert any("UPPER" in sql for sql in called["sql"])

    response = client.post("/api/generate-builder-sql", json={"mode": "by_person", "person_id": "12345"})
    assert response.status_code in [200, 400]
    if response.status_code == 200:
        data = response.get_json()
        sql = data.get("sql", "")
        assert "EMPLOYEE_ID" in sql

    response = client.post(
        "/api/generate-builder-sql",
        json={
            "mode": "by_person",
            "person_id": "00001",
            "filter_bu_codes": ["abc"],
            "filter_job_titles": ["mgr"],
        },
    )
    assert response.status_code in [200, 400]
    if response.status_code == 200:
        sql = response.get_json().get("sql", "")
        assert "BU_CODE" in sql
        assert "JOB_CODE" in sql

    response = client.post(
        "/api/generate-builder-sql",
        json={
            "mode": "by_person",
            "persons": ["gwilson"],
            "attributes_bu_code": "IGNORED_FOR_BY_PERSON",
        },
    )
    assert response.status_code in [200, 400]
    if response.status_code == 200:
        sql = response.get_json().get("sql", "")
        assert "gwilson" in sql
        assert "IGNORED_FOR_BY_PERSON" not in sql

    response = client.post("/api/test-query", json={"sql": "SELECT * FROM dual"})
    assert response.status_code in [200, 500]


def test_group_edit_hides_builder_summary_when_override_exists(client, app_workspace):
    _, base = app_workspace
    _write_group(
        base,
        "sample_group",
        query_builder={"mode": "by_role", "attributes_job_code": "000545"},
        override_query="SELECT USERNAME FROM omsadm.employee_mv",
    )

    rv = client.get("/group/sample_group")
    assert rv.status_code == 200
    assert b"Override SQL is active" in rv.data
    assert b"Remove Override SQL Script" in rv.data
    assert b'id="builder-panel" style="display: none;"' in rv.data
    assert b'id="override-panel"' in rv.data


def test_group_edit_renders_saved_builder_summary_without_navigation(client, app_workspace):
    _, base = app_workspace
    _write_group(
        base,
        "summary_group",
        query_builder={"mode": "by_role", "attributes_job_code": "000545"},
    )

    rv = client.get("/group/summary_group")
    assert rv.status_code == 200
    assert b"Builder Method and Parameters" in rv.data
    assert b"Edit SQL Manually (Override)" in rv.data
    assert b'id="override-panel" style="display: none;"' in rv.data


def test_group_new_hides_override_editor_by_default(client):
    rv = client.get("/group/new")
    assert rv.status_code == 200
    assert b"Edit SQL Manually (Override)" in rv.data
    assert b'id="override-panel" style="display: none;"' in rv.data


def test_tag_edit_page_and_update(client, app_workspace):
    _, base = app_workspace
    _write_group(base, "g_one")
    _write_group(base, "g_two")

    # Seed a tag on one group.
    group_cfg = base / "groups" / "g_one" / "group.yaml"
    cfg = yaml.safe_load(group_cfg.read_text(encoding="utf-8")) or {}
    cfg["tags"] = ["demo_tag"]
    group_cfg.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    rv = client.get("/tag/demo_tag/edit")
    assert rv.status_code == 200
    assert b"Edit Tag" in rv.data

    rv = client.post(
        "/tag/demo_tag/edit",
        data={"tag_name": "demo_tag", "groups": ["g_one", "g_two"]},
        follow_redirects=True,
    )
    assert rv.status_code == 200
    assert b"Tags" in rv.data


def test_find_available_port_chooses_fallback_when_preferred_in_use():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    preferred = sock.getsockname()[1]
    sock.listen(1)

    try:
        selected = _find_available_port(preferred)
        assert selected != preferred
    finally:
        sock.close()
