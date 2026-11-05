import hashlib
import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from testing_lab.domain import Status, can_transition
from testing_lab.errors import DomainError, not_found, stale_version
from testing_lab.repositories import IdempotencyRepository, TaskRepository
from testing_lab.schemas import TaskCreate, TaskPage, TaskRead, TaskUpdate


def fingerprint(data: TaskCreate) -> str:
    canonical = json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.keys = IdempotencyRepository(session)

    async def create(self, data: TaskCreate, key: str | None) -> tuple[TaskRead, bool]:
        async with self.session.begin():
            if key is not None and not await self.keys.reserve(key, fingerprint(data)):
                record = await self.keys.get(key)
                if record.fingerprint != fingerprint(data):
                    raise DomainError(
                        409,
                        "idempotency_conflict",
                        "Key was already used with a different payload.",
                    )
                if record.response is None:
                    raise DomainError(
                        503, "incomplete_idempotency", "Stored response is unavailable."
                    )
                return TaskRead.model_validate(record.response), True
            result = TaskRead.model_validate(await self.tasks.create(data))
            if key is not None:
                await self.keys.complete(key, result.model_dump(mode="json"))
        return result, False

    async def get(self, task_id: UUID) -> TaskRead:
        task = await self.tasks.get(task_id)
        if task is None:
            raise not_found()
        return TaskRead.model_validate(task)

    async def list(
        self, status: Status | None, priority: int | None, limit: int, offset: int
    ) -> TaskPage:
        tasks = await self.tasks.list(status, priority, limit, offset)
        return TaskPage(
            items=[TaskRead.model_validate(task) for task in tasks[:limit]],
            limit=limit,
            offset=offset,
            has_more=len(tasks) > limit,
        )

    async def update(self, task_id: UUID, data: TaskUpdate) -> TaskRead:
        async with self.session.begin():
            current = await self.tasks.get(task_id)
            if current is None:
                raise not_found()
            if current.version != data.expected_version:
                raise stale_version()
            if data.status is not None and not can_transition(Status(current.status), data.status):
                raise DomainError(
                    409, "invalid_transition", "This status transition is not allowed."
                )
            changes = data.model_dump(exclude_unset=True, exclude={"expected_version"})
            task = await self.tasks.update(task_id, data.expected_version, changes)
            if task is None:
                raise stale_version()
            result = TaskRead.model_validate(task)
        return result

    async def delete(self, task_id: UUID, version: int) -> None:
        async with self.session.begin():
            if await self.tasks.get(task_id) is None:
                raise not_found()
            if not await self.tasks.delete(task_id, version):
                raise stale_version()
