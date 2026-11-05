from enum import StrEnum


class Status(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.PENDING: frozenset({Status.IN_PROGRESS, Status.CANCELLED}),
    Status.IN_PROGRESS: frozenset({Status.COMPLETED, Status.CANCELLED}),
    Status.COMPLETED: frozenset(),
    Status.CANCELLED: frozenset(),
}


def can_transition(source: Status, target: Status) -> bool:
    return source == target or target in TRANSITIONS[source]
