from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.engine import make_url

from tests.support.database import guarded_test_url, reset_database


def test_missing_test_database_is_rejected(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="Set TEST_DATABASE_URL"):
        guarded_test_url()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://lab@localhost/production",
        "sqlite:///lab_test",
    ],
)
async def test_reset_rejects_unsafe_engine_before_connecting(monkeypatch, url):
    monkeypatch.setenv("TEST_DATABASE_URL", url)
    with pytest.raises(RuntimeError, match="Destructive test isolation"):
        guarded_test_url()
    engine = SimpleNamespace(url=make_url(url), begin=Mock())
    with pytest.raises(RuntimeError, match="Destructive test isolation"):
        await reset_database(engine)
    engine.begin.assert_not_called()
