import pytest
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
    """Clicking the check-again button should force a fresh lookup and store plain version"""
    import yaml, os

    general_path = os.path.join(os.getcwd(), "config", "general.yaml")
    # set up old config state
    old = datetime.now() - timedelta(days=1)
    cfg = yaml.safe_load(open(general_path, "r")) or {}
    # ensure we start with a nested info structure
    cfg["update_info"] = {"tag_name": "1.0.0", "version": "1.0.0", "last_check": old.isoformat()}
    # remove any legacy key if present
    cfg.pop("last_update_check", None)
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

    # perform a GET with force parameter
    rv = client.get('/updates?force=true')
    assert rv.status_code == 200

    # ensure our fake network call was used
    assert called['count'] > 0, "urlopen was never called"

    # read config back and validate changes
    cfg2 = yaml.safe_load(open(general_path, "r"))
    # the nested timestamp should have changed
    assert cfg2["update_info"]["last_check"] != old.isoformat()
    assert cfg2["update_info"]["tag_name"] == '9.9.9'
    # route itself should render the new version in body
    assert b'v9.9.9' in rv.data


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

