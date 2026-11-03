from contextlib import closing
import asyncio
import sqlite3

from conftest import telegram_headers
from backend.app.database import DATABASE_PATH


def test_task_create_list_and_validation(api_client):
    first = api_client.post(
        "/api/tasks",
        json={
            "title": "  Первая задача  ",
            "description": "  описание  ",
            "category": "Работа",
            "priority": "high",
            "deadline": "2026-11-10",
        },
    )
    second = api_client.post(
        "/api/tasks",
        json={"title": "Вторая задача"},
    )

    assert first.status_code == 201
    assert first.json()["title"] == "Первая задача"
    assert first.json()["description"] == "описание"
    assert first.json()["is_completed"] is False
    assert first.json()["category"] == "Работа"
    assert first.json()["priority"] == "high"
    assert first.json()["deadline"] == "2026-11-10"
    assert second.status_code == 201

    listed = api_client.get("/api/tasks")
    assert listed.status_code == 200
    assert [task["title"] for task in listed.json()] == [
        "Вторая задача",
        "Первая задача",
    ]

    for payload in (
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 121},
        {"title": "Valid", "description": "x" * 501},
        {"title": "Valid", "priority": "urgent"},
        {"title": "Valid", "deadline": "not-a-date"},
        {"title": "Valid", "category": " "},
    ):
        assert api_client.post("/api/tasks", json=payload).status_code == 422


def test_task_edit_filter_sort_and_validation(api_client):
    task_ids = {}
    for title, priority, deadline, category in (
        ("Позже", "low", "2026-11-12", "Дом"),
        ("Раньше", "high", "2026-11-05", "Работа"),
        ("Без срока", "medium", None, "Дом"),
    ):
        response = api_client.post(
            "/api/tasks",
            json={
                "title": title,
                "priority": priority,
                "deadline": deadline,
                "category": category,
            },
        )
        assert response.status_code == 201
        task_ids[title] = response.json()["id"]

    assert [
        task["title"]
        for task in api_client.get("/api/tasks?status=active&sort=deadline").json()
    ] == ["Раньше", "Позже", "Без срока"]
    assert [
        task["title"]
        for task in api_client.get("/api/tasks?category=Дом").json()
    ] == ["Без срока", "Позже"]
    assert [
        task["title"]
        for task in api_client.get("/api/tasks?sort=priority").json()
    ] == ["Раньше", "Без срока", "Позже"]

    edited = api_client.patch(
        f"/api/tasks/{task_ids['Позже']}",
        json={
            "title": "  Обновлённая  ",
            "description": "  детали  ",
            "category": "  Личное  ",
            "priority": "medium",
            "deadline": None,
        },
    )
    assert edited.status_code == 200
    assert edited.json()["title"] == "Обновлённая"
    assert edited.json()["description"] == "детали"
    assert edited.json()["category"] == "Личное"
    assert edited.json()["priority"] == "medium"
    assert edited.json()["deadline"] is None

    assert api_client.patch(
        f"/api/tasks/{task_ids['Позже']}",
        json={"title": "  "},
    ).status_code == 422
    assert api_client.patch(
        f"/api/tasks/{task_ids['Позже']}",
        json={"priority": "urgent"},
    ).status_code == 422
    assert api_client.patch(
        f"/api/tasks/{task_ids['Позже']}",
        json={"deadline": "yesterday"},
    ).status_code == 422
    assert api_client.patch("/api/tasks/99999", json={"title": "Missing"}).status_code == 404
    assert api_client.get("/api/tasks?sort=unknown").status_code == 422


def test_telegram_auth_and_user_data_isolation(api_client):
    own_task = api_client.post(
        "/api/tasks",
        json={"title": "Только мой профиль"},
    ).json()

    other_user_headers = telegram_headers(user_id=2)
    other_tasks = api_client.get("/api/tasks", headers=other_user_headers)
    assert other_tasks.status_code == 200
    assert other_tasks.json() == []
    assert api_client.patch(
        f"/api/tasks/{own_task['id']}",
        headers=other_user_headers,
        json={"title": "Чужое изменение"},
    ).status_code == 404
    assert api_client.patch(
        f"/api/tasks/{own_task['id']}/complete",
        headers=other_user_headers,
    ).status_code == 404
    assert api_client.delete(
        f"/api/tasks/{own_task['id']}",
        headers=other_user_headers,
    ).status_code == 404
    assert api_client.get("/api/tasks").json()[0]["title"] == "Только мой профиль"

    created_for_other_user = api_client.post(
        "/api/tasks",
        headers=other_user_headers,
        json={"title": "Другой пользователь"},
    )
    assert created_for_other_user.status_code == 201
    assert api_client.get("/api/tasks").json()[0]["title"] == "Только мой профиль"
    forged_owner = api_client.post(
        "/api/tasks",
        json={"title": "User ID from request body", "user_id": 2},
    )
    assert forged_owner.status_code == 201
    assert api_client.get("/api/tasks").json()[0]["title"] == (
        "User ID from request body"
    )
    assert [
        task["title"]
        for task in api_client.get(
            "/api/tasks",
            headers=other_user_headers,
        ).json()
    ] == ["Другой пользователь"]

    invalid = api_client.get(
        "/api/profile",
        headers={"X-Telegram-Init-Data": "user=%7B%22id%22%3A1%7D"},
    )
    assert invalid.status_code == 401
    assert api_client.get(
        "/api/profile",
        headers=telegram_headers(auth_date=1),
    ).status_code == 401

    tampered_header = telegram_headers(user_id=1)["X-Telegram-Init-Data"]
    tampered_header = tampered_header.replace("%22id%22%3A1", "%22id%22%3A2")
    assert api_client.get(
        "/api/profile",
        headers={"X-Telegram-Init-Data": tampered_header},
    ).status_code == 401


def test_protected_routes_fail_closed_without_token(api_client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TASKFLOW_ENV", "production")
    monkeypatch.setenv("TASKFLOW_ALLOW_UNAUTHENTICATED_LOCAL", "true")
    requests = (
        ("GET", "/api/profile", None),
        ("GET", "/api/achievements", None),
        ("GET", "/api/tasks", None),
        ("POST", "/api/tasks", {"title": "Blocked"}),
        ("PATCH", "/api/tasks/99999", {"title": "Blocked"}),
        ("PATCH", "/api/tasks/99999/complete", None),
        ("DELETE", "/api/tasks/99999", None),
        ("GET", "/api/habits", None),
        ("POST", "/api/habits", {"title": "Blocked"}),
        ("PATCH", "/api/habits/99999", {"title": "Blocked"}),
        ("GET", "/api/habits/99999/history", None),
        ("POST", "/api/habits/99999/complete", None),
        ("DELETE", "/api/habits/99999", None),
    )

    for method, path, payload in requests:
        response = api_client.request(method, path, json=payload)
        assert response.status_code == 503, (method, path, response.text)


def test_local_auth_requires_explicit_development_settings(
    api_client,
    monkeypatch,
):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TASKFLOW_ENV", "development")
    monkeypatch.setenv("TASKFLOW_ALLOW_UNAUTHENTICATED_LOCAL", "true")

    response = api_client.get(
        "/api/profile",
        headers={"X-Telegram-Init-Data": ""},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == 1


def test_task_completion_profile_and_repeat_reward(api_client):
    task = api_client.post("/api/tasks", json={"title": "Выполнить"})
    task_id = task.json()["id"]

    initial_profile = api_client.get("/api/profile").json()
    assert initial_profile == {
        "user_id": 1,
        "xp": 0,
        "level": 1,
        "current_level_xp": 0,
        "next_level_xp": 100,
        "completed_tasks": 0,
    }

    completed = api_client.patch(f"/api/tasks/{task_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["is_completed"] is True
    assert api_client.get("/api/profile").json() == {
        "user_id": 1,
        "xp": 10,
        "level": 1,
        "current_level_xp": 10,
        "next_level_xp": 100,
        "completed_tasks": 1,
    }

    achievements = api_client.get("/api/achievements").json()
    first_step = next(item for item in achievements if item["code"] == "first_step")
    assert first_step["unlocked"] is True
    assert first_step["unlocked_at"] is not None

    edited = api_client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Изменить после выполнения"},
    )
    assert edited.status_code == 200
    assert edited.json()["is_completed"] is True
    assert api_client.get("/api/profile").json()["xp"] == 10

    repeated = api_client.patch(f"/api/tasks/{task_id}/complete")
    assert repeated.status_code == 200
    assert repeated.json()["is_completed"] is False
    profile_after_repeat = api_client.get("/api/profile").json()
    assert profile_after_repeat["xp"] == 10
    assert profile_after_repeat["completed_tasks"] == 1

    api_client.patch(f"/api/tasks/{task_id}/complete")
    assert api_client.get("/api/profile").json()["xp"] == 10
    achievements_after_repeat = api_client.get("/api/achievements").json()
    assert sum(item["unlocked"] for item in achievements_after_repeat) == 1
    with closing(sqlite3.connect(DATABASE_PATH)) as database:
        first_step_count = database.execute(
            "SELECT COUNT(*) FROM achievements WHERE code = ?",
            ("first_step",),
        ).fetchone()[0]
    assert first_step_count == 1


def test_task_delete_and_missing_task_responses(api_client):
    task_id = api_client.post(
        "/api/tasks",
        json={"title": "Удалить"},
    ).json()["id"]
    api_client.patch(f"/api/tasks/{task_id}/complete")

    deleted = api_client.delete(f"/api/tasks/{task_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"message": "Задача удалена", "id": task_id}
    assert api_client.get("/api/profile").json()["xp"] == 10
    assert api_client.get("/api/profile").json()["completed_tasks"] == 1
    assert api_client.get("/api/tasks").json() == []
    assert api_client.delete(f"/api/tasks/{task_id}").status_code == 404
    assert api_client.patch(
        f"/api/tasks/{task_id}/complete"
    ).status_code == 404


def test_achievement_thresholds_and_profile_level(api_client):
    locked = api_client.get("/api/achievements").json()
    assert len(locked) == 4
    assert not any(item["unlocked"] for item in locked)

    for index in range(25):
        task_id = api_client.post(
            "/api/tasks",
            json={"title": f"Задача {index + 1}"},
        ).json()["id"]
        response = api_client.patch(f"/api/tasks/{task_id}/complete")
        assert response.status_code == 200

        if index == 4:
            unlocked_at_five = {
                item["code"]: item["unlocked"]
                for item in api_client.get("/api/achievements").json()
            }
            assert unlocked_at_five["first_step"] is True
            assert unlocked_at_five["on_fire"] is True
            assert unlocked_at_five["productivity_master"] is False
        if index == 8:
            at_ninety_xp = {
                item["code"]: item["unlocked"]
                for item in api_client.get("/api/achievements").json()
            }
            assert at_ninety_xp["new_level"] is False
        if index == 9:
            at_one_hundred_xp = {
                item["code"]: item["unlocked"]
                for item in api_client.get("/api/achievements").json()
            }
            assert at_one_hundred_xp["new_level"] is True
            assert api_client.get("/api/profile").json()["level"] == 2

    profile = api_client.get("/api/profile").json()
    assert profile == {
        "user_id": 1,
        "xp": 250,
        "level": 3,
        "current_level_xp": 50,
        "next_level_xp": 100,
        "completed_tasks": 25,
    }

    achievements = api_client.get("/api/achievements").json()
    assert len(achievements) == 4
    assert all(item["unlocked"] for item in achievements)
    assert all(item["unlocked_at"] is not None for item in achievements)


def test_habit_create_completion_history_and_daily_repeat(
    api_client,
    monkeypatch,
):
    from datetime import date, timedelta

    from backend.app import database as database_module

    current_day = date.today()

    monkeypatch.setattr(database_module, "today", lambda: current_day)

    created = api_client.post(
        "/api/habits",
        json={"title": "  Читать  ", "description": "  каждый день  "},
    )
    assert created.status_code == 201
    habit = created.json()
    assert habit["title"] == "Читать"
    assert habit["description"] == "каждый день"
    assert habit["completed_today"] is False
    assert habit["streak"] == 0
    assert habit["total_completions"] == 0

    habit_id = habit["id"]
    assert api_client.get("/api/habits").json()[0]["id"] == habit_id
    assert api_client.get("/api/profile").json()["xp"] == 0

    completed = api_client.post(f"/api/habits/{habit_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["xp_awarded_now"] == 5
    assert completed.json()["already_completed"] is False
    assert completed.json()["habit"]["completed_today"] is True
    assert completed.json()["habit"]["streak"] == 1
    assert completed.json()["habit"]["total_completions"] == 1
    assert api_client.get("/api/profile").json()["xp"] == 5
    assert api_client.get(
        f"/api/habits/{habit_id}/history"
    ).json() == [
        {"completed_date": current_day.isoformat(), "xp_awarded": 1}
    ]

    current_day += timedelta(days=1)
    next_day = api_client.post(f"/api/habits/{habit_id}/complete")
    assert next_day.status_code == 200
    assert next_day.json()["xp_awarded_now"] == 5
    assert next_day.json()["habit"]["completed_today"] is True
    assert next_day.json()["habit"]["streak"] == 2
    assert next_day.json()["habit"]["total_completions"] == 2
    assert api_client.get("/api/profile").json()["xp"] == 10

    repeated = api_client.post(f"/api/habits/{habit_id}/complete")
    assert repeated.status_code == 200
    assert repeated.json()["xp_awarded_now"] == 0
    assert repeated.json()["already_completed"] is True
    assert repeated.json()["habit"]["total_completions"] == 2
    assert api_client.get("/api/profile").json()["xp"] == 10
    assert api_client.get("/api/habits").json()[0]["completed_today"] is True
    assert api_client.get(
        f"/api/habits/{habit_id}/history?limit=1"
    ).json() == [
        {"completed_date": current_day.isoformat(), "xp_awarded": 1}
    ]
    assert api_client.delete(f"/api/habits/{habit_id}").status_code == 200
    assert api_client.get(
        f"/api/habits/{habit_id}/history"
    ).status_code == 404
    assert api_client.get("/api/profile").json()["xp"] == 10


def test_habit_validation_and_delete(api_client):
    for payload in (
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 121},
        {"title": "Valid", "description": "x" * 501},
    ):
        assert api_client.post("/api/habits", json=payload).status_code == 422

    habit_id = api_client.post(
        "/api/habits",
        json={"title": "Удалить"},
    ).json()["id"]

    assert api_client.delete(f"/api/habits/{habit_id}").status_code == 200
    assert api_client.get("/api/habits").json() == []
    assert api_client.delete(f"/api/habits/{habit_id}").status_code == 404
    assert api_client.post(
        f"/api/habits/{habit_id}/complete"
    ).status_code == 404


def test_habit_edit_and_owner_history(api_client):
    habit_id = api_client.post(
        "/api/habits",
        json={"title": "Исходное", "description": "Старое"},
    ).json()["id"]
    updated = api_client.patch(
        f"/api/habits/{habit_id}",
        json={"title": " Новое ", "description": " Новое описание "},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Новое"
    assert updated.json()["description"] == "Новое описание"
    assert api_client.patch(
        f"/api/habits/{habit_id}",
        json={"title": " "},
    ).status_code == 422
    assert api_client.get(
        f"/api/habits/{habit_id}/history",
        headers=telegram_headers(user_id=2),
    ).status_code == 404
    other_user_headers = telegram_headers(user_id=2)
    assert api_client.get(
        "/api/habits",
        headers=other_user_headers,
    ).json() == []
    assert api_client.patch(
        f"/api/habits/{habit_id}",
        headers=other_user_headers,
        json={"title": "Чужое изменение"},
    ).status_code == 404
    assert api_client.post(
        f"/api/habits/{habit_id}/complete",
        headers=other_user_headers,
    ).status_code == 404
    assert api_client.delete(
        f"/api/habits/{habit_id}",
        headers=other_user_headers,
    ).status_code == 404
    assert api_client.get("/api/habits").json()[0]["title"] == "Новое"


def test_legacy_database_migration_preserves_existing_rows(
    tmp_path,
    monkeypatch,
):
    from backend.app import database as database_module

    legacy_database = tmp_path / "legacy.sqlite"
    with closing(sqlite3.connect(legacy_database)) as database:
        database.execute("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                is_completed INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        database.execute(
            "INSERT INTO tasks (title, description) VALUES (?, ?)",
            ("Сохранённая задача", "Не терять данные"),
        )
        database.execute("""
            CREATE TABLE profiles (
                user_id INTEGER PRIMARY KEY,
                xp INTEGER NOT NULL DEFAULT 0
            )
        """)
        database.execute(
            "INSERT INTO profiles (user_id, xp) VALUES (1, 70)"
        )
        database.commit()

    monkeypatch.setattr(database_module, "DATABASE_PATH", legacy_database)
    asyncio.run(database_module.init_db())

    with closing(sqlite3.connect(legacy_database)) as database:
        task = database.execute("""
            SELECT title, description, user_id, xp_awarded,
                   category, priority, deadline
            FROM tasks WHERE id = 1
        """).fetchone()
        profile = database.execute("""
            SELECT xp, completed_tasks FROM profiles WHERE user_id = 1
        """).fetchone()
        integrity = database.execute("PRAGMA integrity_check").fetchone()[0]

    assert task == (
        "Сохранённая задача",
        "Не терять данные",
        1,
        0,
        "Общее",
        "medium",
        None,
    )
    assert profile == (70, 0)
    assert integrity == "ok"
