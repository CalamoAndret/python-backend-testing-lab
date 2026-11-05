from dataclasses import asdict, dataclass

from hypothesis import strategies as st


@dataclass(frozen=True)
class Operation:
    kind: str
    slot: int = 0
    title: str = "task"
    priority: int = 3
    status: str = "in_progress"
    stale: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


operations = st.builds(
    Operation,
    kind=st.sampled_from(["create", "read", "update", "delete"]),
    slot=st.integers(0, 3),
    title=st.sampled_from(["task", "changed", "Unicode: café 日本語"]),
    priority=st.integers(1, 5),
    status=st.sampled_from(["pending", "in_progress", "completed", "cancelled"]),
    stale=st.booleans(),
)
