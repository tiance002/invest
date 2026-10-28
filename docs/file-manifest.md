# 本轮新增文件清单

初始仓库为空，因此以下均为本轮新增文件；没有修改或删除已有业务文件。实现过程中对新增文件的修正已包含在最终版本。

共 94 个交付文件。依赖目录、编译产物、运行日志、PID、临时本机数据库和工具工作配置被 Git 忽略，不计入清单。

## 分组统计

| 分组 | 文件数 |
|---|---:|
| `根目录` | 4 |
| `.planning` | 3 |
| `artifacts` | 16 |
| `backend` | 43 |
| `docs` | 7 |
| `frontend` | 16 |
| `scripts` | 5 |

## 根目录

- `.env.example`
- `.gitignore`
- `README.md`
- `compose.yaml`

## .planning

- `.planning/phase-one/findings.md`
- `.planning/phase-one/progress.md`
- `.planning/phase-one/task_plan.md`

## artifacts

- `artifacts/backend-tests.xml`
- `artifacts/backend-versions.json`
- `artifacts/browser-inspection.json`
- `artifacts/browser-verification.json`
- `artifacts/database-snapshot.json`
- `artifacts/demo-failure.png`
- `artifacts/demo-initial-dom.html`
- `artifacts/demo-initial.png`
- `artifacts/demo-mobile.png`
- `artifacts/demo-result.png`
- `artifacts/demo-retry.png`
- `artifacts/demo-timeout.png`
- `artifacts/demo-trace.png`
- `artifacts/frontend-tests.xml`
- `artifacts/runtime-lifecycle.json`
- `artifacts/runtime-verification.json`

## backend

- `backend/.env.example`
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/0001_phase_one.py`
- `backend/app/__init__.py`
- `backend/app/agents/__init__.py`
- `backend/app/agents/model.py`
- `backend/app/analysis/__init__.py`
- `backend/app/analysis/schemas.py`
- `backend/app/api/__init__.py`
- `backend/app/api/routes.py`
- `backend/app/data/__init__.py`
- `backend/app/data/evidence.py`
- `backend/app/decisions/__init__.py`
- `backend/app/decisions/synthesis.py`
- `backend/app/discovery/__init__.py`
- `backend/app/discovery/validation.py`
- `backend/app/evaluation/__init__.py`
- `backend/app/evaluation/models.py`
- `backend/app/infrastructure/__init__.py`
- `backend/app/infrastructure/config.py`
- `backend/app/infrastructure/db.py`
- `backend/app/infrastructure/errors.py`
- `backend/app/infrastructure/models.py`
- `backend/app/infrastructure/notifications.py`
- `backend/app/main.py`
- `backend/app/orchestration/__init__.py`
- `backend/app/orchestration/store.py`
- `backend/app/orchestration/workflow.py`
- `backend/app/portfolio/__init__.py`
- `backend/app/rsi_lab/__init__.py`
- `backend/app/rsi_lab/models.py`
- `backend/app/worker.py`
- `backend/pyproject.toml`
- `backend/tests/conftest.py`
- `backend/tests/test_api.py`
- `backend/tests/test_concurrency.py`
- `backend/tests/test_graph_unit.py`
- `backend/tests/test_infrastructure.py`
- `backend/tests/test_validation.py`
- `backend/tests/test_workflow.py`
- `backend/uv.lock`

## docs

- `docs/api-contract.md`
- `docs/architecture.md`
- `docs/file-manifest.md`
- `docs/next-steps.md`
- `docs/repository-audit.md`
- `docs/runtime-notes.md`
- `docs/verification.md`

## frontend

- `frontend/.env.example`
- `frontend/.gitignore`
- `frontend/index.html`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/public/favicon.svg`
- `frontend/src/App.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api.test.ts`
- `frontend/src/api.ts`
- `frontend/src/main.tsx`
- `frontend/src/styles.css`
- `frontend/src/test-setup.ts`
- `frontend/src/types.ts`
- `frontend/tsconfig.json`
- `frontend/vite.config.ts`

## scripts

- `scripts/browser_demo.py`
- `scripts/qa-requirements.txt`
- `scripts/start-dev.ps1`
- `scripts/stop-dev.ps1`
- `scripts/verify_runtime.py`

## 本机生成且保留的内容

- `backend/.venv`、`frontend/node_modules`、`frontend/dist`：依赖及构建结果。
- `.runtime`：本项目进程状态、日志、浏览器 QA 环境；临时初始化的原生 PostgreSQL 目录已停止并保留，最终运行使用 Docker。
- Docker 数据卷 `investment-thesis-arena-postgres-data`：持久任务、结果和运行记录。Redis `/data` 使用 tmpfs。
- `.serena`：工具工作配置，不属于应用源码。

未创建远程仓库、提交、PR 或发布部署。
