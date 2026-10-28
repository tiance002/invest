import asyncio
from typing import Protocol

from app.analysis.schemas import AgentOutput
from app.infrastructure.errors import ModelFailure


class ModelAdapter(Protocol):
    provider: str
    model_name: str

    async def complete(self, role: str, payload: dict, attempt: int) -> AgentOutput: ...


class DeterministicMockAdapter:
    """A local deterministic adapter. Deliberately has no credentials or HTTP client."""

    provider = "deterministic-mock"
    model_name = "arena-mock-v1"

    async def complete(self, role: str, payload: dict, attempt: int) -> AgentOutput:
        request = payload["request"]
        await asyncio.sleep(0.03)
        if role == "challenger" and request["scenario"] == "fail_once" and attempt == 1:
            raise ModelFailure("simulated fixture failure")
        if role == "challenger" and request["scenario"] == "timeout":
            await asyncio.sleep(3600)  # Cancelled by asyncio.wait_for; no external API is contacted.
        refs = [item["id"] for item in payload["evidence"]["items"]]
        if role == "researcher":
            return AgentOutput(
                role="researcher",
                basis=["[模拟] 样本 A 提供需求假设，样本 B 提供覆盖范围限制。"],
                doubts=["[模拟] 缺少真实财务数据、时间序列与独立来源。"],
                conclusion=(
                    f"[模拟] 已整理 {request['symbol']} 的虚构证据链；仅验证研究流程，不形成投资建议。"
                ),
                evidence_refs=refs,
            )
        return AgentOutput(
            role="challenger",
            basis=["[模拟] 已对照研究员输出与固定反例样本 B。"],
            doubts=["[模拟] 样本选择偏差尚未排除。", "[模拟] 需求假设缺少独立验证。"],
            conclusion="[模拟] 证据不足以支持现实判断；保留分歧并请求进一步核查。",
            evidence_refs=refs,
        )
