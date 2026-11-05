from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from testing_lab.domain import Status


def postgres_text(value: str) -> str:
    if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError("Text must contain valid Unicode without NUL characters")
    return value


SafeText = Annotated[str, AfterValidator(postgres_text)]
Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(postgres_text),
]
Priority = Annotated[int, Field(strict=True, ge=1, le=5)]
Version = Annotated[int, Field(strict=True, ge=1, le=2_147_483_646)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskCreate(InputModel):
    title: Title
    description: SafeText = Field(default="", max_length=10_000)
    priority: Priority = 3


class TaskUpdate(InputModel):
    expected_version: Version
    title: Title | None = None
    description: SafeText | None = Field(default=None, max_length=10_000)
    priority: Priority | None = None
    status: Status | None = None

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        fields = self.model_fields_set - {"expected_version"}
        if not fields:
            raise ValueError("At least one changed field is required")
        if any(getattr(self, field) is None for field in fields):
            raise ValueError("Changed fields cannot be null")
        return self


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    status: Status
    priority: int
    created_at: datetime
    updated_at: datetime
    version: int


class TaskPage(BaseModel):
    items: list[TaskRead]
    limit: int
    offset: int
    has_more: bool


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, object]] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody
