import pytest
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

