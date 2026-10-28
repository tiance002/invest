import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from app.agents.model import DeterministicMockAdapter, ModelAdapter
from app.data.evidence import evidence_bundle
from app.decisions.synthesis import synthesize
from app.infrastructure.errors import (
    MODEL_TIMEOUT,
    SIMULATED_FAILURE,
    WORKFLOW_FAILED,
    LostLease,
    ModelFailure,
    SafeError,
)
from app.orchestration.store import Claim, TaskStore


class WorkflowState(TypedDict):
    outputs: list[dict]
    result: dict


class WorkflowError(Exception):
    def __init__(self, error: SafeError):
        self.error = error


def build_graph(store: TaskStore, claim: Claim, adapter: ModelAdapter, timeout: float):
    async def agent_step(role: str, state: WorkflowState) -> dict:
        payload = {
            "mode": "mock",
            "request": claim.request,
            "evidence": evidence_bundle(),
            "previous_outputs": state["outputs"],
            "prompt_version": f"{role}-mock-v1",
        }
        agent_id = store.start_agent(claim, role, payload, adapter.provider, adapter.model_name)
        error = None
        output = None
        try:
            output = (
                await asyncio.wait_for(adapter.complete(role, payload, claim.attempt), timeout)
            ).model_dump()
        except TimeoutError:
            error = MODEL_TIMEOUT
        except ModelFailure:
            error = SIMULATED_FAILURE
        except Exception:
            error = WORKFLOW_FAILED
        store.finish_agent(claim, agent_id, output, error)
        if error:
            raise WorkflowError(error)
        return {"outputs": [*state["outputs"], output]}

    async def researcher(state: WorkflowState):
        return await agent_step("researcher", state)

    async def challenger(state: WorkflowState):
        return await agent_step("challenger", state)

    def synthesis(state: WorkflowState):
        return {"result": synthesize(state["outputs"])}

    graph = StateGraph(WorkflowState)
    graph.add_node("researcher", researcher)
    graph.add_node("challenger", challenger)
    graph.add_node("synthesis", synthesis)
    graph.add_edge(START, "researcher")
    graph.add_edge("researcher", "challenger")
    graph.add_edge("challenger", "synthesis")
    graph.add_edge("synthesis", END)
    return graph.compile()


async def execute_claim(store: TaskStore, claim: Claim, adapter: ModelAdapter | None = None):
    stopped = asyncio.Event()

    async def maintain_lease():
        while not stopped.is_set():
            try:
                await asyncio.wait_for(stopped.wait(), timeout=store.settings.lease_seconds / 3)
            except TimeoutError:
                store.heartbeat(claim)

    lease_task = asyncio.create_task(maintain_lease())
    try:
        graph = build_graph(
            store, claim, adapter or DeterministicMockAdapter(), store.settings.model_timeout_seconds
        )
        # Even inherited developer tracing settings must not export mock requests or evidence.
        with tracing_context(enabled=False):
            outcome = await graph.ainvoke({"outputs": []}, config={"callbacks": []})
        # Surface a failed heartbeat before trying to finalize. Finalization checks the fence again.
        if lease_task.done():
            lease_task.result()
        store.finish(claim, outcome["result"])
    except LostLease:
        # A stale worker never changes task, run, trace, or result after losing ownership.
        return
    except WorkflowError as exc:
        try:
            store.finish(claim, None, exc.error)
        except LostLease:
            pass
    except Exception:
        try:
            store.finish(claim, None, WORKFLOW_FAILED)
        except LostLease:
            pass
    finally:
        stopped.set()
        lease_task.cancel()
        await asyncio.gather(lease_task, return_exceptions=True)
