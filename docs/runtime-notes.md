# Local runtime

The Phase 1 development runtime keeps PostgreSQL and Redis in the isolated Docker Compose project `investment-thesis-arena` and runs the backend, worker, and frontend on the Windows host. It does not use or modify the pre-existing `study-plan-postgresql` Windows service or `E:\pgsql\data`.

## Endpoints

| Component | Address | Persistence |
| --- | --- | --- |
| PostgreSQL 16 (`pgvector/pgvector:pg16`, digest pinned; extension not enabled) | `127.0.0.1:55433` | Named volume `investment-thesis-arena-postgres-data` |
| Redis 7 (`redis:7-alpine`, digest pinned) | `127.0.0.1:56379` | Ephemeral queue data; `/data` uses tmpfs |
| FastAPI | `http://127.0.0.1:8000` | Host process |
| Vite | `http://127.0.0.1:5173` | Host process |

The checked-in values are local samples only: PostgreSQL user `arena`, password `arena_local`, and database `arena`. They are not production credentials.

## Start and stop

From PowerShell at the repository root:

```powershell
Copy-Item .env.example .env  # optional; only needed for overrides
.\scripts\start-dev.ps1
.\scripts\stop-dev.ps1
```

`start-dev.ps1` starts Docker Desktop if necessary, waits up to 60 seconds for the engine, starts healthy PostgreSQL and Redis containers, runs `uv sync --frozen --group dev`, applies Alembic migrations, runs `npm ci`, and launches the API, worker, and frontend as hidden processes. Use `-DependenciesOnly` to stop after PostgreSQL and Redis are healthy. Use `-SkipInstall` only after dependencies are synchronized; migrations still run.

Process metadata and stdout/stderr logs are stored under `.runtime`. The stop script verifies each recorded PID's start time and executable path before stopping its process tree, stops only the `investment-thesis-arena` PostgreSQL and Redis containers, and preserves the PostgreSQL named volume. It never runs `docker compose down` or deletes volumes. A previously initialized `.runtime/postgres-data` directory is preserved but is not used by the Docker runtime.

If a configured port is occupied by another process, startup stops with the owning PID instead of terminating it. Override local values in an untracked `.env` file when necessary.

