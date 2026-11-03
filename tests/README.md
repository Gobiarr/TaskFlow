# Backend tests

The test configuration creates a temporary SQLite database and sets
`TASKFLOW_DATABASE_PATH` before importing the FastAPI app. It signs test
Telegram `initData` with a dummy token, so tests verify the authentication
boundary without using real credentials. Database tables are reset between
tests, SQLite integrity is checked after each test, and the temporary
directory is removed when pytest exits.

The suite covers API routes, task and habit CRUD, filtering, sorting, XP,
levels, achievements, daily habit history, Telegram user isolation, input
validation, and an additive migration from the earlier task/profile schema.
The backend does not currently have external Telegram dependencies at test
time; it does not start bot polling or send messages.

Run from the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The test suite never opens the working `taskflow.db`.
