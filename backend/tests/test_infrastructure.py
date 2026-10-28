import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.infrastructure.db import make_engine
from app.infrastructure.notifications import Notifications
from app.main import create_app
from app.orchestration.workflow import execute_claim


@pytest.mark.integration
def test_redis_outage_does_not_lose_durable_task(sessions, settings, store, payload):
    outage = Notifications("redis://127.0.0.1:1/0")
    with TestClient(create_app(settings, sessions, outage)) as client:
        response = client.post("/api/tasks", json=payload, headers={"Idempotency-Key": "redis-outage-key"})
        assert response.status_code == 202
        assert client.get("/readyz").json()["redis"] == "degraded"
        claim = store.claim()  # The worker's database poll needs no Redis payload.
        asyncio.run(execute_claim(store, claim))
        assert client.get(f"/api/tasks/{response.json()['id']}").json()["status"] == "succeeded"


@pytest.mark.integration
def test_reserved_offline_schema_exists_without_runtime_routes(sessions, settings, notifications):
    with sessions() as session:
        tables = set(inspect(session.connection()).get_table_names())
    assert {
        "evaluation_runs",
        "rsi_proposals",
        "rsi_experiments",
        "rsi_evaluations",
        "rsi_approvals",
        "rsi_rollbacks",
    } <= tables
    app = create_app(settings, sessions, notifications)
    assert all("rsi" not in path and "evaluation" not in path for path in app.openapi()["paths"])


def test_database_unavailable_returns_safe_errors(settings, notifications, payload):
    from sqlalchemy.orm import sessionmaker

    engine = make_engine("postgresql+psycopg://arena:secret_for_test@127.0.0.1:1/arena")
    try:
        with TestClient(create_app(settings, sessionmaker(engine), notifications)) as client:
            response = client.get("/readyz")
            assert response.status_code == 503 and "secret_for_test" not in response.text
            response = client.post("/api/tasks", json=payload, headers={"Idempotency-Key": "db-outage-key"})
            assert response.status_code == 503 and "secret_for_test" not in response.text
    finally:
        engine.dispose()
