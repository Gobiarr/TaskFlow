# TaskFlow Mini App

TaskFlow is a Telegram Mini App for tracking tasks and daily habits, earning
experience, and following levels and achievements. The interface is a compact
dark application with violet accents and a four-section bottom navigation.

## Features

- Create, edit, complete, filter, sort, and delete tasks.
- Categorize tasks, set priority and an optional deadline.
- Track daily habits, consecutive-day streaks, completion history, and habit
  edits/deletions.
- Earn 10 XP for a task's first completion and 5 XP for one habit completion
  per day. Re-completing a task does not award XP again.
- View profile level, completed-task count, and four achievement milestones.
- Verify Telegram Mini App `initData` when `TELEGRAM_BOT_TOKEN` is configured;
  task, habit, profile, and achievement data are scoped to that Telegram user.

## Stack and layout

- Python 3.13+, FastAPI, Pydantic, aiosqlite, SQLite, aiogram.
- HTML, CSS, and vanilla JavaScript; no frontend build step.

```text
backend/app/       FastAPI routes, configuration, and SQLite operations
bot/               Telegram bot entry point
frontend/          Mini App HTML, styles, and JavaScript
tests/             Isolated pytest API and SQLite tests
```

## Requirements

- Python 3.13 or newer.
- Telegram bot token for bot polling and verified Mini App authentication.
- A public HTTPS URL for the Mini App when opening it through Telegram.

## Setup

From the repository root in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`:

```dotenv
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBAPP_URL=https://your-domain.example/
TASKFLOW_ENV=production
TASKFLOW_ALLOW_UNAUTHENTICATED_LOCAL=false
TASKFLOW_DATABASE_PATH=taskflow.db
TASKFLOW_TIMEZONE=
```

Keep `.env` private. `TASKFLOW_TIMEZONE` is optional; when empty, the backend
uses the host's local time zone. On Windows, named IANA zones require system
time-zone data to be available to Python; if it is unavailable, leave the
setting empty to use the configured Windows local time zone.

`TELEGRAM_BOT_TOKEN` is required for verified Telegram authentication. Without
it, protected API routes return `503` by default. For local-only development,
set `TASKFLOW_ENV=development` and
`TASKFLOW_ALLOW_UNAUTHENTICATED_LOCAL=true`; this explicitly enables the
single-user development identity (user ID 1). The local mode must never be
enabled in a publicly reachable deployment.

## Run

Start the API and serve the Mini App from the same origin:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The root page is `http://127.0.0.1:8000/`; health check is
`http://127.0.0.1:8000/api/health`. For Telegram, deploy the API and static
frontend behind HTTPS and configure the resulting URL in BotFather and
`TELEGRAM_WEBAPP_URL`.

Run the Telegram bot in another terminal after configuring `.env`:

```powershell
.\.venv\Scripts\python.exe -m bot.main
```

The bot provides `/start` (opens the configured Mini App) and `/help`. The
Telegram token and public HTTPS deployment must be supplied by the operator;
no real Telegram messages are sent by the test suite.

## Tests

For test tooling, install the development requirements once:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests set `TASKFLOW_DATABASE_PATH` before application import, use a unique
temporary SQLite database, reset its data between tests, check SQLite
integrity, and remove the temporary directory after the run. They never use
the working `taskflow.db`.

## API

| Method | Route | Description |
|---|---|---|
| GET | `/api/health` | Service health |
| GET | `/api/profile` | XP, level, and completed task count |
| GET | `/api/achievements` | Achievement status and unlock dates |
| GET | `/api/tasks` | List tasks; `status`, `category`, and `sort` filters |
| POST | `/api/tasks` | Create task |
| PATCH | `/api/tasks/{task_id}` | Edit task |
| PATCH | `/api/tasks/{task_id}/complete` | Toggle task completion |
| DELETE | `/api/tasks/{task_id}` | Delete task |
| GET | `/api/habits` | List habits and current statistics |
| POST | `/api/habits` | Create habit |
| PATCH | `/api/habits/{habit_id}` | Edit habit |
| GET | `/api/habits/{habit_id}/history` | Recent completion dates |
| POST | `/api/habits/{habit_id}/complete` | Complete habit for the configured local day |
| DELETE | `/api/habits/{habit_id}` | Delete habit and its completion history |

Task list filters: `status=all|active|completed`, exact `category`, and
`sort=newest|oldest|deadline|priority`.

## Security and data

- Telegram requests are authenticated with Telegram's `initData` HMAC
  signature, an `auth_date` freshness check, and user-scoped database queries
  whenever `TELEGRAM_BOT_TOKEN` is configured. Protected API routes fail
  closed when the token is missing; unauthenticated access requires both
  explicit local development settings.
- The bot token belongs only in `.env` or the deployment secret manager. Do
  not commit secrets, user database files, virtual environments, or generated
  Python files.
- The SQLite schema is upgraded additively. Existing task rows are assigned to
  the legacy single-user profile (user ID 1) and kept; migrations do not drop
  or replace tables.
- Use a private persistent volume for `taskflow.db` in production and arrange
  separate backups. The project does not currently implement database
  encryption, rate limiting, or automated backups.
- Bot polling and public Telegram deployment need the operator's token and
  HTTPS domain and must be verified manually.
