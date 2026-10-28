import pytest
from pydantic import ValidationError

from app.analysis.schemas import TaskRequest
from app.infrastructure.config import Settings
from app.infrastructure.db import make_engine


@pytest.mark.parametrize(
    "changes",
    [
        {"symbol": "12345"},
        {"symbol": "1234567"},
        {"market": "US", "symbol": "aapl"},
        {"horizon_days": 0},
        {"horizon_days": 21},
        {"horizon_days": True},
        {"scenario": "live"},
        {"research_question": " "},
        {"broker_token": "not-accepted"},
    ],
)
def test_request_rejects_invalid_inputs(payload, changes):
    with pytest.raises(ValidationError):
        TaskRequest(**(payload | changes))


def test_accepts_market_specific_symbols_and_canonical_defaults():
    request = TaskRequest(symbol=" BRK.B ", market="US", research_question="mock question")
    assert request.symbol == "BRK.B"
    assert request.horizon_days == 3
    assert request.scenario == "normal"


def test_runtime_cannot_enable_live_mode_or_sqlite():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mode="live")
    with pytest.raises(ValueError, match="PostgreSQL"):
        make_engine("sqlite://")
