"""FastAPI middleware for request tracking, error handling, and logging."""
import time
import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add a unique request ID to each request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and add request ID."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Add request ID to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        start_time = time.time()

        # Log request
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_host=request.client.host if request.client else None,
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log response
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
            )

            return response
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration * 1000, 2),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for global error handling."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle errors globally."""
        try:
            return await call_next(request)
        except ValueError as e:
            logger.warning("validation_error", error=str(e), path=request.url.path)
            return JSONResponse(
                status_code=400,
                content={"detail": str(e), "type": "validation_error"},
            )
        except PermissionError as e:
            logger.warning("permission_error", error=str(e), path=request.url.path)
            return JSONResponse(
                status_code=403,
                content={"detail": str(e), "type": "permission_error"},
            )
        except Exception as e:
            logger.exception("internal_error", error=str(e), path=request.url.path)
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "type": "internal_error",
                    "request_id": getattr(request.state, "request_id", None),
                },
            )
