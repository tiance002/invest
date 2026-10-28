from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.discovery.validation import valid_symbol


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    symbol: str = Field(min_length=1, max_length=10)
    market: Literal["CN_A", "US"]
    horizon_days: int = Field(default=3, ge=1, le=20, strict=True)
    research_question: str = Field(min_length=2, max_length=1000)
    scenario: Literal["normal", "fail_once", "timeout"] = "normal"

    @model_validator(mode="after")
    def check_symbol(self):
        if not valid_symbol(self.symbol, self.market):
            raise ValueError("CN_A requires six digits; US requires an uppercase ticker (1–10 characters)")
        return self


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["mock"] = "mock"
    role: Literal["researcher", "challenger"]
    basis: list[str]
    doubts: list[str]
    conclusion: str
    evidence_refs: list[str]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ResearchResult(BaseModel):
    mode: Literal["mock"]
    summary: str
    agreements: list[str]
    disagreements: list[str]
    open_questions: list[str]
    evidence_refs: list[str]
    agent_outputs: list[AgentOutput]


class AgentRunDetail(BaseModel):
    id: str
    role: str
    status: str
    input: Any
    output: AgentOutput | None
    evidence_refs: list[str]
    duration_ms: int | None
    error: ErrorDetail | None
    model_provider: str
    model_name: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None


class TaskRunDetail(BaseModel):
    id: str
    attempt: int
    run_version: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    error: ErrorDetail | None
    agent_runs: list[AgentRunDetail]


class TaskDetail(BaseModel):
    id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    mode: Literal["mock"]
    request: TaskRequest
    run_version: str
    attempt_count: int
    created_at: datetime
    updated_at: datetime
    error: ErrorDetail | None
    result: ResearchResult | None
    runs: list[TaskRunDetail]


class TaskList(BaseModel):
    items: list[TaskDetail]
