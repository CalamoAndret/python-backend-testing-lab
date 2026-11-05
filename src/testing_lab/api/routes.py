from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from testing_lab.domain import Status
from testing_lab.schemas import ErrorResponse, TaskCreate, TaskPage, TaskRead, TaskUpdate
from testing_lab.services import TaskService

router = APIRouter()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.sessions() as session:
        yield session


Session = Annotated[AsyncSession, Depends(get_session)]


def get_service(session: Session) -> TaskService:
    return TaskService(session)


Service = Annotated[TaskService, Depends(get_service)]
Errors = {code: {"model": ErrorResponse} for code in (404, 409, 422, 503)}


@router.get("/health/live", tags=["health"])
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", tags=["health"], responses={503: {"model": ErrorResponse}})
async def ready(session: Session) -> dict[str, str]:
    # Check schema readiness as well as connectivity (no table creation at startup).
    await session.execute(text("SELECT id FROM tasks LIMIT 0"))
    await session.execute(text("SELECT key FROM idempotency_keys LIMIT 0"))
    return {"status": "ready"}


@router.post("/tasks", response_model=TaskRead, status_code=201, tags=["tasks"], responses=Errors)
async def create_task(
    data: TaskCreate,
    response: Response,
    service: Service,
    idempotency_key: Annotated[
        str | None, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ] = None,
) -> TaskRead:
    task, replayed = await service.create(data, idempotency_key)
    response.headers["Location"] = f"/tasks/{task.id}"
    response.headers["Idempotency-Replayed"] = str(replayed).lower()
    return task


@router.get("/tasks", response_model=TaskPage, tags=["tasks"], responses=Errors)
async def list_tasks(
    service: Service,
    status: Status | None = None,
    priority: Annotated[int | None, Query(ge=1, le=5)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> TaskPage:
    return await service.list(status, priority, limit, offset)


@router.get("/tasks/{task_id}", response_model=TaskRead, tags=["tasks"], responses=Errors)
async def get_task(task_id: UUID, service: Service) -> TaskRead:
    return await service.get(task_id)


@router.patch("/tasks/{task_id}", response_model=TaskRead, tags=["tasks"], responses=Errors)
async def update_task(task_id: UUID, data: TaskUpdate, service: Service) -> TaskRead:
    return await service.update(task_id, data)


@router.delete("/tasks/{task_id}", status_code=204, tags=["tasks"], responses=Errors)
async def delete_task(
    task_id: UUID, service: Service, expected_version: Annotated[int, Query(ge=1, le=2_147_483_646)]
) -> Response:
    await service.delete(task_id, expected_version)
    return Response(status_code=204)
