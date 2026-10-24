
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Register consistent handlers for unexpected API errors."""

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.error(
            "Unhandled exception while processing %s %s",
            request.method,
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )

        settings = get_settings()
        if settings.debug:
            raise exc

        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
        )

