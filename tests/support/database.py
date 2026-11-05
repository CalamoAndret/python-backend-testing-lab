import os

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine


def guarded_test_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        raise RuntimeError(
            "Set TEST_DATABASE_URL to a migrated PostgreSQL database ending in _test"
        )
    validate_test_database(make_url(value))
    return value


def validate_test_database(url: URL) -> None:
    if url.drivername != "postgresql+asyncpg" or not (url.database or "").endswith("_test"):
        raise RuntimeError(
            "Destructive test isolation requires postgresql+asyncpg and a _test suffix"
        )


async def reset_database(engine: AsyncEngine) -> None:
    # Enforce the guard here too, before any connection or destructive statement.
    validate_test_database(engine.url)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE idempotency_keys, tasks"))
