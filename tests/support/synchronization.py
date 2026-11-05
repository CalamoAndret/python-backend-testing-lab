import asyncio

from sqlalchemy import text


async def wait_for_database_block(database, blocked_pid: int, blocker_pid: int) -> None:
    """Observe the actual PostgreSQL lock dependency, with a bounded deadline.

    Each query yields to the event loop. There are no timing-based sleeps.
    """
    async with asyncio.timeout(10), database.engine.connect() as observer:
        while True:
            blockers = await observer.scalar(
                text("SELECT pg_blocking_pids(:pid)"), {"pid": blocked_pid}
            )
            if blocker_pid in blockers:
                return
