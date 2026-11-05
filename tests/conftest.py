from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from testing_lab.config import Settings
from testing_lab.main import create_app
from tests.support.database import guarded_test_url, reset_database


@pytest.fixture
async def app():
    application = create_app(Settings(database_url=guarded_test_url()))
    async with application.router.lifespan_context(application):
        await reset_database(application.state.database.engine)
        yield application


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


@pytest.fixture
def database(app):
    return app.state.database
