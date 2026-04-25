"""FastAPI application factory."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.clients import router as clients_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.search import router as search_router
from app.core.config import Settings, get_settings
from app.core.errors import AppError, build_error_response
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app_settings = settings or get_settings()
    configure_logging(app_settings.app_env)

    app = FastAPI(title="Nevis Search API", version="1.0.0")
    app.state.settings = app_settings

    register_exception_handlers(app)
    app.include_router(clients_router)
    app.include_router(documents_router)
    app.include_router(search_router)
    app.include_router(health_router)

    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Register application-level exception handlers."""
    app.add_exception_handler(AppError, handle_app_error)


async def handle_app_error(_request: Request, exc: Exception) -> JSONResponse:
    """Convert application errors to HTTP JSON responses."""
    if not isinstance(exc, AppError):
        raise exc

    payload = build_error_response(exc).model_dump(exclude_none=True)
    return JSONResponse(status_code=exc.status_code, content=payload)


app = create_app()
