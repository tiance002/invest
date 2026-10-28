import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.data.evidence import evidence_bundle
from app.infrastructure.errors import LostLease
from app.infrastructure.models import Task, TaskResult
from app.orchestration.store import db_now
from app.orchestration.workflow import execute_claim

pytestmark = pytest.mark.integration


def test_multiple_workers_claim_each_task_once(store, payload):
    ids = {store.create(payload, "concurrent-" + uuid.uuid4().hex)[0] for _ in range(6)}
    with ThreadPoolExecutor(max_workers=12) as pool:
        claims = list(pool.map(lambda _: store.claim(), range(12)))
    acquired = [claim for claim in claims if claim]
    assert len(acquired) == len(ids) and {claim.task_id for claim in acquired} == ids
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda claim: asyncio.run(execute_claim(store, claim)), acquired))
    assert all(store.get(task_id)["status"] == "succeeded" for task_id in ids)


def test_expired_lease_is_reclaimed_and_stale_worker_cannot_commit(store, sessions, payload):
    task_id = store.create(payload, "lease-test-key")[0]
    stale = store.claim()
    stale_agent = store.start_agent(
        stale,
        "researcher",
        {"request": payload, "evidence": evidence_bundle()},
        "deterministic-mock",
        "arena-mock-v1",
    )
    with sessions.begin() as session:
        task = session.get(Task, task_id)
        task.lease_until = db_now(session) - timedelta(seconds=1)
    # Expiry alone fences writes, even before another worker reclaims the row.
    with pytest.raises(LostLease):
        store.finish(stale, {"mode": "mock", "summary": "stale result"})
    current = store.claim()
    assert current.fencing_token > stale.fencing_token and current.attempt == 2
    with pytest.raises(LostLease):
        store.heartbeat(stale)
    with pytest.raises(LostLease):
        store.finish_agent(stale, stale_agent, {"mode": "mock", "conclusion": "stale"}, None)
    asyncio.run(execute_claim(store, current))
    with pytest.raises(LostLease):
        store.finish(stale, {"mode": "mock", "summary": "stale result"})
    detail = store.get(task_id)
    assert detail["status"] == "succeeded"
    assert detail["runs"][0]["error"]["code"] == "LEASE_EXPIRED"
    assert detail["runs"][0]["agent_runs"][0]["error"]["code"] == "LEASE_EXPIRED"
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(TaskResult)) == 1


def test_skip_locked_does_not_wait_for_another_worker_row_lock(store, sessions, payload):
    task_id = store.create(payload, "row-lock-test-key")[0]
    with sessions.begin() as session:
        session.scalar(select(Task).where(Task.id == task_id).with_for_update())
        assert store.claim() is None
    assert store.claim().task_id == task_id


@pytest.mark.asyncio
async def test_heartbeat_renews_lease_during_a_long_workflow(store, payload):
    from app.agents.model import DeterministicMockAdapter

    class SlowMock(DeterministicMockAdapter):
        async def complete(self, role, payload, attempt):
            await asyncio.sleep(1.7)
            return await super().complete(role, payload, attempt)

    store.settings.model_timeout_seconds = 4
    task_id = store.create(payload, "heartbeat-test-key")[0]
    claim = store.claim()
    execution = asyncio.create_task(execute_claim(store, claim, SlowMock()))
    await asyncio.sleep(3.1)
    assert store.claim() is None
    await execution
    assert store.get(task_id)["status"] == "succeeded"
    assert store.get(task_id)["attempt_count"] == 1


def test_worker_crash_recovery_is_bounded(store, sessions, payload, settings):
    task_id = store.create(payload, "bounded-crash-key")[0]
    for attempt in range(settings.max_attempts):
        assert store.claim().attempt == attempt + 1
        with sessions.begin() as session:
            session.get(Task, task_id).lease_until = db_now(session) - timedelta(seconds=1)
    assert store.claim() is None
    task = store.get(task_id)
    assert task["status"] == "failed" and task["attempt_count"] == settings.max_attempts
    assert all(run["status"] == "failed" for run in task["runs"])


@pytest.mark.asyncio
async def test_cancelled_workflow_leaves_recoverable_audit_and_no_result(store, sessions, payload):
    from app.agents.model import DeterministicMockAdapter

    entered = asyncio.Event()

    class PausedMock(DeterministicMockAdapter):
        async def complete(self, role, payload, attempt):
            entered.set()
            await asyncio.Event().wait()

    task_id = store.create(payload, "cancelled-workflow-key")[0]
    stale = store.claim()
    execution = asyncio.create_task(execute_claim(store, stale, PausedMock()))
    await asyncio.wait_for(entered.wait(), timeout=2)
    execution.cancel()
    with pytest.raises(asyncio.CancelledError):
        await execution
    with sessions.begin() as session:
        session.get(Task, task_id).lease_until = db_now(session) - timedelta(seconds=1)
    current = store.claim()
    await execute_claim(store, current)
    detail = store.get(task_id)
    assert detail["status"] == "succeeded" and detail["attempt_count"] == 2
    assert detail["runs"][0]["error"]["code"] == "LEASE_EXPIRED"
    assert detail["runs"][0]["agent_runs"][0]["error"]["code"] == "LEASE_EXPIRED"
    assert detail["runs"][1]["status"] == "succeeded"
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(TaskResult)) == 1
