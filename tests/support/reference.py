from copy import deepcopy
from dataclasses import dataclass, field
from uuid import UUID

from tests.support.operations import Operation

# Deliberately independent of production domain logic: a shared transition helper
# would make implementation and oracle reproduce the same defect.
ALLOWED = {
    "pending": {"pending", "in_progress", "cancelled"},
    "in_progress": {"in_progress", "completed", "cancelled"},
    "completed": {"completed"},
    "cancelled": {"cancelled"},
}
FIELDS = ("title", "description", "priority", "status", "version")


@dataclass
class ReferenceModel:
    live: dict[int, dict] = field(default_factory=dict)
    originals: dict[int, tuple[dict, dict]] = field(default_factory=dict)
    identities: dict[int, str] = field(default_factory=dict)

    def path(self, slot: int) -> str:
        return f"/tasks/{self.identities.get(slot, str(UUID(int=slot + 1)))}"

    def version(self, op: Operation) -> int:
        current = self.live.get(op.slot, {}).get("version", 1)
        return current + int(op.stale)

    def expected_status(self, op: Operation) -> int:
        if op.kind == "create":
            previous = self.originals.get(op.slot)
            payload = {"title": op.title, "priority": op.priority}
            return 409 if previous and previous[0] != payload else 201
        if op.slot not in self.live:
            return 404
        if op.kind == "read":
            return 200
        if op.stale:
            return 409
        if op.kind == "update":
            return 200 if op.status in ALLOWED[self.live[op.slot]["status"]] else 409
        if op.kind == "delete":
            return 204
        raise ValueError(f"Unknown operation: {op.kind}")

    def accept(self, op: Operation, status: int, body: dict | None) -> None:
        assert status == self.expected_status(op), f"unexpected status for {op}: {status}"
        if op.kind == "create" and status == 201:
            if op.slot in self.originals:
                assert body == self.originals[op.slot][1], "retry did not replay original response"
                return
            assert body is not None
            assert body["id"] not in self.identities.values(), "duplicate task identity"
            self.identities[op.slot] = body["id"]
            self.originals[op.slot] = ({"title": op.title, "priority": op.priority}, deepcopy(body))
            self.live[op.slot] = dict(
                title=op.title, priority=op.priority, description="", status="pending", version=1
            )
        elif op.kind == "update" and status == 200:
            self.live[op.slot].update(
                title=op.title,
                priority=op.priority,
                status=op.status,
                version=self.live[op.slot]["version"] + 1,
            )
        elif op.kind == "delete" and status == 204:
            del self.live[op.slot]
        if status == 200 or (op.kind == "create" and status == 201):
            assert body is not None
            self.assert_task(op.slot, body)

    def assert_task(self, slot: int, body: dict) -> None:
        assert body["id"] == self.identities[slot]
        assert {key: body[key] for key in FIELDS} == self.live[slot]
        assert body["updated_at"] >= body["created_at"]

    def assert_snapshot(self, tasks: list[dict]) -> None:
        assert len(tasks) == len(self.live), "database diverged from reference model"
        assert len({task["id"] for task in tasks}) == len(tasks)
        by_id = {task["id"]: task for task in tasks}
        for slot in self.live:
            self.assert_task(slot, by_id[self.identities[slot]])
