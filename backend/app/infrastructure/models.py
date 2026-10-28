import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db import Base


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    mode: Mapped[str] = mapped_column(String(8), default="mock")
    request: Mapped[dict[str, Any]] = mapped_column(JSONB)
    run_version: Mapped[str] = mapped_column(String(64), default="mock-graph-v1")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    fencing_token: Mapped[int] = mapped_column(Integer, default=0)
    active_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    runs: Mapped[list["TaskRun"]] = relationship(back_populates="task", order_by="TaskRun.attempt")
    result: Mapped["TaskResult | None"] = relationship(back_populates="task", uselist=False)
    __table_args__ = (
        Index("ix_tasks_claim", "status", "lease_until", "created_at"),
        CheckConstraint("mode = 'mock'", name="ck_tasks_mock_only"),
        CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="ck_tasks_status"),
        CheckConstraint("attempt_count >= 0 AND fencing_token >= 0", name="ck_tasks_counts"),
    )


class IdempotencyRequest(Base):
    __tablename__ = "idempotency_requests"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaskRun(Base):
    __tablename__ = "task_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    attempt: Mapped[int] = mapped_column(Integer)
    run_version: Mapped[str] = mapped_column(String(64))
    fencing_token: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    task: Mapped[Task] = relationship(back_populates="runs")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="run", order_by="AgentRun.started_at")
    __table_args__ = (UniqueConstraint("task_id", "attempt", name="uq_task_attempt"),)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id", ondelete="RESTRICT"))
    role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="running")
    input: Mapped[dict] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evidence_refs: Mapped[list] = mapped_column(JSONB, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_provider: Mapped[str] = mapped_column(String(64), default="deterministic-mock")
    model_name: Mapped[str] = mapped_column(String(64), default="arena-mock-v1")
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    run: Mapped[TaskRun] = relationship(back_populates="agent_runs")
    __table_args__ = (UniqueConstraint("run_id", "role", name="uq_run_agent_role"),)


class TaskResult(Base):
    __tablename__ = "task_results"
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id", ondelete="RESTRICT"), unique=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    task: Mapped[Task] = relationship(back_populates="result")
