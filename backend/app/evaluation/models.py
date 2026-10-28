"""Reserved offline evaluation records. No API or runtime activation path in phase one."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_version: Mapped[str] = mapped_column(String(128))
    baseline_version: Mapped[str] = mapped_column(String(128))
    candidate_version: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="reserved")
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
