# Phase one architecture skeleton

## Goal
Deliver a running mock-only React/TypeScript + FastAPI + LangGraph + PostgreSQL + Redis + Python worker research loop. No real trading, financial accounts, or autonomous RSI.

## Current Phase
Phase one complete; no phase-two implementation started.

## Next Step
Deliver the running URLs, verification evidence and documentation, then stop.

### Phase 1: Audit and minimal design
**Status:** complete
- Empty workspace verified with hidden entries and rg; no code, config, data, tests, or Git history.
- Python 3.13.0, Node 24.18.0, npm 11.16.0, Docker CLI 29.8.0 / Compose 5.5.1 available.
- Docker desktop-linux engine is not running; runtime recovery required.

### Phase 2: Implement mock-only vertical slice
**Status:** complete
- API validation, durable jobs/runs, idempotency, retries, leases, errors.
- LangGraph deterministic researcher / challenger / synthesis.
- React UI with prominent simulated-data labeling and trace visibility.
- Alembic migration, PostgreSQL/Redis compose, bounded config.

### Phase 3: Run and verify
**Status:** complete
- Unit/API/workflow tests and real PostgreSQL/Redis integration.
- Build frontend, launch processes, browser submission and result retrieval.
- Duplicate submission, retry, failure, external timeout, Redis outage.

### Phase 4: Deliver evidence and documentation
**Status:** complete
- Audit, architecture/sequence diagrams, file manifest, startup/migration guide.
- Test evidence, real browser screenshots, explicit mocks and limitations.
- Stop at phase-one scope.

## Ownership
Root owns shared planning, integration QA, final documentation. Workers own only assigned paths and report technical findings in English. No competing planning files.

## Errors Encountered
- Initial git status: not a git repository; expected in empty directory, initialized Git.
- Docker engine named pipe absent; runtime worker to start installed Docker Desktop.
- Initial PATH-only database inventory incomplete; expanded Windows/WSL/Docker inspection found native PG16.4. Final explicit user decision remains Docker for both dependencies.
- PyPI/npm network resets slowed dependency installation; bounded retries completed. Frontend patched test-runner dependencies; npm audit now zero findings.
- Official PostgreSQL17 pull stalled; reused cached digest-pinned PostgreSQL16.15 container image, ordinary PostgreSQL only. User informed; both dependencies remain grouped in Docker as explicitly requested.
- Initial favicon404 fixed; final browser has zero console/page errors. FastAPI internal route test assertion updated to public OpenAPI.
- Process timestamp UTC conversion fixed by runtime worker; duplicate-start and full stop/start verified.
- Read-only DB snapshot during intentional lifecycle stop returned service unavailable; retried after lifecycle complete, verified no duplicates and no leftover test schemas.
