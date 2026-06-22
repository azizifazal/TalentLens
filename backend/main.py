from __future__ import annotations

import os
import time

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from mangum import Mangum

from backend.core.config import get_settings
from backend.core.exceptions import TalentLensError
from backend.core.logging_config import configure_logging
from backend.routes import rankings, resumes, sessions

configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
logger = structlog.get_logger(__name__)

settings = get_settings()

app = FastAPI(
    title="TalentLens AI API",
    description="AI-powered candidate ranking and shortlisting engine",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)



@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.monotonic()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        path=request.url.path,
        method=request.method,
    )
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start_time) * 1000, 2)
    logger.info(
        "request_completed",
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.exception_handler(TalentLensError)
async def talentlens_exception_handler(request: Request, exc: TalentLensError) -> JSONResponse:
    logger.warning("talentlens_error", message=exc.message, status_code=exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again."},
    )


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    return {"status": "healthy", "service": "talentlens-api", "version": "2.0.0"}


app.include_router(sessions.router)
app.include_router(resumes.router)
app.include_router(rankings.router)


handler = Mangum(app, lifespan="off", api_gateway_base_path=None)
