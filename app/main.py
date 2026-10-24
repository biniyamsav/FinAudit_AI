
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.api.error_handlers import register_error_handlers
from app.core.config import get_settings

# Local frontend dev servers only; never widen this to "*" with credentials.
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def create_app() -> FastAPI:
    """Create and configure the FinAudit_AI application."""

    settings = get_settings()
    settings.validate_for_startup()

    app = FastAPI(
        title="FinAudit_AI",
        description="Financial Knowledge Graph & Compliance Audit Engine",
        version="0.1.0",
        debug=settings.environment == "development",
    )

    register_error_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
