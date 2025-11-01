"""Main FastAPI application."""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import close_db, init_db
from app.middleware import ErrorHandlerMiddleware, LoggingMiddleware, RequestIDMiddleware
from app.settings import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.app_env == "dev" else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("application_startup", env=settings.app_env, db=settings.effective_database_url)

    # Initialize database
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))

    # Start scheduler for background jobs
    try:
        from app.scheduler import start_scheduler
        start_scheduler()
        logger.info("scheduler_started")
    except Exception as e:
        logger.error("scheduler_start_failed", error=str(e))

    yield

    # Cleanup
    logger.info("application_shutdown")
    
    # Stop scheduler
    try:
        from app.scheduler import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.error("scheduler_stop_failed", error=str(e))
    
    await close_db()


# Create FastAPI application
app = FastAPI(
    title="CRM-MT5-Python",
    description="CRM system with MetaTrader 5 and Pipedrive integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Add middlewares (order matters - first added is executed last)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
except RuntimeError:
    logger.warning("static_directory_not_found", path="app/ui/static")

# Setup Jinja2 templates
try:
    templates = Jinja2Templates(directory="app/ui/templates")
except Exception as e:
    logger.warning("templates_directory_not_found", path="app/ui/templates", error=str(e))
    templates = None

# Import and include routers
try:
    from app.routers import (
        auth,
        health,
        customers,
        agents,
        accounts,
        balance,
        positions,
        audit,
        reports,
        webhooks_pipedrive,
        users,
        websocket,
    )

    # Health check (no prefix, used by load balancers)
    app.include_router(health.router, prefix="/health", tags=["Health"])
    
    # Authentication
    app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
    
    # Business logic routers
    app.include_router(agents.router)
    app.include_router(customers.router)
    app.include_router(accounts.router)
    app.include_router(balance.router)
    app.include_router(positions.router)
    app.include_router(audit.router)
    app.include_router(reports.router)
    app.include_router(users.router)
    
    # WebSocket
    app.include_router(websocket.router)
    
    # Webhooks
    app.include_router(webhooks_pipedrive.router)
    
    logger.info("routers_registered", count=12)
except ImportError as e:
    logger.warning("router_import_failed", error=str(e))
# app.include_router(webhooks_pipedrive.router, prefix="/webhooks/pipedrive", tags=["Webhooks"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "CRM-MT5-Python API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
