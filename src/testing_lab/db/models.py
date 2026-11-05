from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("char_length(btrim(title)) BETWEEN 1 AND 200", name="ck_task_title"),
        CheckConstraint("char_length(description) <= 10000", name="ck_task_description"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')", name="ck_task_status"
        ),
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_task_priority"),
        CheckConstraint("version >= 1", name="ck_task_version"),
        CheckConstraint("updated_at >= created_at", name="ck_task_timestamps"),
        Index("ix_tasks_created_id", "created_at", "id"),
        Index("ix_tasks_status_created_id", "status", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    priority: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        CheckConstraint("char_length(key) BETWEEN 1 AND 128", name="ck_idempotency_key"),
        CheckConstraint("char_length(fingerprint) = 64", name="ck_idempotency_fingerprint"),
    )

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
