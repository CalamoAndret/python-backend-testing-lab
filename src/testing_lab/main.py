import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from asyncpg import PostgresError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from testing_lab.api.routes import router
from testing_lab.config import Settings
from testing_lab.db.session import Database
from testing_lab.errors import DomainError

logger = logging.getLogger(__name__)


def error(
    status: int,
    code: str,
    message: str,
    details: list | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or []}},
        headers=headers,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database = Database(config)
        try:
            yield
        finally:
            await app.state.database.close()

    app = FastAPI(title="Python Backend Testing Lab", version="1.0.0", lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Avoid echoing arbitrary request bodies and non-JSON exception contexts.
        details = [
            {"location": list(e["loc"]), "message": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return error(422, "validation_error", "Request validation failed.", details)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return error(exc.status_code, "http_error", str(exc.detail), headers=exc.headers)

    @app.exception_handler(OSError)
    @app.exception_handler(PostgresError)
    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: Exception) -> JSONResponse:
        # Driver exceptions can contain SQL, bound values, and PostgreSQL row details.
        logger.error("database_operation_failed", extra={"error_type": type(exc).__name__})
        return error(503, "database_unavailable", "Database operation failed; retry later.")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unexpected_request_failure", extra={"path": request.url.path})
        return error(500, "internal_error", "An unexpected error occurred.")

    return app


app = create_app()
