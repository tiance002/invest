"""Exercise the actual compiled LangGraph independently of database availability."""

import uuid
from types import SimpleNamespace

import pytest

from app.agents.model import DeterministicMockAdapter
from app.infrastructure.errors import WORKFLOW_FAILED, LostLease
from app.orchestration.store import Claim
from app.orchestration.workflow import WorkflowError, build_graph, execute_claim


class TraceRecorder:
    def __init__(self):
        self.events = []

    def start_agent(self, claim, role, payload, provider, model):
        self.events.append({"role": role, "input": payload, "status": "running"})
        return len(self.events) - 1

    def finish_agent(self, claim, agent_id, output, error):
        self.events[agent_id].update(output=output, error=error, status="failed" if error else "succeeded")


@pytest.mark.asyncio
async def test_real_langgraph_executes_two_agents_and_synthesis(payload):
    recorder = TraceRecorder()
    claim = Claim(uuid.uuid4(), uuid.uuid4(), 1, 1, payload)
    graph = build_graph(recorder, claim, DeterministicMockAdapter(), 0.5)
    result = (await graph.ainvoke({"outputs": []}))["result"]
    assert result["mode"] == "mock"
    assert [event["role"] for event in recorder.events] == ["researcher", "challenger"]
    assert recorder.events[1]["input"]["previous_outputs"][0]["role"] == "researcher"
    assert result["evidence_refs"] == ["mock-evidence-v1:sample-a", "mock-evidence-v1:sample-b"]
    assert result["agreements"] and result["disagreements"] and result["open_questions"]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario,code", [("fail_once", "SIMULATED_FAILURE"), ("timeout", "MODEL_TIMEOUT")])
async def test_graph_faults_keep_first_agent_output(payload, scenario, code):
    recorder = TraceRecorder()
    claim = Claim(uuid.uuid4(), uuid.uuid4(), 1, 1, payload | {"scenario": scenario})
    graph = build_graph(recorder, claim, DeterministicMockAdapter(), 0.08)
    with pytest.raises(WorkflowError) as caught:
        await graph.ainvoke({"outputs": []})
    assert caught.value.error.code == code
    assert recorder.events[0]["status"] == "succeeded"
    assert recorder.events[0]["output"]["mode"] == "mock"
    assert recorder.events[1]["status"] == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("lost_lease", [False, True])
async def test_failed_background_heartbeat_cannot_publish_success(payload, lost_lease):
    import asyncio

    class FailingHeartbeat(TraceRecorder):
        settings = SimpleNamespace(lease_seconds=0.06, model_timeout_seconds=0.5)

        def __init__(self):
            super().__init__()
            self.finishes = []

        def heartbeat(self, claim):
            if lost_lease:
                raise LostLease()
            raise RuntimeError("DO_NOT_PERSIST_HEARTBEAT_SECRET")

        def finish(self, claim, result, error=None):
            self.finishes.append((result, error))

    class SlowMock(DeterministicMockAdapter):
        async def complete(self, role, payload, attempt):
            await asyncio.sleep(0.04)
            return await super().complete(role, payload, attempt)

    recorder = FailingHeartbeat()
    claim = Claim(uuid.uuid4(), uuid.uuid4(), 1, 1, payload)
    await execute_claim(recorder, claim, SlowMock())
    assert recorder.finishes == ([] if lost_lease else [(None, WORKFLOW_FAILED)])
    assert "DO_NOT_PERSIST_HEARTBEAT_SECRET" not in str(recorder.events)
