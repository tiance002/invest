import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.infrastructure.models import IdempotencyRequest, Task, TaskResult
from app.main import create_app
from app.orchestration.workflow import execute_claim

pytestmark = pytest.mark.integration


def submit(client, payload, key="submit-key-001"):
    response = client.post("/api/tasks", json=payload, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    return response.json()


def test_lifecycle_and_durable_before_wake(client, payload, store, notifications):
    def assert_committed(task_id):
        assert store.get(uuid.UUID(task_id))["status"] == "queued"
        notifications.calls.append(task_id)
        return False

    notifications.notify = assert_committed
    task = submit(client, payload)
    assert task["mode"] == "mock" and task["status"] == "queued"
    assert task["runs"] == [] and task["result"] is None
    assert notifications.calls == [task["id"]]
    claim = store.claim()
    assert client.get(f"/api/tasks/{task['id']}").json()["status"] == "running"
    asyncio.run(execute_claim(store, claim))
    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["status"] == "succeeded" and detail["attempt_count"] == 1
    assert detail["result"]["mode"] == "mock"
    assert len(detail["result"]["agent_outputs"]) == 2
    assert detail["runs"][0]["duration_ms"] >= 0
    assert [a["role"] for a in detail["runs"][0]["agent_runs"]] == ["researcher", "challenger"]
    for agent in detail["runs"][0]["agent_runs"]:
        assert agent["status"] == "succeeded" and agent["duration_ms"] >= 0
        assert agent["input"]["evidence"]["version"] == "mock-evidence-v1"
        assert agent["input_tokens"] is None and agent["cost_usd"] is None
    assert client.get("/api/tasks").json()["items"][0]["id"] == task["id"]
    assert client.get(f"/api/tasks/{uuid.uuid4()}").status_code == 404


def test_missing_key_invalid_payload_and_uuid(client, payload):
    assert client.post("/api/tasks", json=payload).status_code == 422
    assert client.post("/api/tasks", json=payload, headers={"Idempotency-Key": "short"}).status_code == 422
    response = client.post(
        "/api/tasks", json=payload | {"market": "HK"}, headers={"Idempotency-Key": "valid-key-001"}
    )
    assert response.status_code == 422
    assert client.get("/api/tasks/not-a-uuid").status_code == 422


def test_idempotency_is_immutable_and_payload_sensitive(client, payload, store, sessions, notifications):
    task = submit(client, payload)
    replay = submit(client, payload)
    assert replay["id"] == task["id"]
    assert len(notifications.calls) == 1
    response = client.post(
        "/api/tasks", json=payload | {"horizon_days": 5}, headers={"Idempotency-Key": "submit-key-001"}
    )
    assert response.status_code == 409
    asyncio.run(execute_claim(store, store.claim()))
    assert submit(client, payload)["status"] == "succeeded"
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 1
        assert session.scalar(select(func.count()).select_from(IdempotencyRequest)) == 1
        assert session.scalar(select(func.count()).select_from(TaskResult)) == 1
    assert (
        client.post(
            f"/api/tasks/{task['id']}/retry", headers={"Idempotency-Key": "new-retry-key"}
        ).status_code
        == 409
    )


def test_same_key_concurrent_requests_create_one_task(sessions, settings, notifications, payload):
    def concurrent_submit(_):
        with TestClient(create_app(settings, sessions, notifications)) as client:
            return submit(client, payload)["id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(concurrent_submit, range(8)))
    assert len(set(ids)) == 1
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 1


def test_health_and_redis_degraded_readiness(client):
    assert client.get("/healthz").json() == {"status": "ok", "mode": "mock"}
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["postgres"] == "ok" and response.json()["redis"] == "degraded"


def test_key_cannot_cross_actions_or_tasks(client, payload, store):
    first = submit(client, payload | {"scenario": "fail_once"}, "cross-action-key")
    asyncio.run(execute_claim(store, store.claim()))
    retry_url = f"/api/tasks/{first['id']}/retry"
    assert client.post(retry_url, headers={"Idempotency-Key": "cross-action-key"}).status_code == 409
    assert client.post(retry_url, headers={"Idempotency-Key": "shared-retry-key"}).status_code == 202
    second = submit(client, payload | {"scenario": "timeout"}, "second-create-key")
    conflict = client.post(
        f"/api/tasks/{second['id']}/retry", headers={"Idempotency-Key": "shared-retry-key"}
    )
    assert conflict.status_code == 409
    assert client.get(f"/api/tasks/{second['id']}").json()["attempt_count"] == 0
