from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.db import SessionLocal
from app.infrastructure.notifications import Notifications
from app.orchestration.store import TaskStore


def create_app(settings: Settings | None = None, sessions=None, notifications=None) -> FastAPI:
    settings = settings or get_settings()
    sessions = sessions or SessionLocal
    app = FastAPI(title="Investment Thesis Arena — MOCK ONLY", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )
    app.state.store = TaskStore(sessions, settings)
    app.state.notifications = notifications or Notifications(settings.redis_url)
    app.include_router(router)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request: Request, _exc: SQLAlchemyError):
        return JSONResponse(status_code=503, content={"detail": "数据库暂不可用；请保留原幂等键后重试。"})

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, _exc: Exception):
        return JSONResponse(status_code=500, content={"detail": "请求未能完成；请保留原幂等键后重试。"})

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "mode": "mock"}

    @app.get("/readyz")
    def readyz():
        postgres = False
        try:
            with sessions() as session:
                session.execute(text("SELECT 1 FROM tasks LIMIT 0"))
                postgres = True
        except SQLAlchemyError:
            pass
        redis = app.state.notifications.healthy()
        body = {
            "status": "ok" if postgres and redis else "degraded" if postgres else "unavailable",
            "mode": "mock",
            "postgres": "ok" if postgres else "unavailable",
            "redis": "ok" if redis else "degraded",
            "durable_polling": True,
        }
        return JSONResponse(status_code=200 if postgres else 503, content=body)

    return app


app = create_app()
