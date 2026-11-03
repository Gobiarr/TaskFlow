from contextlib import closing
import os
import sqlite3
from pathlib import Path

from backend.app.main import app
from backend.app.database import DATABASE_PATH

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_PATH = Path(os.environ["TASKFLOW_DATABASE_PATH"]).resolve()


def test_app_import_and_name():
    assert app.title == "TaskFlow API"


def test_expected_api_routes_are_registered():
    routes = {
        (method, route.path)
        for route in app.routes
        for method in (getattr(route, "methods", None) or set())
    }

    assert {
        ("GET", "/api/health"),
        ("GET", "/api/profile"),
        ("GET", "/api/achievements"),
        ("GET", "/api/tasks"),
        ("POST", "/api/tasks"),
        ("PATCH", "/api/tasks/{task_id}"),
        ("PATCH", "/api/tasks/{task_id}/complete"),
        ("DELETE", "/api/tasks/{task_id}"),
        ("GET", "/api/habits"),
        ("POST", "/api/habits"),
        ("PATCH", "/api/habits/{habit_id}"),
        ("GET", "/api/habits/{habit_id}/history"),
        ("POST", "/api/habits/{habit_id}/complete"),
        ("DELETE", "/api/habits/{habit_id}"),
    } <= routes


def test_health_endpoint_and_database_are_isolated(api_client):
    assert DATABASE_PATH.resolve() == TEST_DATABASE_PATH
    assert DATABASE_PATH.resolve() != (PROJECT_ROOT / "taskflow.db").resolve()
    assert any(
        parent.name.startswith("taskflow-tests-")
        for parent in TEST_DATABASE_PATH.parents
    )
    assert TEST_DATABASE_PATH.is_file()

    response = api_client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "application": "TaskFlow",
    }

    with closing(
        sqlite3.connect(
            f"{TEST_DATABASE_PATH.as_uri()}?mode=ro",
            uri=True,
        )
    ) as database:
        assert database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert database.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0


def test_frontend_and_static_assets_are_served(api_client):
    homepage = api_client.get("/")
    assert homepage.status_code == 200
    assert 'id="task-form"' in homepage.text
    assert 'id="task-status-filter"' in homepage.text
    assert 'id="habit-form"' in homepage.text

    for path in (
        "/static/css/style.css",
        "/static/js/app.js",
        "/static/favicon.svg",
    ):
        response = api_client.get(path)
        assert response.status_code == 200
        assert response.content
