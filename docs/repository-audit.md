# 仓库初始审查

审查日期：2026-10-28，Asia/Shanghai。

`D:\Investment Thesis Arena` 初始为空目录；包含隐藏项的目录枚举及 `rg --files` 均未发现业务文件。初始 `git status` 返回 `fatal: not a git repository`，随后为本轮新增文件初始化 Git，未导入或覆盖其他项目。

| 检查项 | 初始结果 | 实施决定 |
|---|---|---|
| 前端、后端及可复用组件 | 无 | 新建 React/TypeScript 与 FastAPI 模块化单体 |
| 依赖、锁文件、运行脚本 | 无 | 分别建立 Python 与 npm 依赖及可复现启动方式 |
| 数据库、迁移、用户数据 | 仓库中无相关文件 | 使用独立 Compose 项目和 PostgreSQL 命名卷 |
| 测试与 CI | 无 | 增加 API、工作流、故障与浏览器验证 |
| Git 历史 | 无 | 初始化本地 Git；本轮不创建远程仓库 |
| Python | 3.13.0 | 使用项目虚拟环境 |
| Node.js / npm | 24.18.0 / 11.16.0 | 使用 Vite，保留 npm lockfile |
| Docker CLI / Compose | 29.8.0 / 5.5.1 | PostgreSQL、Redis 使用容器 |
| Docker 引擎 | 初始未运行，Linux engine named pipe 不存在 | 启动已安装 Docker Desktop 后验证容器 |
| psql / redis-server | PATH 中不存在 | 使用容器客户端与 Python 客户端验证 |

不存在需要提交确认的技术栈冲突。本轮未删除已有代码、配置、数据库或用户数据。宿主机其他项目、容器与数据不属于本轮范围。

用户随后要求扩大本机检查，发现 Windows 服务 `study-plan-postgresql` 正在运行，程序位于 `E:\pgsql\bin`，版本 16.4，数据目录 `E:\pgsql\data`；`pg_isready` 确认 `127.0.0.1:5432` 接受连接。此前 PATH 检查不能证明未安装，本次已纠正该认识。在 Windows 服务、运行进程、常用端口、检查过的安装目录和 WSL Ubuntu 软件包中未发现原生 Redis；Docker 存在其他项目的 Redis 镜像与已停止容器。

用户最终明确选择：PostgreSQL 和 Redis 都放入 Docker，使用易读的容器名称并归入同一个 Compose 项目组。因此本项目使用 `investment-thesis-arena` 项目组，容器为 `investment-thesis-arena-postgres`、`investment-thesis-arena-redis`。PostgreSQL 映射到 55433，避开现有 5432 及另一个已停止项目历史使用的 55432。
