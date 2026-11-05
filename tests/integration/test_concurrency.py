import asyncio

import pytest
from sqlalchemy import func, select, text

from testing_lab.db.models import IdempotencyRecord, Task
from testing_lab.repositories import IdempotencyRepository, TaskRepository
from tests.support.synchronization import wait_for_database_block

pytestmark = [pytest.mark.postgres, pytest.mark.concurrency]


async def test_atomic_update_allows_exactly_one_winner(client, monkeypatch):
    task = (await client.post("/tasks", json={"title": "original"})).json()
    barrier = asyncio.Barrier(2)
    original = TaskRepository.get

    async def synchronized_read(self, task_id):
        result = await original(self, task_id)
        if result is not None and result.version == 1:
            await barrier.wait()
        return result

    monkeypatch.setattr(TaskRepository, "get", synchronized_read)
    path = f"/tasks/{task['id']}"
    async with asyncio.timeout(10):
        responses = await asyncio.gather(
            *[
                client.patch(
                    path, json={"expected_version": 1, "title": title, "priority": priority}
                )
                for title, priority in [("writer-a", 1), ("writer-b", 5)]
            ]
        )
    assert sorted(r.status_code for r in responses) == [200, 409]
    winner = next(r.json() for r in responses if r.status_code == 200)
    assert winner["version"] == 2
    assert (await client.get(path)).json() == winner


async def test_update_delete_race_preserves_a_single_outcome(client, monkeypatch):
    task = (await client.post("/tasks", json={"title": "original"})).json()
    barrier = asyncio.Barrier(2)
    original = TaskRepository.get

    async def synchronized_read(self, task_id):
        result = await original(self, task_id)
        await barrier.wait()
        return result

    monkeypatch.setattr(TaskRepository, "get", synchronized_read)
    path = f"/tasks/{task['id']}"
    async with asyncio.timeout(10):
        update, delete = await asyncio.gather(
            client.patch(path, json={"expected_version": 1, "priority": 1}),
            client.delete(path, params={"expected_version": 1}),
        )
    monkeypatch.setattr(TaskRepository, "get", original)
    assert (update.status_code, delete.status_code) in {(200, 409), (409, 204)}
    current = await client.get(path)
    if update.status_code == 200:
        assert current.json() == update.json()
    else:
        assert current.status_code == 404


@pytest.mark.parametrize("abort_owner", [False, True])
async def test_concurrent_idempotency_waits_for_commit_or_rollback(
    client, database, monkeypatch, abort_owner
):
    owner_ready, contender_ready, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    pids = {}
    reserve = IdempotencyRepository.reserve
    create = TaskRepository.create

    async def controlled_reserve(self, key, fingerprint):
        pid = await self.session.scalar(text("SELECT pg_backend_pid()"))
        if not owner_ready.is_set():
            result = await reserve(self, key, fingerprint)
            pids["owner"] = pid
            owner_ready.set()
            await release.wait()
            return result
        pids["contender"] = pid
        contender_ready.set()
        return await reserve(self, key, fingerprint)

    async def controlled_create(self, data):
        pid = await self.session.scalar(text("SELECT pg_backend_pid()"))
        if abort_owner and pid == pids["owner"]:
            raise RuntimeError("owner aborted")
        return await create(self, data)

    monkeypatch.setattr(IdempotencyRepository, "reserve", controlled_reserve)
    monkeypatch.setattr(TaskRepository, "create", controlled_create)
    headers = {"Idempotency-Key": "contended-key"}
    requests = []
    try:
        async with asyncio.timeout(15):
            requests.append(
                asyncio.create_task(client.post("/tasks", json={"title": "task"}, headers=headers))
            )
            await owner_ready.wait()
            requests.append(
                asyncio.create_task(client.post("/tasks", json={"title": "task"}, headers=headers))
            )
            await contender_ready.wait()
            await wait_for_database_block(database, pids["contender"], pids["owner"])
            release.set()
            owner, contender = await asyncio.gather(*requests, return_exceptions=True)
        assert contender.status_code == 201
        if abort_owner:
            assert isinstance(owner, RuntimeError)
            assert contender.headers["idempotency-replayed"] == "false"
        else:
            assert owner.status_code == 201
            assert owner.json() == contender.json()
            assert contender.headers["idempotency-replayed"] == "true"
        async with database.sessions() as session:
            assert await session.scalar(select(func.count()).select_from(Task)) == 1
            assert await session.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1
            assert (await session.scalars(select(IdempotencyRecord))).one().response is not None
    finally:
        release.set()
        for request in requests:
            if not request.done():
                request.cancel()
        await asyncio.gather(*requests, return_exceptions=True)


async def test_concurrent_different_payloads_share_key(client, monkeypatch):
    barrier = asyncio.Barrier(2)
    original = IdempotencyRepository.reserve

    async def reserve_together(self, key, fingerprint):
        await barrier.wait()
        return await original(self, key, fingerprint)

    monkeypatch.setattr(IdempotencyRepository, "reserve", reserve_together)
    async with asyncio.timeout(10):
        responses = await asyncio.gather(
            *[
                client.post("/tasks", json={"title": title}, headers={"Idempotency-Key": "same"})
                for title in ["first", "different"]
            ]
        )
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert len((await client.get("/tasks")).json()["items"]) == 1
