
import os
import aiosqlite
from pathlib import Path
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.app.config import PROJECT_ROOT

DATABASE_PATH = Path(
    os.environ.get(
        "TASKFLOW_DATABASE_PATH",
        str(PROJECT_ROOT / "taskflow.db"),
    )
).expanduser()
_timezone_name = os.environ.get("TASKFLOW_TIMEZONE")
try:
    APP_TIMEZONE = ZoneInfo(_timezone_name) if _timezone_name else None
except ZoneInfoNotFoundError as error:
    raise RuntimeError(
        f"Unknown TASKFLOW_TIMEZONE: {_timezone_name}"
    ) from error

TEST_USER_ID = 1
XP_PER_TASK = 10
XP_PER_HABIT = 5
DEFAULT_TASK_CATEGORY = "Общее"

ACHIEVEMENTS = [
    {
        "code": "first_step",
        "title": "Первый шаг",
        "description": "Выполни первую задачу",
        "icon": "🥇",
    },
    {
        "code": "on_fire",
        "title": "В ударе",
        "description": "Выполни 5 разных задач",
        "icon": "🔥",
    },
    {
        "code": "productivity_master",
        "title": "Мастер продуктивности",
        "description": "Выполни 25 разных задач",
        "icon": "💎",
    },
    {
        "code": "new_level",
        "title": "Новый уровень",
        "description": "Набери 100 XP",
        "icon": "⚡",
    },
]


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                is_completed INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                xp_awarded INTEGER NOT NULL DEFAULT 0,
                category TEXT NOT NULL DEFAULT 'Общее',
                priority TEXT NOT NULL DEFAULT 'medium',
                deadline TEXT
            )
        """)

        async with db.execute("PRAGMA table_info(tasks)") as cursor:
            columns = await cursor.fetchall()

        column_names = {column[1] for column in columns}

        for column_name, definition in {
            "user_id": "INTEGER NOT NULL DEFAULT 1",
            "xp_awarded": "INTEGER NOT NULL DEFAULT 0",
            "category": "TEXT NOT NULL DEFAULT 'Общее'",
            "priority": "TEXT NOT NULL DEFAULT 'medium'",
            "deadline": "TEXT",
        }.items():
            if column_name not in column_names:
                await db.execute(
                    f"ALTER TABLE tasks ADD COLUMN {column_name} {definition}"
                )

        await db.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                xp INTEGER NOT NULL DEFAULT 0,
                completed_tasks INTEGER NOT NULL DEFAULT 0
            )
        """)

        async with db.execute("PRAGMA table_info(profiles)") as cursor:
            profile_columns = await cursor.fetchall()

        profile_column_names = {
            column[1] for column in profile_columns
        }

        if "completed_tasks" not in profile_column_names:
            await db.execute("""
                ALTER TABLE profiles
                ADD COLUMN completed_tasks INTEGER NOT NULL DEFAULT 0
            """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                unlocked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, code)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS habit_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                completed_date TEXT NOT NULL,
                xp_awarded INTEGER NOT NULL DEFAULT 0,
                UNIQUE(habit_id, completed_date)
            )
        """)

        await db.execute("""
            INSERT OR IGNORE INTO profiles (
                user_id, xp, completed_tasks
            )
            VALUES (?, 0, 0)
        """, (TEST_USER_ID,))

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_user_status
            ON tasks (user_id, is_completed)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_habits_user
            ON habits (user_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_habit_completions_user_date
            ON habit_completions (user_id, completed_date)
        """)
        await db.commit()


def today():
    if APP_TIMEZONE is None:
        return datetime.now().astimezone().date()
    return datetime.now(APP_TIMEZONE).date()


async def get_all_tasks(
    user_id: int = TEST_USER_ID,
    category: str | None = None,
    status_filter: str = "all",
    sort: str = "newest",
):
    order_by = {
        "newest": "id DESC",
        "oldest": "id ASC",
        "deadline": "deadline IS NULL, deadline ASC, id DESC",
        "priority": (
            "CASE priority WHEN 'high' THEN 0 "
            "WHEN 'medium' THEN 1 ELSE 2 END, id DESC"
        ),
    }[sort]
    conditions = ["user_id = ?"]
    parameters: list[object] = [user_id]
    if category:
        conditions.append("category = ?")
        parameters.append(category)
    if status_filter == "active":
        conditions.append("is_completed = 0")
    elif status_filter == "completed":
        conditions.append("is_completed = 1")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(f"""
            SELECT id, title, description, is_completed, created_at,
                   category, priority, deadline
            FROM tasks
            WHERE {" AND ".join(conditions)}
            ORDER BY {order_by}
        """, parameters) as cursor:
            rows = await cursor.fetchall()

    return [dict(row) for row in rows]


async def create_task(
    title: str,
    description: str = "",
    user_id: int = TEST_USER_ID,
    category: str = DEFAULT_TASK_CATEGORY,
    priority: str = "medium",
    deadline: str | None = None,
):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO profiles (user_id) VALUES (?)",
            (user_id,),
        )
        cursor = await db.execute(
            """
            INSERT INTO tasks (
                user_id, title, description, category, priority, deadline
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, title, description, category, priority, deadline),
        )
        await db.commit()
        return cursor.lastrowid


async def get_task_by_id(task_id: int, user_id: int = TEST_USER_ID):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT id, title, description, is_completed, created_at,
                   category, priority, deadline
            FROM tasks
            WHERE id = ? AND user_id = ?
        """, (task_id, user_id)) as cursor:
            row = await cursor.fetchone()

    return dict(row) if row else None


async def update_task(task_id: int, user_id: int, updates: dict):
    if not updates:
        return await get_task_by_id(task_id, user_id)

    assignments = ", ".join(f"{column} = ?" for column in updates)
    values = [*updates.values(), task_id, user_id]
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            f"UPDATE tasks SET {assignments} WHERE id = ? AND user_id = ?",
            values,
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None

    return await get_task_by_id(task_id, user_id)


async def unlock_eligible_achievements(db, user_id: int = TEST_USER_ID):
    async with db.execute("""
        SELECT xp, completed_tasks
        FROM profiles
        WHERE user_id = ?
    """, (user_id,)) as cursor:
        profile = await cursor.fetchone()

    if profile is None:
        return

    xp = profile[0]
    completed_tasks = profile[1]

    conditions = {
        "first_step": completed_tasks >= 1,
        "on_fire": completed_tasks >= 5,
        "productivity_master": completed_tasks >= 25,
        "new_level": xp >= 100,
    }

    for achievement in ACHIEVEMENTS:
        if conditions[achievement["code"]]:
            await db.execute("""
                INSERT OR IGNORE INTO achievements (user_id, code)
                VALUES (?, ?)
            """, (user_id, achievement["code"]))


async def complete_task(task_id: int, user_id: int = TEST_USER_ID):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            "INSERT OR IGNORE INTO profiles (user_id) VALUES (?)",
            (user_id,),
        )

        async with db.execute("""
            SELECT is_completed, xp_awarded
            FROM tasks
            WHERE id = ? AND user_id = ?
        """, (task_id, user_id)) as cursor:
            task = await cursor.fetchone()

        if task is None:
            await db.rollback()
            return False

        if task["is_completed"]:
            await db.execute("""
                UPDATE tasks
                SET is_completed = 0
                WHERE id = ? AND user_id = ?
            """, (task_id, user_id))
        else:
            await db.execute("""
                UPDATE tasks
                SET is_completed = 1
                WHERE id = ? AND user_id = ?
            """, (task_id, user_id))

            if not task["xp_awarded"]:
                await db.execute("""
                    UPDATE profiles
                    SET xp = xp + ?,
                        completed_tasks = completed_tasks + 1
                    WHERE user_id = ?
                """, (XP_PER_TASK, user_id))

                await db.execute("""
                    UPDATE tasks
                    SET xp_awarded = 1
                    WHERE id = ? AND user_id = ?
                """, (task_id, user_id))

                await unlock_eligible_achievements(db, user_id)

        await db.commit()
        return True


async def delete_task(task_id: int, user_id: int = TEST_USER_ID):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_profile(user_id: int = TEST_USER_ID):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT user_id, xp, completed_tasks
            FROM profiles
            WHERE user_id = ?
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()

    return dict(row) if row else {
        "user_id": user_id,
        "xp": 0,
        "completed_tasks": 0,
    }


async def get_achievements(user_id: int = TEST_USER_ID):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT code, unlocked_at
            FROM achievements
            WHERE user_id = ?
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()

    unlocked = {row["code"]: row["unlocked_at"] for row in rows}

    return [
        {
            **achievement,
            "unlocked": achievement["code"] in unlocked,
            "unlocked_at": unlocked.get(achievement["code"]),
        }
        for achievement in ACHIEVEMENTS
    ]


def _habit_streak(completion_dates):
    completed = set(completion_dates)
    current_day = today()

    # Если привычка ещё не выполнена сегодня, серия может
    # продолжаться со вчерашнего дня.
    if current_day.isoformat() not in completed:
        current_day -= timedelta(days=1)

    streak = 0

    while current_day.isoformat() in completed:
        streak += 1
        current_day -= timedelta(days=1)

    return streak


async def get_habits(user_id: int = TEST_USER_ID):
    current_day = today().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT
                h.id,
                h.title,
                h.description,
                h.created_at,
                EXISTS(
                    SELECT 1
                    FROM habit_completions c
                    WHERE c.habit_id = h.id
                      AND c.user_id = h.user_id
                      AND c.completed_date = ?
                ) AS completed_today
            FROM habits h
            WHERE h.user_id = ?
            ORDER BY h.id DESC
        """, (current_day, user_id)) as cursor:
            rows = await cursor.fetchall()

        habits = []

        for row in rows:
            habit = dict(row)

            async with db.execute("""
                SELECT completed_date
                FROM habit_completions
                WHERE habit_id = ? AND user_id = ?
                ORDER BY completed_date DESC
            """, (habit["id"], user_id)) as cursor:
                completions = await cursor.fetchall()

            dates = [item["completed_date"] for item in completions]
            habit["completed_today"] = bool(habit["completed_today"])
            habit["streak"] = _habit_streak(dates)
            habit["total_completions"] = len(dates)

            habits.append(habit)

    return habits


async def create_habit(
    title: str,
    description: str = "",
    user_id: int = TEST_USER_ID,
):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO profiles (user_id) VALUES (?)",
            (user_id,),
        )
        cursor = await db.execute("""
            INSERT INTO habits (user_id, title, description)
            VALUES (?, ?, ?)
        """, (user_id, title, description))

        await db.commit()
        habit_id = cursor.lastrowid

    return await get_habit_by_id(habit_id, user_id)


async def get_habit_by_id(habit_id: int, user_id: int = TEST_USER_ID):
    habits = await get_habits(user_id)

    for habit in habits:
        if habit["id"] == habit_id:
            return habit

    return None


async def update_habit(habit_id: int, user_id: int, updates: dict):
    if not updates:
        return await get_habit_by_id(habit_id, user_id)

    assignments = ", ".join(f"{column} = ?" for column in updates)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            f"UPDATE habits SET {assignments} WHERE id = ? AND user_id = ?",
            [*updates.values(), habit_id, user_id],
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None

    return await get_habit_by_id(habit_id, user_id)


async def get_habit_history(
    habit_id: int,
    user_id: int,
    limit: int = 30,
):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("""
            SELECT c.completed_date, c.xp_awarded
            FROM habit_completions c
            JOIN habits h ON h.id = c.habit_id
            WHERE c.habit_id = ? AND c.user_id = ? AND h.user_id = ?
            ORDER BY c.completed_date DESC
            LIMIT ?
        """, (habit_id, user_id, user_id, limit)) as cursor:
            rows = await cursor.fetchall()

    return [
        {"completed_date": row[0], "xp_awarded": row[1]}
        for row in rows
    ]


async def complete_habit(habit_id: int, user_id: int = TEST_USER_ID):
    completion_date = today().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            "INSERT OR IGNORE INTO profiles (user_id) VALUES (?)",
            (user_id,),
        )

        async with db.execute("""
            SELECT id
            FROM habits
            WHERE id = ? AND user_id = ?
        """, (habit_id, user_id)) as cursor:
            habit = await cursor.fetchone()

        if habit is None:
            await db.rollback()
            return None

        async with db.execute("""
            SELECT id
            FROM habit_completions
            WHERE habit_id = ?
              AND user_id = ?
              AND completed_date = ?
        """, (habit_id, user_id, completion_date)) as cursor:
            existing = await cursor.fetchone()

        if existing:
            await db.commit()
            return {
                "habit": await get_habit_by_id(habit_id, user_id),
                "xp_awarded_now": 0,
                "already_completed": True,
            }

        await db.execute("""
            INSERT INTO habit_completions (
                habit_id, user_id, completed_date, xp_awarded
            )
            VALUES (?, ?, ?, 1)
        """, (habit_id, user_id, completion_date))

        await db.execute("""
            UPDATE profiles
            SET xp = xp + ?
            WHERE user_id = ?
        """, (XP_PER_HABIT, user_id))

        await unlock_eligible_achievements(db, user_id)
        await db.commit()

    return {
        "habit": await get_habit_by_id(habit_id, user_id),
        "xp_awarded_now": XP_PER_HABIT,
        "already_completed": False,
    }


async def delete_habit(habit_id: int, user_id: int = TEST_USER_ID):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")

        async with db.execute("""
            SELECT id
            FROM habits
            WHERE id = ? AND user_id = ?
        """, (habit_id, user_id)) as cursor:
            habit = await cursor.fetchone()

        if habit is None:
            await db.rollback()
            return False

        await db.execute("""
            DELETE FROM habit_completions
            WHERE habit_id = ? AND user_id = ?
        """, (habit_id, user_id))

        await db.execute("""
            DELETE FROM habits
            WHERE id = ? AND user_id = ?
        """, (habit_id, user_id))

        await db.commit()
        return True
