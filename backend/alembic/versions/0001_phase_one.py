"""Explicit mock task, trace, evaluation and offline RSI schema.

Revision ID: 0001_phase_one
Revises: None
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0001_phase_one"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tasks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("request", pg.JSONB(), nullable=False),
        sa.Column("run_version", sa.String(64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("active_run_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", pg.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("mode = 'mock'", name="ck_tasks_mock_only"),
        sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="ck_tasks_status"),
        sa.CheckConstraint("attempt_count >= 0 AND fencing_token >= 0", name="ck_tasks_counts"),
    )
    op.create_index("ix_tasks_claim", "tasks", ["status", "lease_until", "created_at"])
    op.create_table(
        "idempotency_requests",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "task_id", pg.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "task_runs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id", pg.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("run_version", sa.String(64), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", pg.JSONB(), nullable=True),
        sa.UniqueConstraint("task_id", "attempt", name="uq_task_attempt"),
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("task_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("input", pg.JSONB(), nullable=False),
        sa.Column("output", pg.JSONB(), nullable=True),
        sa.Column("evidence_refs", pg.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", pg.JSONB(), nullable=True),
        sa.Column("model_provider", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(14, 8), nullable=True),
        sa.UniqueConstraint("run_id", "role", name="uq_run_agent_role"),
    )
    op.create_table(
        "task_results",
        sa.Column(
            "task_id", pg.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), primary_key=True
        ),
        sa.Column(
            "run_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("task_runs.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "evaluation_runs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_version", sa.String(128), nullable=False),
        sa.Column("baseline_version", sa.String(128), nullable=False),
        sa.Column("candidate_version", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("metrics", pg.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rsi_proposals",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(128), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rsi_experiments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("proposal_id", pg.UUID(as_uuid=True), sa.ForeignKey("rsi_proposals.id"), nullable=False),
        sa.Column("sandbox_version", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rsi_evaluations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_id", pg.UUID(as_uuid=True), sa.ForeignKey("rsi_experiments.id"), nullable=False
        ),
        sa.Column(
            "evaluation_run_id", pg.UUID(as_uuid=True), sa.ForeignKey("evaluation_runs.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rsi_approvals",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "evaluation_id", pg.UUID(as_uuid=True), sa.ForeignKey("rsi_evaluations.id"), nullable=False
        ),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reviewer", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rsi_rollbacks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("approval_id", pg.UUID(as_uuid=True), sa.ForeignKey("rsi_approvals.id"), nullable=False),
        sa.Column("target_version", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    for table in [
        "rsi_rollbacks",
        "rsi_approvals",
        "rsi_evaluations",
        "rsi_experiments",
        "rsi_proposals",
        "evaluation_runs",
        "task_results",
        "agent_runs",
        "task_runs",
        "idempotency_requests",
    ]:
        op.drop_table(table)
    op.drop_index("ix_tasks_claim", table_name="tasks")
    op.drop_table("tasks")
