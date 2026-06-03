"""Payment Service application entrypoint."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1.routes import router as api_router
from app.api.v1.webhook import router as webhook_router
from app.core.config import settings
from app.core.logging import configure_service_logging
from app.db.database import check_database_ready
from shared.errors import register_error_handlers
from shared.internal_mldsa_mtls import InternalMLDSAMTLSMiddleware
from shared.request_context import RequestContextMiddleware


configure_service_logging()

app = FastAPI(
    title="Payment Service API",
    version="0.1.0",
    description="Stripe sandbox payment and webhook API.",
)
app.state.settings = settings
app.add_middleware(RequestContextMiddleware, settings=settings)
app.add_middleware(InternalMLDSAMTLSMiddleware, settings=settings)
register_error_handlers(app)
app.include_router(api_router, prefix="/api/v1")
app.include_router(webhook_router)


@app.get("/health/live", tags=["health"])
async def live():
    return {"status": "live", "service": settings.service_name}


@app.get("/health/ready", tags=["health"])
async def ready():
    if await check_database_ready():
        return {"status": "ready", "service": settings.service_name, "database": "ok"}
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "service": settings.service_name, "database": "unavailable"},
    )
