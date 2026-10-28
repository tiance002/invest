"""PostgreSQL owns task durability, immutable idempotency, leases, traces and final results."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import selectinload

from app.infrastructure.errors import LEASE_EXPIRED, LostLease, SafeError
from app.infrastructure.models import AgentRun, IdempotencyRequest, Task, TaskResult, TaskRun

RUN_VERSION = "mock-graph-v1"


class RequestConflict(Exception):
    pass


class TaskMissing(Exception):
    pass


@dataclass(frozen=True)
class Claim:
    task_id: uuid.UUID
    run_id: uuid.UUID
    fencing_token: int
    attempt: int
    request: dict


def elapsed(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() * 1000))


def db_now(session) -> datetime:
    return session.scalar(select(func.clock_timestamp()))


def fingerprint(action: str, payload: dict) -> str:
    canonical = json.dumps({"action": action, "payload": payload}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def lock_key(session, key: str) -> None:
    # Serialize identical keys before looking them up. The immutable primary key also enforces uniqueness.
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})


def existing_request(session, key: str, digest: str) -> uuid.UUID | None:
    record = session.get(IdempotencyRequest, key)
    if record is None:
        return None
    if record.fingerprint != digest:
        raise RequestConflict("幂等键已用于不同请求；请使用新的幂等键。")
    return record.task_id


class TaskStore:
    def __init__(self, sessions, settings):
        self.sessions = sessions
        self.settings = settings

    def create(self, payload: dict, key: str) -> tuple[uuid.UUID, bool]:
        digest = fingerprint("create", payload)
        with self.sessions.begin() as session:
            lock_key(session, key)
            old = existing_request(session, key, digest)
            if old:
                return old, False
            task = Task(request=payload, run_version=RUN_VERSION)
            session.add(task)
            session.flush()
            session.add(IdempotencyRequest(key=key, fingerprint=digest, task_id=task.id))
            task_id = task.id
        return task_id, True

    def retry(self, task_id: uuid.UUID, key: str) -> tuple[uuid.UUID, bool]:
        digest = fingerprint("retry", {"task_id": str(task_id)})
        with self.sessions.begin() as session:
            lock_key(session, key)
            old = existing_request(session, key, digest)
            if old:
                return old, False
            task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
            if task is None:
                raise TaskMissing()
            if task.status != "failed":
                raise RequestConflict("只有失败的任务可以重试。")
            if task.attempt_count >= self.settings.max_attempts:
                raise RequestConflict("该任务已达到最大尝试次数。")
            task.status = "queued"
            task.error = None
            task.active_run_id = None
            task.lease_until = None
            task.updated_at = db_now(session)
            session.add(IdempotencyRequest(key=key, fingerprint=digest, task_id=task_id))
        return task_id, True

    @staticmethod
    def _detail(task: Task) -> dict:
        return {
            "id": str(task.id),
            "status": task.status,
            "mode": task.mode,
            "request": task.request,
            "run_version": task.run_version,
            "attempt_count": task.attempt_count,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "error": task.error,
            "result": task.result.payload if task.result else None,
            "runs": [
                {
                    "id": str(run.id),
                    "attempt": run.attempt,
                    "run_version": run.run_version,
                    "status": run.status,
                    "started_at": run.started_at,
                    "finished_at": run.finished_at,
                    "duration_ms": run.duration_ms,
                    "error": run.error,
                    "agent_runs": [
                        {
                            "id": str(agent.id),
                            "role": agent.role,
                            "status": agent.status,
                            "input": agent.input,
                            "output": agent.output,
                            "evidence_refs": agent.evidence_refs,
                            "duration_ms": agent.duration_ms,
                            "error": agent.error,
                            "model_provider": agent.model_provider,
                            "model_name": agent.model_name,
                            "input_tokens": agent.input_tokens,
                            "output_tokens": agent.output_tokens,
                            "cost_usd": float(agent.cost_usd) if agent.cost_usd is not None else None,
                        }
                        for agent in run.agent_runs
                    ],
                }
                for run in task.runs
            ],
        }

    @staticmethod
    def _details_query():
        return select(Task).options(
            selectinload(Task.runs).selectinload(TaskRun.agent_runs), selectinload(Task.result)
        )

    def get(self, task_id: uuid.UUID) -> dict | None:
        with self.sessions() as session:
            task = session.scalar(self._details_query().where(Task.id == task_id))
            return self._detail(task) if task else None

    def latest(self) -> list[dict]:
        with self.sessions() as session:
            tasks = session.scalars(self._details_query().order_by(Task.created_at.desc()).limit(50)).all()
            return [self._detail(task) for task in tasks]

    @staticmethod
    def _expire_run(session, task: Task, now: datetime) -> None:
        run = session.get(TaskRun, task.active_run_id)
        if run is None or run.status != "running":
            return
        run.status, run.error, run.finished_at = "failed", LEASE_EXPIRED.as_dict(), now
        run.duration_ms = elapsed(run.started_at, now)
        for agent in run.agent_runs:
            if agent.status == "running":
                agent.status, agent.error, agent.finished_at = "failed", LEASE_EXPIRED.as_dict(), now
                agent.duration_ms = elapsed(agent.started_at, now)

    def claim(self) -> Claim | None:
        with self.sessions.begin() as session:
            # SKIP LOCKED allows multiple processes; an expired lease is reclaimed under the same row lock.
            for _ in range(100):
                now = db_now(session)
                task = session.scalar(
                    select(Task)
                    .where(
                        or_(
                            Task.status == "queued",
                            and_(
                                Task.status == "running",
                                Task.lease_until <= now,
                            ),
                        )
                    )
                    .order_by(Task.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                if task is None:
                    return None
                if task.status == "running":
                    self._expire_run(session, task, now)
                if task.attempt_count >= self.settings.max_attempts:
                    task.status, task.error = "failed", LEASE_EXPIRED.as_dict()
                    task.lease_until, task.active_run_id, task.updated_at = None, None, now
                    session.flush()
                    continue
                task.attempt_count += 1
                task.fencing_token += 1
                run = TaskRun(
                    task_id=task.id,
                    attempt=task.attempt_count,
                    run_version=RUN_VERSION,
                    fencing_token=task.fencing_token,
                    started_at=now,
                )
                session.add(run)
                session.flush()
                task.status, task.error = "running", None
                task.active_run_id = run.id
                task.lease_until = now + timedelta(seconds=self.settings.lease_seconds)
                task.updated_at = now
                return Claim(task.id, run.id, task.fencing_token, task.attempt_count, task.request)
        return None

    @staticmethod
    def _owned(session, claim: Claim) -> tuple[Task, TaskRun, datetime]:
        task = session.scalar(select(Task).where(Task.id == claim.task_id).with_for_update())
        now = db_now(session)
        if (
            task is None
            or task.status != "running"
            or task.fencing_token != claim.fencing_token
            or task.active_run_id != claim.run_id
            or task.lease_until is None
            or task.lease_until <= now
        ):
            raise LostLease()
        run = session.get(TaskRun, claim.run_id)
        if run is None or run.status != "running":
            raise LostLease()
        return task, run, now

    def heartbeat(self, claim: Claim) -> None:
        with self.sessions.begin() as session:
            task, _, now = self._owned(session, claim)
            task.lease_until = now + timedelta(seconds=self.settings.lease_seconds)

    def start_agent(self, claim: Claim, role: str, payload: dict, provider: str, model: str) -> uuid.UUID:
        with self.sessions.begin() as session:
            _, _, now = self._owned(session, claim)
            agent = AgentRun(
                run_id=claim.run_id,
                role=role,
                input=payload,
                started_at=now,
                evidence_refs=[item["id"] for item in payload["evidence"]["items"]],
                model_provider=provider,
                model_name=model,
            )
            session.add(agent)
            session.flush()
            return agent.id

    def finish_agent(self, claim: Claim, agent_id: uuid.UUID, output: dict | None, error: SafeError | None):
        with self.sessions.begin() as session:
            _, _, now = self._owned(session, claim)
            agent = session.get(AgentRun, agent_id)
            if agent is None or agent.run_id != claim.run_id or agent.status != "running":
                raise LostLease()
            agent.status = "failed" if error else "succeeded"
            agent.output = output
            agent.error = error.as_dict() if error else None
            agent.finished_at = now
            agent.duration_ms = elapsed(agent.started_at, now)

    def finish(self, claim: Claim, result: dict | None, error: SafeError | None = None):
        with self.sessions.begin() as session:
            task, run, now = self._owned(session, claim)
            task.status = run.status = "failed" if error else "succeeded"
            task.error = run.error = error.as_dict() if error else None
            task.updated_at = run.finished_at = now
            run.duration_ms = elapsed(run.started_at, now)
            task.lease_until = None
            task.active_run_id = None
            if error:
                for agent in run.agent_runs:
                    if agent.status == "running":
                        agent.status, agent.error, agent.finished_at = "failed", error.as_dict(), now
                        agent.duration_ms = elapsed(agent.started_at, now)
            else:
                # TaskResult's task_id PK and run_id UNIQUE enforce one immutable final result.
                session.add(TaskResult(task_id=task.id, run_id=run.id, payload=result))
