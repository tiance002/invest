import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request

from app.analysis.schemas import TaskDetail, TaskList, TaskRequest
from app.orchestration.store import RequestConflict, TaskMissing

router = APIRouter(prefix="/api")
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


@router.post("/tasks", status_code=202, response_model=TaskDetail)
def create_task(payload: TaskRequest, request: Request, idempotency_key: IdempotencyKey):
    try:
        task_id, created = request.app.state.store.create(payload.model_dump(), idempotency_key)
    except RequestConflict as exc:
        raise HTTPException(409, str(exc)) from None
    # create() has committed. Notification failures cannot undo the durable task row.
    if created:
        request.app.state.notifications.notify(str(task_id))
    return request.app.state.store.get(task_id)


@router.get("/tasks", response_model=TaskList)
def list_tasks(request: Request):
    return {"items": request.app.state.store.latest()}


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: uuid.UUID, request: Request):
    result = request.app.state.store.get(task_id)
    if result is None:
        raise HTTPException(404, "任务不存在。")
    return result


@router.post("/tasks/{task_id}/retry", status_code=202, response_model=TaskDetail)
def retry_task(task_id: uuid.UUID, request: Request, idempotency_key: IdempotencyKey):
    try:
        result_id, created = request.app.state.store.retry(task_id, idempotency_key)
    except RequestConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except TaskMissing:
        raise HTTPException(404, "任务不存在。") from None
    if created:
        request.app.state.notifications.notify(str(result_id))
    return request.app.state.store.get(result_id)
