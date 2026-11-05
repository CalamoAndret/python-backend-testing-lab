import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from testing_lab.config import Settings
from testing_lab.domain import Status, can_transition
from testing_lab.schemas import TaskCreate, TaskUpdate
from testing_lab.services import fingerprint


@pytest.mark.parametrize(
    "source,target,allowed",
    [
        ("pending", "in_progress", True),
        ("pending", "completed", False),
        ("in_progress", "completed", True),
        ("in_progress", "pending", False),
        ("completed", "pending", False),
        ("cancelled", "in_progress", False),
        ("pending", "cancelled", True),
        ("in_progress", "cancelled", True),
    ],
)
def test_status_contract(source, target, allowed):
    assert can_transition(Status(source), Status(target)) is allowed


@given(st.sampled_from(list(Status)))
def test_same_status_is_allowed(status):
    assert can_transition(status, status)


@given(st.sampled_from([Status.COMPLETED, Status.CANCELLED]), st.sampled_from(list(Status)))
def test_terminal_status_cannot_be_reopened(source, target):
    assert can_transition(source, target) is (source == target)


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=200))
def test_normalized_payloads_have_same_fingerprint(title):
    assert fingerprint(TaskCreate(title=f" {title} ")) == fingerprint(
        TaskCreate(title=title, description="", priority=3)
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"title": " "},
        {"title": "x" * 201},
        {"title": "ok", "priority": 0},
        {"title": "ok", "priority": True},
        {"title": "ok", "priority": "3"},
        {"title": "ok", "unexpected": "value"},
        {"title": "ok", "description": "x" * 10001},
    ],
)
def test_invalid_creation(payload):
    with pytest.raises(ValidationError):
        TaskCreate(**payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"expected_version": 1},
        {"expected_version": 0, "title": "ok"},
        {"expected_version": 1, "title": None},
        {"expected_version": True, "title": "ok"},
        {"expected_version": 1, "status": "unknown"},
    ],
)
def test_invalid_patch(payload):
    with pytest.raises(ValidationError):
        TaskUpdate(**payload)


def test_fingerprint_includes_every_field():
    base = TaskCreate(title="task")
    assert (
        len(
            {
                fingerprint(base),
                fingerprint(TaskCreate(title="other")),
                fingerprint(TaskCreate(title="task", priority=4)),
                fingerprint(TaskCreate(title="task", description="other")),
            }
        )
        == 4
    )


def test_postgresql_is_required():
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite+aiosqlite:///:memory:")


@pytest.mark.parametrize("text", ["nul\x00byte", "unpaired\ud800surrogate"])
def test_postgresql_incompatible_text_is_rejected(text):
    with pytest.raises(ValidationError):
        TaskCreate(title=text)
    with pytest.raises(ValidationError):
        TaskCreate(title="ok", description=text)
    with pytest.raises(ValidationError):
        TaskUpdate(expected_version=1, description=text)
