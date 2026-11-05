"""Opt-in mutation: remove the atomic version predicate. Never loaded by the app."""

import pytest
from sqlalchemy import func, update

from testing_lab.db.models import Task
from testing_lab.repositories import TaskRepository


@pytest.fixture(autouse=True)
def deliberately_broken_version_check(monkeypatch):
    async def broken_update(self, task_id, version, changes):
        result = await self.session.execute(
            update(Task)
            .where(Task.id == task_id)  # BUG: missing `Task.version == version`
            .values(**changes, version=Task.version + 1, updated_at=func.clock_timestamp())
            .returning(Task)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    monkeypatch.setattr(TaskRepository, "update", broken_update)
