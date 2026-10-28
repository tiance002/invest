# Investment Thesis Arena

第一阶段：以 A 股研究请求为主、支持美股代码的个人投资研究工作流骨架。当前所有数据、研究和反方结论均为**模拟实现**，仅用于验证软件流程，不产生真实投资建议，不连接资金账户，不执行交易。

React + TypeScript 前端 → FastAPI → PostgreSQL 持久任务 → Python Worker → LangGraph 研究/反方/合并 → 前端结果与审计轨迹。Redis 用于任务唤醒，数据库轮询承担故障时的恢复路径。

## 本机启动

环境：Python 3.13+、uv、Node.js 22.12+、npm、Docker Desktop（Linux containers）、Docker Compose。Windows PowerShell 执行：

```powershell
Set-Location 'D:\Investment Thesis Arena'
.\scripts\start-dev.ps1
```

启动脚本会启动数据库容器、等待健康检查、同步锁定依赖、执行 Alembic 迁移，然后在后台启动 API、Worker、Vite。日志与进程记录位于 `.runtime`。可选的本地配置参考 `.env.example`；存在 `.env` 时不要覆盖，直接修改需要的字段。

已经安装依赖时：

```powershell
.\scripts\start-dev.ps1 -SkipInstall
```

| 组件 | 地址 / 名称 |
|---|---|
| 前端 | [http://127.0.0.1:5173](http://127.0.0.1:5173) |
| API 文档 | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| 存活 / 就绪检查 | `/healthz` / `/readyz` |
| Compose 项目组 | `investment-thesis-arena` |
| PostgreSQL | `investment-thesis-arena-postgres`，`127.0.0.1:55433` |
| PostgreSQL 数据卷 | `investment-thesis-arena-postgres-data` |
| Redis | `investment-thesis-arena-redis`，`127.0.0.1:56379` |

数据库默认的 `arena / arena_local / arena` 分别为本机开发用户名、样例密码、数据库名。实际验证版本为 PostgreSQL 16.15、Redis 7.4.12，两者镜像均固定 digest；PostgreSQL 镜像包含 pgvector 包，本轮未启用该扩展。不要把该配置当作公网部署配置。现有宿主机 PostgreSQL 的 5432 端口和数据保持独立。

```powershell
docker compose ps
.\scripts\stop-dev.ps1
```

停止脚本仅处理本项目记录的应用进程与 Compose 服务，保留数据卷。再次启动可读取已有任务。

## 分别启动与数据库迁移

只启动数据库依赖：

```powershell
docker compose up -d --wait postgres redis
```

后端终端（工作目录 `backend`）：

```powershell
uv sync --frozen --group dev
uv run --frozen alembic upgrade head
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Worker 使用另一个终端（工作目录 `backend`）：

```powershell
uv run --frozen python -m app.worker
```

前端终端（工作目录 `frontend`）：

```powershell
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

初始迁移为 `backend/alembic/versions/0001_phase_one.py`，通过 `alembic_version` 追踪。`uv run --frozen alembic current` 查看版本，`uv run --frozen alembic history` 查看历史。启动时只执行 upgrade，不自动重建表或删除数据。手动运行后端时环境配置从 `backend/.env` 或 `ARENA_*` 环境变量读取；根目录启动脚本会把根目录 `.env` 载入子进程。

## 使用与验证

浏览器输入市场、证券代码、研究周期与问题，点击“开始模拟研究”。默认周期为 3 个交易日，支持 1–20 日；周期是任务元数据，不代表已实现有效策略。支持正常、首次失败后重试恢复、持续超时三个模拟场景。

页面提供研究依据、疑点、双方结论、共识/分歧、证据引用，以及原始输入输出、运行版本、耗时与错误。刷新可恢复所选任务。内容不变时重复提交复用幂等键；有意新建同内容任务请点击“新任务”。

后端完整测试需要本项目 PostgreSQL 已运行。在 `backend` 执行：

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://arena:arena_local@127.0.0.1:55433/arena'
uv run --frozen pytest -q
uv run --frozen ruff check app tests alembic
```

集成测试在随机命名的 `arena_test_*` schema 中运行并清理自己的 schema，不删除业务表。未设置 `TEST_DATABASE_URL` 会跳过集成测试，不能作为完整验收。

前端在 `frontend` 执行 `npm test`、`npm run build`。整个系统运行后，在根目录执行：

```powershell
python scripts/verify_runtime.py --redis-outage --postgres-restart
```

该验收会创建模拟任务、检查并发重复提交/重试/超时，并短暂停止本项目 Redis 和 PostgreSQL 再恢复，核对持久化结果，结果写入 `artifacts/runtime-verification.json`。在本项目没有其他待处理任务时运行。

浏览器演示脚本使用 Python Playwright，可使用已安装 Edge：

```powershell
python -m venv .runtime/qa-venv
.\.runtime\qa-venv\Scripts\python.exe -m pip install -r scripts/qa-requirements.txt
.\.runtime\qa-venv\Scripts\python.exe scripts/browser_demo.py --browser-channel msedge
```

也可安装 Playwright Chromium 后使用默认浏览器：`python -m playwright install chromium`（在相同 QA 环境中运行）。截图和演示记录位于 `artifacts`。

## 文档

- [初始仓库与本机环境审查](docs/repository-audit.md)
- [目录职责、架构图、时序图和一致性设计](docs/architecture.md)
- [API 契约](docs/api-contract.md)
- [运行脚本说明](docs/runtime-notes.md)
- [验收结果与实际演示](docs/verification.md)
- [本轮文件清单](docs/file-manifest.md)
- [模拟功能、已知限制与下一阶段建议](docs/next-steps.md)
