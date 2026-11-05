from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from testing_lab.config import Settings
from testing_lab.main import create_app
from tests.support.database import guarded_test_url

pytestmark = pytest.mark.postgres


async def test_crud_and_transitions(client):
    response = await client.post("/tasks", json={"title": "  Ship lab  ", "priority": 1})
    assert response.status_code == 201
    task = response.json()
    assert response.headers["location"] == f"/tasks/{task['id']}"
    assert task["title"] == "Ship lab"
    assert task["version"] == 1
    assert task["created_at"] == task["updated_at"]
    path = response.headers["location"]
    assert (await client.get(path)).json() == task
    for version, status in [(1, "in_progress"), (2, "completed")]:
        response = await client.patch(path, json={"expected_version": version, "status": status})
        assert response.status_code == 200
        assert response.json()["version"] == version + 1
        assert response.json()["updated_at"] >= task["updated_at"]
    invalid = await client.patch(path, json={"expected_version": 3, "status": "pending"})
    assert invalid.status_code == 409
    assert invalid.json()["error"]["code"] == "invalid_transition"
    assert (await client.get(path)).json()["version"] == 3
    assert (await client.delete(path, params={"expected_version": 2})).status_code == 409
    assert (await client.delete(path, params={"expected_version": 3})).status_code == 204
    assert (await client.get(path)).status_code == 404


async def test_filters_pagination_and_uniqueness(client):
    ids = []
    for index in range(5):
        response = await client.post(
            "/tasks", json={"title": f"Task {index}", "priority": index + 1}
        )
        ids.append(response.json()["id"])
    assert len(set(ids)) == 5
    first = (await client.get("/tasks", params={"limit": 2})).json()
    second = (await client.get("/tasks", params={"limit": 2, "offset": 2})).json()
    last = (await client.get("/tasks", params={"limit": 2, "offset": 4})).json()
    assert [item["id"] for page in [first, second, last] for item in page["items"]] == ids
    assert first["has_more"] and second["has_more"] and not last["has_more"]
    await client.patch(f"/tasks/{ids[0]}", json={"expected_version": 1, "status": "cancelled"})
    filtered = (await client.get("/tasks", params={"status": "cancelled", "priority": 1})).json()
    assert [item["id"] for item in filtered["items"]] == ids[:1]
    assert not (await client.get("/tasks", params={"offset": 100})).json()["items"]


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("post", "/tasks", {"title": ""}),
        ("post", "/tasks", {"title": "task", "status": "completed"}),
        ("patch", "/tasks/not-a-uuid", {"expected_version": 1, "title": "task"}),
        ("patch", f"/tasks/{uuid4()}", {"expected_version": 1, "description": None}),
        ("patch", f"/tasks/{uuid4()}", {"expected_version": 1}),
    ],
)
async def test_validation_errors(client, method, path, payload):
    response = await client.request(method, path, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_missing_resources(client):
    path = f"/tasks/{uuid4()}"
    assert (await client.get(path)).status_code == 404
    assert (
        await client.patch(path, json={"expected_version": 1, "priority": 2})
    ).status_code == 404
    assert (await client.delete(path, params={"expected_version": 1})).status_code == 404
    assert (await client.get("/health/ready")).status_code == 200


async def test_stale_update_preserves_all_fields(client):
    task = (await client.post("/tasks", json={"title": "original"})).json()
    path = f"/tasks/{task['id']}"
    winner = await client.patch(
        path, json={"expected_version": 1, "title": "winner", "priority": 1}
    )
    loser = await client.patch(path, json={"expected_version": 1, "title": "loser", "priority": 5})
    assert loser.status_code == 409
    assert loser.json()["error"]["code"] == "version_conflict"
    assert (await client.get(path)).json() == winner.json()


async def test_idempotency_replays_original_response_after_update_and_delete(client):
    headers = {"Idempotency-Key": "persistent-key"}
    first = await client.post("/tasks", json={"title": "task"}, headers=headers)
    task = first.json()
    await client.patch(f"/tasks/{task['id']}", json={"expected_version": 1, "title": "changed"})
    replay = await client.post("/tasks", json={"title": "task", "priority": 3}, headers=headers)
    assert replay.status_code == 201
    assert replay.headers["idempotency-replayed"] == "true"
    assert replay.json() == task
    conflict = await client.post("/tasks", json={"title": "different"}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    await client.delete(f"/tasks/{task['id']}", params={"expected_version": 2})
    assert (await client.post("/tasks", json={"title": "task"}, headers=headers)).json() == task
    assert (await client.get("/tasks")).json()["items"] == []


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"priority": 6}, {"status": "unknown"}]
)
async def test_invalid_query(client, params):
    assert (await client.get("/tasks", params=params)).status_code == 422


@pytest.mark.parametrize("key", ["", " ", "x" * 129, "bad/key"])
async def test_invalid_idempotency_key(client, key):
    response = await client.post("/tasks", json={"title": "task"}, headers={"Idempotency-Key": key})
    assert response.status_code == 422


async def test_idempotency_survives_new_application_instance(client):
    headers = {"Idempotency-Key": "across-instances"}
    first = await client.post("/tasks", json={"title": "durable"}, headers=headers)
    other_app = create_app(Settings(database_url=guarded_test_url()))
    async with (
        other_app.router.lifespan_context(other_app),
        AsyncClient(
            transport=ASGITransport(app=other_app), base_url="http://other"
        ) as other_client,
    ):
        second = await other_client.post("/tasks", json={"title": "durable"}, headers=headers)
    assert first.json() == second.json()
    assert second.headers["idempotency-replayed"] == "true"


async def test_same_status_and_description_update(client):
    created = (await client.post("/tasks", json={"title": "task"})).json()
    result = await client.patch(
        f"/tasks/{created['id']}",
        json={"expected_version": 1, "status": "pending", "description": "Updated café 日本語"},
    )
    assert result.status_code == 200
    assert result.json()["description"] == "Updated café 日本語"
    assert result.json()["version"] == 2
