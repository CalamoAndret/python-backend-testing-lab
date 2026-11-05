from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from testing_lab.db.models import IdempotencyRecord, Task
from testing_lab.repositories import IdempotencyRepository
from testing_lab.schemas import TaskCreate, TaskUpdate
from testing_lab.services import TaskService, fingerprint

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(
    "values",
    [
        {"title": " "},
        {"priority": 0},
        {"status": "unknown"},
        {"version": 0},
        {"description": "x" * 10001},
    ],
)
async def test_database_constraints_and_session_recovery(database, values):
    async with database.sessions() as session:
        with pytest.raises(IntegrityError):
            async with session.begin():
                session.add(Task(**({"title": "valid", "description": ""} | values)))
                await session.flush()
        assert await session.scalar(select(func.count()).select_from(Task)) == 0
        await session.rollback()
        result, _ = await TaskService(session).create(TaskCreate(title="recovered"), None)
        assert result.title == "recovered"


async def test_task_and_reservation_rollback_together(database, monkeypatch):
    async with database.sessions() as session:
        service = TaskService(session)
        monkeypatch.setattr(
            service.keys, "complete", AsyncMock(side_effect=RuntimeError("injected"))
        )
        with pytest.raises(RuntimeError, match="injected"):
            await service.create(TaskCreate(title="must roll back"), "rollback-key")
    async with database.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 0
        assert await session.scalar(select(func.count()).select_from(IdempotencyRecord)) == 0
        await session.rollback()
        task, replayed = await TaskService(session).create(
            TaskCreate(title="retry"), "rollback-key"
        )
        assert task.version == 1 and not replayed


async def test_rollback_after_reservation_allows_retry(database):
    async with database.sessions() as session:
        with pytest.raises(RuntimeError):
            async with session.begin():
                assert await IdempotencyRepository(session).reserve("reserved", "a" * 64)
                raise RuntimeError("abort")
        async with session.begin():
            assert await IdempotencyRepository(session).reserve("reserved", "b" * 64)


async def test_incomplete_record_is_reported_without_duplicate_creation(database):
    data = TaskCreate(title="task")
    async with database.sessions() as session, session.begin():
        session.add(IdempotencyRecord(key="incomplete", fingerprint=fingerprint(data)))
    from testing_lab.errors import DomainError

    async with database.sessions() as session:
        with pytest.raises(DomainError, match="Stored response") as caught:
            await TaskService(session).create(data, "incomplete")
        assert caught.value.status_code == 503
        assert await session.scalar(select(func.count()).select_from(Task)) == 0


async def test_read_committed_isolation(database):
    async with database.sessions() as session:
        assert await session.scalar(text("SHOW transaction_isolation")) == "read committed"


async def test_update_rolls_back_after_sql_write(database, monkeypatch):
    async with database.sessions() as session:
        original, _ = await TaskService(session).create(TaskCreate(title="original"), None)
    async with database.sessions() as session:
        service = TaskService(session)
        update = service.tasks.update

        async def write_then_fail(*args):
            assert await update(*args) is not None
            raise RuntimeError("failure after update")

        monkeypatch.setattr(service.tasks, "update", write_then_fail)
        with pytest.raises(RuntimeError, match="failure after update"):
            await service.update(original.id, TaskUpdate(expected_version=1, title="rollback"))
    async with database.sessions() as session:
        assert await TaskService(session).get(original.id) == original
