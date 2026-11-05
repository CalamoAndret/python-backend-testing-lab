from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from testing_lab.db.models import IdempotencyRecord, Task
from testing_lab.domain import Status
from testing_lab.schemas import TaskCreate


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: TaskCreate) -> Task:
        task = Task(**data.model_dump())
        self.session.add(task)
        await self.session.flush()
        return task

    async def get(self, task_id: UUID) -> Task | None:
        return await self.session.get(Task, task_id)

    async def list(
        self, status: Status | None, priority: int | None, limit: int, offset: int
    ) -> list[Task]:
        query = select(Task).order_by(Task.created_at, Task.id).limit(limit + 1).offset(offset)
        if status is not None:
            query = query.where(Task.status == status)
        if priority is not None:
            query = query.where(Task.priority == priority)
        return list((await self.session.scalars(query)).all())

    async def update(self, task_id: UUID, version: int, changes: dict) -> Task | None:
        result = await self.session.execute(
            update(Task)
            .where(Task.id == task_id, Task.version == version)
            .values(**changes, version=Task.version + 1, updated_at=func.clock_timestamp())
            .returning(Task)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def delete(self, task_id: UUID, version: int) -> bool:
        result = await self.session.execute(
            delete(Task).where(Task.id == task_id, Task.version == version).returning(Task.id)
        )
        return result.scalar_one_or_none() is not None


class IdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reserve(self, key: str, fingerprint: str) -> bool:
        # The unique index serializes contenders, including uncommitted insertions.
        result = await self.session.execute(
            insert(IdempotencyRecord)
            .values(key=key, fingerprint=fingerprint)
            .on_conflict_do_nothing(index_elements=[IdempotencyRecord.key])
            .returning(IdempotencyRecord.key)
        )
        return result.scalar_one_or_none() is not None

    async def get(self, key: str) -> IdempotencyRecord:
        # A separate statement gets a fresh READ COMMITTED snapshot after a waiter wakes.
        return (
            await self.session.scalars(
                select(IdempotencyRecord).where(IdempotencyRecord.key == key)
            )
        ).one()

    async def complete(self, key: str, response: dict) -> None:
        await self.session.execute(
            update(IdempotencyRecord).where(IdempotencyRecord.key == key).values(response=response)
        )
