
from contextlib import asynccontextmanager
from datetime import date
import hashlib
import hmac
import json
import os
import time
from typing import Literal
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.app.config import PROJECT_ROOT
from backend.app.database import (
    complete_task,
    create_task,
    delete_task,
    get_all_tasks,
    get_achievements,
    get_profile,
    get_task_by_id,
    get_habit_by_id,
    init_db,
    create_habit,
    get_habits,
    complete_habit,
    delete_habit,
    get_habit_history,
    update_habit,
    update_task,
)

FRONTEND_DIR = PROJECT_ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="TaskFlow API",
    description="API приложения TaskFlow Mini App",
    version="0.5.0",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static",
)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    category: str = Field(default="Общее", min_length=1, max_length=50)
    priority: Literal["low", "medium", "high"] = "medium"
    deadline: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    priority: Literal["low", "medium", "high"] | None = None
    deadline: date | None = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str
    is_completed: bool
    created_at: str
    category: str
    priority: str
    deadline: str | None


class ProfileResponse(BaseModel):
    user_id: int
    xp: int
    level: int
    current_level_xp: int
    next_level_xp: int
    completed_tasks: int


class AchievementResponse(BaseModel):
    code: str
    title: str
    description: str
    icon: str
    unlocked: bool
    unlocked_at: str | None


class HabitCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class HabitUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class HabitResponse(BaseModel):
    id: int
    title: str
    description: str
    created_at: str
    completed_today: bool
    streak: int
    total_completions: int


def _validated_user_id(request: Request) -> int:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        local_auth_enabled = (
            os.environ.get("TASKFLOW_ENV", "production").lower()
            == "development"
            and os.environ.get(
                "TASKFLOW_ALLOW_UNAUTHENTICATED_LOCAL", ""
            ).lower()
            == "true"
        )
        if local_auth_enabled:
            return 1
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Telegram authentication is not configured; "
                "protected API is unavailable"
            ),
        )

    init_data = request.headers.get("X-Telegram-Init-Data", "")
    try:
        pairs = parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
        )
        values = dict(pairs)
        if len(values) != len(pairs):
            raise ValueError("Duplicate Telegram field")
        received_hash = values.pop("hash")
        auth_date = int(values["auth_date"])
        user = json.loads(values["user"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется корректная авторизация Telegram",
        ) from None

    if (
        len(received_hash) != 64
        or any(character not in "0123456789abcdef" for character in received_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректная подпись Telegram",
        )

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(received_hash, expected_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Подпись Telegram недействительна",
        )

    if auth_date > time.time() + 60 or time.time() - auth_date > 86400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Данные авторизации Telegram устарели",
        )

    user_id = user.get("id") if isinstance(user, dict) else None
    if (
        not isinstance(user_id, int)
        or isinstance(user_id, bool)
        or user_id < 1
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="В данных Telegram отсутствует корректный пользователь",
        )
    return user_id


def format_task(task: dict) -> dict:
    return {
        "id": task["id"],
        "title": task["title"],
        "description": task["description"],
        "is_completed": bool(task["is_completed"]),
        "created_at": str(task["created_at"]),
        "category": task["category"],
        "priority": task["priority"],
        "deadline": task["deadline"],
    }


def format_habit(habit: dict) -> dict:
    return {
        "id": habit["id"],
        "title": habit["title"],
        "description": habit["description"],
        "created_at": str(habit["created_at"]),
        "completed_today": bool(habit["completed_today"]),
        "streak": habit["streak"],
        "total_completions": habit["total_completions"],
    }


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "application": "TaskFlow"}


@app.get("/api/profile", response_model=ProfileResponse)
async def profile(request: Request):
    user_id = _validated_user_id(request)
    user = await get_profile(user_id)
    xp = user["xp"]

    return {
        "user_id": user["user_id"],
        "xp": xp,
        "level": xp // 100 + 1,
        "current_level_xp": xp % 100,
        "next_level_xp": 100,
        "completed_tasks": user["completed_tasks"],
    }


@app.get("/api/achievements", response_model=list[AchievementResponse])
async def list_achievements(request: Request):
    return await get_achievements(_validated_user_id(request))


@app.get("/api/tasks", response_model=list[TaskResponse])
async def list_tasks(
    request: Request,
    category: str | None = None,
    task_status: Literal["all", "active", "completed"] = Query(
        default="all",
        alias="status",
    ),
    sort: Literal["newest", "oldest", "deadline", "priority"] = "newest",
):
    if category is not None and not category.strip():
        raise HTTPException(
            status_code=422,
            detail="Категория не может быть пустой",
        )
    tasks = await get_all_tasks(
        _validated_user_id(request),
        category.strip() if category else None,
        task_status,
        sort,
    )
    return [format_task(task) for task in tasks]


@app.post(
    "/api/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_task(task_data: TaskCreate, request: Request):
    title = task_data.title.strip()

    if not title:
        raise HTTPException(
            status_code=422,
            detail="Название задачи не может быть пустым",
        )

    category = task_data.category.strip()
    if not category:
        raise HTTPException(
            status_code=422,
            detail="Категория не может быть пустой",
        )

    task_id = await create_task(
        title=title,
        description=task_data.description.strip(),
        user_id=_validated_user_id(request),
        category=category,
        priority=task_data.priority,
        deadline=task_data.deadline.isoformat() if task_data.deadline else None,
    )

    task = await get_task_by_id(task_id, _validated_user_id(request))

    if task is None:
        raise HTTPException(
            status_code=500,
            detail="Не удалось получить созданную задачу",
        )

    return format_task(task)


@app.patch("/api/tasks/{task_id}", response_model=TaskResponse)
async def edit_task(
    task_id: int,
    task_data: TaskUpdate,
    request: Request,
):
    updates = {}
    for field in ("title", "description", "category", "priority", "deadline"):
        if field not in task_data.model_fields_set:
            continue
        value = getattr(task_data, field)
        if field != "deadline" and value is None:
            raise HTTPException(
                status_code=422,
                detail=f"Поле {field} не может быть пустым",
            )
        if field in {"title", "description", "category"} and value is not None:
            value = value.strip()
            if field in {"title", "category"} and not value:
                raise HTTPException(
                    status_code=422,
                    detail="Название и категория не могут быть пустыми",
                )
        if field == "deadline":
            value = value.isoformat() if value is not None else None
        updates[field] = value

    task = await update_task(
        task_id,
        _validated_user_id(request),
        updates,
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return format_task(task)


@app.patch("/api/tasks/{task_id}/complete", response_model=TaskResponse)
async def toggle_task(task_id: int, request: Request):
    user_id = _validated_user_id(request)
    updated = await complete_task(task_id, user_id)

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Задача не найдена",
        )

    task = await get_task_by_id(task_id, user_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return format_task(task)


@app.delete("/api/tasks/{task_id}")
async def remove_task(task_id: int, request: Request):
    deleted = await delete_task(task_id, _validated_user_id(request))

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Задача не найдена",
        )

    return {"message": "Задача удалена", "id": task_id}


@app.get("/api/habits", response_model=list[HabitResponse])
async def list_habits(request: Request):
    habits = await get_habits(_validated_user_id(request))
    return [format_habit(habit) for habit in habits]


@app.post(
    "/api/habits",
    response_model=HabitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_habit(habit_data: HabitCreate, request: Request):
    title = habit_data.title.strip()

    if not title:
        raise HTTPException(
            status_code=422,
            detail="Название привычки не может быть пустым",
        )

    habit = await create_habit(
        title=title,
        description=habit_data.description.strip(),
        user_id=_validated_user_id(request),
    )

    if habit is None:
        raise HTTPException(
            status_code=500,
            detail="Не удалось создать привычку",
        )

    return format_habit(habit)


@app.patch("/api/habits/{habit_id}")
async def edit_habit(
    habit_id: int,
    habit_data: HabitUpdate,
    request: Request,
):
    updates = {}
    for field in ("title", "description"):
        if field not in habit_data.model_fields_set:
            continue
        value = getattr(habit_data, field)
        if value is None:
            raise HTTPException(
                status_code=422,
                detail=f"Поле {field} не может быть пустым",
            )
        if value is not None:
            value = value.strip()
            if field == "title" and not value:
                raise HTTPException(
                    status_code=422,
                    detail="Название привычки не может быть пустым",
                )
        updates[field] = value

    habit = await update_habit(
        habit_id,
        _validated_user_id(request),
        updates,
    )
    if habit is None:
        raise HTTPException(status_code=404, detail="Привычка не найдена")
    return format_habit(habit)


@app.get("/api/habits/{habit_id}/history")
async def habit_history(
    habit_id: int,
    request: Request,
    limit: int = Query(default=30, ge=1, le=365),
):
    user_id = _validated_user_id(request)
    habit = await get_habit_by_id(habit_id, user_id)
    if habit is None:
        raise HTTPException(status_code=404, detail="Привычка не найдена")
    return await get_habit_history(habit_id, user_id, limit)


@app.post("/api/habits/{habit_id}/complete")
async def finish_habit(habit_id: int, request: Request):
    user_id = _validated_user_id(request)
    result = await complete_habit(habit_id, user_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Привычка не найдена",
        )

    return {
        **result,
        "habit": format_habit(result["habit"]),
    }


@app.delete("/api/habits/{habit_id}")
async def remove_habit(habit_id: int, request: Request):
    deleted = await delete_habit(habit_id, _validated_user_id(request))

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Привычка не найдена",
        )

    return {"message": "Привычка удалена", "id": habit_id}


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")
