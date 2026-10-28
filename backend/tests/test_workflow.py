import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.agents.model import DeterministicMockAdapter
from app.infrastructure.errors import WORKFLOW_FAILED
from app.orchestration.store import RequestConflict
from app.orchestration.workflow import execute_claim

pytestmark = pytest.mark.integration


def create(store, payload):
    return store.create(payload, "task-key-" + uuid.uuid4().hex)[0]


def test_fail_once_preserves_partial_trace_then_retry_is_durable(client, store, payload):
    task_id = create(store, payload | {"scenario": "fail_once"})
    asyncio.run(execute_claim(store, store.claim()))
    detail = store.get(task_id)
    assert detail["status"] == "failed" and detail["error"]["code"] == "SIMULATED_FAILURE"
    assert detail["result"] is None
    first = detail["runs"][0]
    assert first["agent_runs"][0]["output"]["role"] == "researcher"
    assert first["agent_runs"][1]["status"] == "failed"
    headers = {"Idempotency-Key": "retry-key-001"}
    assert client.post(f"/api/tasks/{task_id}/retry", headers=headers).json()["status"] == "queued"
    assert client.post(f"/api/tasks/{task_id}/retry", headers=headers).status_code == 202
    assert (
        client.post(f"/api/tasks/{task_id}/retry", headers={"Idempotency-Key": "retry-key-002"}).status_code
        == 409
    )
    asyncio.run(execute_claim(store, store.claim()))
    replay = client.post(f"/api/tasks/{task_id}/retry", headers=headers)
    assert replay.status_code == 202 and replay.json()["status"] == "succeeded"
    assert replay.json()["attempt_count"] == 2 and len(replay.json()["runs"]) == 2
    assert replay.json()["runs"][0]["agent_runs"][0]["output"] == first["agent_runs"][0]["output"]


def test_timeout_and_maximum_attempts(client, store, payload, settings):
    task_id = create(store, payload | {"scenario": "timeout"})
    for attempt in range(1, settings.max_attempts + 1):
        asyncio.run(execute_claim(store, store.claim()))
        task = store.get(task_id)
        assert task["status"] == "failed" and task["attempt_count"] == attempt
        assert task["error"]["code"] == "MODEL_TIMEOUT"
        assert task["runs"][-1]["agent_runs"][0]["status"] == "succeeded"
        response = client.post(
            f"/api/tasks/{task_id}/retry", headers={"Idempotency-Key": f"retry-timeout-{attempt}"}
        )
        assert response.status_code == (202 if attempt < settings.max_attempts else 409)
    assert store.claim() is None


def test_concurrent_retry_keys_can_only_queue_one_attempt(store, payload):
    task_id = create(store, payload | {"scenario": "fail_once"})
    asyncio.run(execute_claim(store, store.claim()))

    def retry(index):
        try:
            store.retry(task_id, f"concurrent-retry-{index}")
            return "accepted"
        except RequestConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(retry, range(6)))
    assert outcomes.count("accepted") == 1 and outcomes.count("conflict") == 5
    asyncio.run(execute_claim(store, store.claim()))
    assert store.get(task_id)["attempt_count"] == 2


def test_same_retry_key_concurrently_replays_one_durable_retry(store, payload, sessions):
    from sqlalchemy import func, select

    from app.infrastructure.models import IdempotencyRequest

    task_id = create(store, payload | {"scenario": "fail_once"})
    asyncio.run(execute_claim(store, store.claim()))
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: store.retry(task_id, "shared-retry-key"), range(8)))
    assert all(result_id == task_id for result_id, _ in responses)
    assert sum(created for _, created in responses) == 1
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(IdempotencyRequest)) == 2
    asyncio.run(execute_claim(store, store.claim()))
    assert store.retry(task_id, "shared-retry-key") == (task_id, False)
    assert len(store.get(task_id)["runs"]) == 2


def test_unexpected_model_failure_never_persists_secret_exception(store, payload):
    class Broken(DeterministicMockAdapter):
        async def complete(self, role, payload, attempt):
            if role == "challenger":
                raise RuntimeError("DO_NOT_PERSIST_SECRET_sk-test-password")
            return await super().complete(role, payload, attempt)

    task_id = create(store, payload)
    asyncio.run(execute_claim(store, store.claim(), Broken()))
    task = store.get(task_id)
    assert task["error"] == WORKFLOW_FAILED.as_dict()
    assert "DO_NOT_PERSIST_SECRET" not in str(task)
    assert task["runs"][0]["agent_runs"][0]["status"] == "succeeded"
    assert task["runs"][0]["agent_runs"][1]["error"] == WORKFLOW_FAILED.as_dict()
