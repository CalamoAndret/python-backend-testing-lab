from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from testing_lab.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine = create_async_engine(
            settings.database_url,
            isolation_level="READ COMMITTED",
            pool_pre_ping=True,
            hide_parameters=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            connect_args={
                "server_settings": {"statement_timeout": "10000", "lock_timeout": "5000"}
            },
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def close(self) -> None:
        await self.engine.dispose()
