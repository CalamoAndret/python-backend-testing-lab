import json
from pathlib import Path

from tests.support.operations import Operation
from tests.support.reference import ReferenceModel


def request_for(model: ReferenceModel, op: Operation) -> tuple[str, str, dict]:
    if op.kind == "create":
        return (
            "POST",
            "/tasks",
            {
                "json": {"title": op.title, "priority": op.priority},
                "headers": {"Idempotency-Key": f"sequence:{op.slot}"},
            },
        )
    path = model.path(op.slot)
    if op.kind == "read":
        return "GET", path, {}
    if op.kind == "update":
        return (
            "PATCH",
            path,
            {
                "json": {
                    "expected_version": model.version(op),
                    "title": op.title,
                    "priority": op.priority,
                    "status": op.status,
                }
            },
        )
    if op.kind == "delete":
        return "DELETE", path, {"params": {"expected_version": model.version(op)}}
    raise ValueError(f"Unknown operation: {op.kind}")


def record_failure(history: list[Operation], path: Path = Path("artifacts/replay.json")) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([op.to_dict() for op in history], indent=2), encoding="utf-8")


async def replay(client, sequence: list[Operation]) -> ReferenceModel:
    model = ReferenceModel()
    history = []
    for operation in sequence:
        history.append(operation)
        try:
            method, path, kwargs = request_for(model, operation)
            response = await client.request(method, path, **kwargs)
            model.accept(
                operation, response.status_code, response.json() if response.content else None
            )
            snapshot = (await client.get("/tasks", params={"limit": 100})).json()
            model.assert_snapshot(snapshot["items"])
        except Exception:
            record_failure(history)
            raise
    return model
