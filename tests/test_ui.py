import pytest
import os
from datetime import datetime, timedelta
from src.ui import create_app


def test_ui_app_creation():
    app = create_app()
    assert app is not None
    # verify that important endpoints exist
    routes = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert 'index' in routes
    assert 'edit_group' in routes
    assert 'generate' in routes
    assert 'status' in routes
    assert 'perform_update' in routes
    assert 'pick_folder' in routes


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_index_page(client):
    rv = client.get('/settings')
    assert rv.status_code == 200
    assert b'General Settings' in rv.data


def test_generate_page(client):
    rv = client.get('/')
    assert rv.status_code == 200
    assert b'Select Reports' in rv.data


def test_pick_folder_api(client):
    # the API should return a json object; since tkinter may not be available during tests, allow error
    rv = client.get('/api/pick-folder')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'cancelled' in data or 'error' in data or 'path' in data


def test_updates_page(client):
    rv = client.get('/updates')
    assert rv.status_code == 200
    assert b'Application Updates' in rv.data


def test_force_bypasses_cache(monkeypatch, client, tmp_path):
    """Clicking the check-again button should clear cache and fetch fresh"""
    import yaml, os

    general_path = os.path.join(os.getcwd(), "config", "general.yaml")
    # set up config with nested info structure
    cfg = yaml.safe_load(open(general_path, "r")) or {}
    cfg["update_info"] = {"version": "1.0.0", "body": "", "last_check": "2026-01-01T00:00:00"}
    yaml.safe_dump(cfg, open(general_path, "w"))

    # fake network responses so the update check returns a new version
    called = {'count': 0}
    def fake_urlopen(url):
        called['count'] += 1
        class Dummy:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                pass
            def read(self):
                if 'raw.githubusercontent' in url:
                    return b"version: '9.9.9'\nrepository: foo/bar\n"
                else:
                    return b'{"body": "notes"}'
        return Dummy()

    from src import ui
    monkeypatch.setattr(ui.urllib.request, 'urlopen', fake_urlopen)

    # perform a GET with check=true to clear and fetch
    rv = client.get('/updates?check=true')
    assert rv.status_code == 200

    # ensure our fake network call was used
    assert called['count'] > 0, "urlopen was never called"

    # read config back and validate changes
    cfg2 = yaml.safe_load(open(general_path, "r"))
    assert cfg2["update_info"]["last_check"] is not None
    assert cfg2["update_info"]["version"] == '9.9.9'
    # route itself should render the new version in body
    assert b'v9.9.9' in rv.data

    # cleanup: reset update_info to empty for next test/download
    cfg2["update_info"] = {}
    yaml.safe_dump(cfg2, open(general_path, "w"))


def test_restart_endpoint(client, tmp_path):
    rv = client.post('/restart')
    # should always return 200
    assert rv.status_code == 200
    assert b"Shutting" in rv.data
    # flag file should have been created
    flag_path = os.path.join(os.getcwd(), "restart.flag")
    assert os.path.exists(flag_path)
    os.remove(flag_path)


def test_update_stashes_changes(monkeypatch, client):
    """perform_update should stash local modifications and pop afterwards"""
    from threading import Event
    from types import SimpleNamespace
    calls = []
    
    def fake_run(cmd, cwd=None, capture_output=False, text=False, timeout=None, check=False):
        calls.append(cmd)
        # simulate normal completed process
        return SimpleNamespace(stdout="ok", stderr="")

    monkeypatch.setattr('src.ui.subprocess.run', fake_run)

    # trigger update
    rv = client.post('/update')
    assert rv.status_code == 302
    # wait until updating flag clears
    import time
    while True:
        status = client.get('/api/update-status').get_json()
        if not status['updating']:
            break
        time.sleep(0.1)
    # ensure stash/pull/pop commands invoked
    assert ['git', 'stash', 'push', '-u', '-m', 'jampy-update'] in calls
    assert ['git', 'pull', '--ff-only'] in calls
    assert ['git', 'stash', 'pop'] in calls


def test_query_builder_routes(client):
    # Test query builder page loads
    response = client.get("/query-builder")
    assert response.status_code == 200
    assert b"SQL Query Builder" in response.data

    # Test employee search (will fail without DB, but should not crash)
    response = client.get("/api/search-employees?q=test")
    assert response.status_code in [200, 500]  # 500 is expected without DB

    # Test attribute searches
    response = client.get("/api/search-job-titles?q=test")
    assert response.status_code in [200, 500]

    response = client.get("/api/search-bu-codes?q=test")
    assert response.status_code in [200, 500]

    response = client.get("/api/search-companies?q=test")
    assert response.status_code in [200, 500]

    response = client.get("/api/search-tree-branches?q=test")
    assert response.status_code in [200, 500]

    # Test SQL generation
    response = client.post("/api/generate-builder-sql", json={
        "mode": "by_person",
        "person_id": "12345"
    })
    assert response.status_code in [200, 400]

    # Test query testing
    response = client.post("/api/test-query", json={
        "sql": "SELECT * FROM dual"
    })
    assert response.status_code in [200, 500]

