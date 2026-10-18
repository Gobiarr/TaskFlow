
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.app.database import (
    complete_task,
    create_task,
    delete_task,
    get_all_tasks,
    get_achievements,
    get_profile,
    get_task_by_id,
    init_db,
    create_habit,
    get_habits,
    complete_habit,
    delete_habit,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
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


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str
    is_completed: bool
    created_at: str


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


class HabitResponse(BaseModel):
    id: int
    title: str
    description: str
    created_at: str
    completed_today: bool
    streak: int
    total_completions: int


def format_task(task: dict) -> dict:
    return {
        "id": task["id"],
        "title": task["title"],
        "description": task["description"],
        "is_completed": bool(task["is_completed"]),
        "created_at": str(task["created_at"]),
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
async def profile():
    user = await get_profile()
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
async def list_achievements():
    return await get_achievements()


@app.get("/api/tasks", response_model=list[TaskResponse])
async def list_tasks():
    tasks = await get_all_tasks()
    return [format_task(task) for task in tasks]


@app.post(
    "/api/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_task(task_data: TaskCreate):
    title = task_data.title.strip()

    if not title:
        raise HTTPException(
            status_code=422,
            detail="Название задачи не может быть пустым",
        )

    task_id = await create_task(
        title=title,
        description=task_data.description.strip(),
    )

    task = await get_task_by_id(task_id)

    if task is None:
        raise HTTPException(
            status_code=500,
            detail="Не удалось получить созданную задачу",
        )

    return format_task(task)


@app.patch("/api/tasks/{task_id}/complete", response_model=TaskResponse)
async def toggle_task(task_id: int):
    updated = await complete_task(task_id)

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Задача не найдена",
        )

    task = await get_task_by_id(task_id)
    return format_task(task)


@app.delete("/api/tasks/{task_id}")
async def remove_task(task_id: int):
    deleted = await delete_task(task_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Задача не найдена",
        )

    return {"message": "Задача удалена", "id": task_id}


@app.get("/api/habits", response_model=list[HabitResponse])
async def list_habits():
    habits = await get_habits()
    return [format_habit(habit) for habit in habits]


@app.post(
    "/api/habits",
    response_model=HabitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_habit(habit_data: HabitCreate):
    title = habit_data.title.strip()

    if not title:
        raise HTTPException(
            status_code=422,
            detail="Название привычки не может быть пустым",
        )

    habit = await create_habit(
        title=title,
        description=habit_data.description.strip(),
    )

    if habit is None:
        raise HTTPException(
            status_code=500,
            detail="Не удалось создать привычку",
        )

    return format_habit(habit)


@app.post("/api/habits/{habit_id}/complete")
async def finish_habit(habit_id: int):
    result = await complete_habit(habit_id)

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
async def remove_habit(habit_id: int):
    deleted = await delete_habit(habit_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Привычка не найдена",
        )

    return {"message": "Привычка удалена", "id": habit_id}


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")
