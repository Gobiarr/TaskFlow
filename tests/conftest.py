import os
import sqlite3
import tempfile
from contextlib import closing
from hashlib import sha256
import hmac
import json
from pathlib import Path
import time
from urllib.parse import urlencode

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DATABASE_PATH = _PROJECT_ROOT / "taskflow.db"
_TEMP_DATABASE_DIRECTORY = tempfile.TemporaryDirectory(
    prefix="taskflow-tests-"
)
TEST_DATABASE_PATH = (
    Path(_TEMP_DATABASE_DIRECTORY.name) / "taskflow-test.db"
).resolve()
_PREVIOUS_DATABASE_PATH = os.environ.get("TASKFLOW_DATABASE_PATH")
_PREVIOUS_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
_PREVIOUS_TIMEZONE = os.environ.get("TASKFLOW_TIMEZONE")
_PREVIOUS_TASKFLOW_ENV = os.environ.get("TASKFLOW_ENV")
_PREVIOUS_LOCAL_AUTH = os.environ.get(
    "TASKFLOW_ALLOW_UNAUTHENTICATED_LOCAL"
)
TEST_BOT_TOKEN = "123456:test-taskflow-bot-token"
os.environ["TELEGRAM_BOT_TOKEN"] = TEST_BOT_TOKEN
os.environ["TASKFLOW_TIMEZONE"] = ""
os.environ["TASKFLOW_ENV"] = "production"
os.environ["TASKFLOW_ALLOW_UNAUTHENTICATED_LOCAL"] = "false"

if TEST_DATABASE_PATH == _DEFAULT_DATABASE_PATH.resolve():
    raise RuntimeError("Test database must not be the project database")

os.environ["TASKFLOW_DATABASE_PATH"] = str(TEST_DATABASE_PATH)


def telegram_headers(user_id=1, auth_date=None):
    values = {
        "auth_date": str(auth_date or int(time.time())),
        "user": json.dumps({"id": user_id}, separators=(",", ":")),
    }
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        TEST_BOT_TOKEN.encode(),
        sha256,
    ).digest()
    values["hash"] = hmac.new(
        secret_key,
        data_check_string.encode(),
        sha256,
    ).hexdigest()
    return {"X-Telegram-Init-Data": urlencode(values)}


@pytest.fixture(scope="session")
def api_client():
    from fastapi.testclient import TestClient

    from backend.app.database import DATABASE_PATH
    from backend.app.main import app

    if DATABASE_PATH.resolve() != TEST_DATABASE_PATH:
        raise RuntimeError(
            "FastAPI is not configured to use the isolated test database"
        )

    with TestClient(app, headers=telegram_headers()) as client:
        yield client


@pytest.fixture(autouse=True)
def reset_test_database(api_client):
    with closing(sqlite3.connect(TEST_DATABASE_PATH)) as database:
        database.execute("DELETE FROM habit_completions")
        database.execute("DELETE FROM habits")
        database.execute("DELETE FROM achievements")
        database.execute("DELETE FROM tasks")
        database.execute("DELETE FROM profiles")
        database.execute(
            "INSERT INTO profiles (user_id, xp, completed_tasks) "
            "VALUES (1, 0, 0)"
        )
        database.commit()

    yield

    with closing(sqlite3.connect(TEST_DATABASE_PATH)) as database:
        result = database.execute("PRAGMA integrity_check").fetchone()[0]

    assert result == "ok"


def pytest_unconfigure(config):
    _TEMP_DATABASE_DIRECTORY.cleanup()

    if _PREVIOUS_DATABASE_PATH is None:
        os.environ.pop("TASKFLOW_DATABASE_PATH", None)
    else:
        os.environ["TASKFLOW_DATABASE_PATH"] = _PREVIOUS_DATABASE_PATH

    if _PREVIOUS_BOT_TOKEN is None:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    else:
        os.environ["TELEGRAM_BOT_TOKEN"] = _PREVIOUS_BOT_TOKEN

    if _PREVIOUS_TIMEZONE is None:
        os.environ.pop("TASKFLOW_TIMEZONE", None)
    else:
        os.environ["TASKFLOW_TIMEZONE"] = _PREVIOUS_TIMEZONE

    if _PREVIOUS_TASKFLOW_ENV is None:
        os.environ.pop("TASKFLOW_ENV", None)
    else:
        os.environ["TASKFLOW_ENV"] = _PREVIOUS_TASKFLOW_ENV

    if _PREVIOUS_LOCAL_AUTH is None:
        os.environ.pop("TASKFLOW_ALLOW_UNAUTHENTICATED_LOCAL", None)
    else:
        os.environ["TASKFLOW_ALLOW_UNAUTHENTICATED_LOCAL"] = (
            _PREVIOUS_LOCAL_AUTH
        )
