from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from testing_lab.api.routes import get_session
from testing_lab.config import Settings
from testing_lab.main import create_app


async def test_http_and_validation_errors_without_database():
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        assert (await client.get("/health/live")).json() == {"status": "ok"}
        assert (await client.get("/unknown")).json()["error"]["code"] == "http_error"
        response = await client.post("/tasks", json={"title": " "})
        assert response.status_code == 422
        assert response.json()["error"]["details"][0]["location"] == ["body", "title"]
        assert "TaskRead" in (await client.get("/openapi.json")).json()["components"]["schemas"]
        wrong_method = await client.post("/health/live")
        assert wrong_method.status_code == 405
        assert "GET" in wrong_method.headers["allow"]


async def test_database_error_is_sanitized(caplog):
    app = create_app()

    async def broken_session():
        raise OperationalError("SELECT secret", {}, Exception("private credentials"))
        yield  # pragma: no cover

    app.dependency_overrides[get_session] = broken_session
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "private" not in response.text
    assert "private credentials" not in caplog.text
    assert "SELECT secret" not in caplog.text
    assert any(
        record.error_type == "OperationalError"
        for record in caplog.records
        if record.name == "testing_lab.main"
    )


async def test_unreachable_database_reports_not_ready():
    app = create_app(Settings(database_url="postgresql+asyncpg://lab@127.0.0.1:1/unavailable"))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "database_unavailable"
        assert (await client.get("/health/live")).status_code == 200


async def test_unexpected_errors_are_sanitized():
    app = create_app()

    async def broken_session():
        raise RuntimeError("private internal state")
        yield  # pragma: no cover

    app.dependency_overrides[get_session] = broken_session
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client,
    ):
        response = await client.get("/health/ready")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private" not in response.text
